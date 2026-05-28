import argparse
import asyncio
import json
import os
import sys
import time

import websockets.exceptions
from dotenv import load_dotenv
from rich import print
from rich.traceback import install
from websockets.asyncio.client import connect

from configs.tickers import COINS, display_name
from utils.discord_bot import format_message, send_message_to_channel
from utils.hyperliquid_api import get_fill_info, get_leverage, get_meta

load_dotenv()
install()

HYPERLIQUID_WS = "wss://api.hyperliquid.xyz/ws"
AGGREGATE_WINDOW_S = 0.5
ZERO_HASH = "0x" + "0" * 64

_OPEN_DIRS = {"Open Long", "Open Short", "Long > Short", "Short > Long"}
_FLIP_DIRS = {"Long > Short", "Short > Long"}


def parse_args():
    parser = argparse.ArgumentParser(description="Paragon Discord Bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print messages to terminal instead of Discord",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run smoke test (fetch meta, format sample message) and exit",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def validate_config(require_discord: bool = True) -> dict:
    """Validate env vars at startup. Returns parsed config or exits."""
    errors: list[str] = []

    mode = os.getenv("POSITION_MODE", "trade_activity")
    if mode not in ("trade_activity", "strict_open"):
        errors.append(
            f"POSITION_MODE must be 'trade_activity' or 'strict_open', got '{mode}'"
        )

    min_usd_raw = os.getenv("MIN_NOTIONAL_USD", "100")
    try:
        min_usd = float(min_usd_raw)
    except ValueError:
        errors.append(f"MIN_NOTIONAL_USD must be a number, got '{min_usd_raw}'")
        min_usd = 100.0

    max_emoji_raw = os.getenv("MAX_EMOJIS", "80")
    try:
        int(max_emoji_raw)
    except ValueError:
        errors.append(f"MAX_EMOJIS must be a number, got '{max_emoji_raw}'")

    if require_discord:
        if not os.getenv("DISCORD_BOT_TOKEN"):
            errors.append("DISCORD_BOT_TOKEN is not set")

        channel_raw = os.getenv("CHANNEL_ID", "")
        if not channel_raw:
            errors.append("CHANNEL_ID is not set")
        elif not channel_raw.isdigit():
            errors.append(f"CHANNEL_ID must be a number, got '{channel_raw}'")

    if errors:
        print("[bold red]Configuration errors:[/bold red]")
        for e in errors:
            print(f"[red]  • {e}[/red]")
        sys.exit(1)

    return {"position_mode": mode, "min_notional_usd": min_usd}


# ---------------------------------------------------------------------------
# Trade validation and extraction
# ---------------------------------------------------------------------------

def validate_trade(trade: dict) -> bool:
    side = trade.get("side")
    users = trade.get("users", [])
    return side in ("A", "B") and len(users) == 2


def get_taker(trade: dict) -> str:
    """side B = taker bought → taker is users[0].
    side A = taker sold  → taker is users[1]."""
    users = trade["users"]
    return users[0] if trade["side"] == "B" else users[1]


def get_direction(trade: dict) -> str:
    return "LONG" if trade["side"] == "B" else "SHORT"


def notional(trade: dict) -> float:
    return float(trade.get("px", 0)) * float(trade.get("sz", 0))


# ---------------------------------------------------------------------------
# Position classification (strict_open mode)
# ---------------------------------------------------------------------------

def classify_position(fill_dir: str | None, start_position: str) -> str | None:
    """Returns title string for the Discord message, or None to skip."""
    if fill_dir is None or fill_dir not in _OPEN_DIRS:
        return None
    if fill_dir in _FLIP_DIRS:
        return "Paragon Position Flipped!"
    if start_position in ("0.0", "0", ""):
        return "New Paragon Position!"
    return "Paragon Position Increased!"


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def agg_key(trade: dict) -> str | None:
    """Key for grouping split fills. Returns None for zero-hash TWAP fills."""
    tx_hash = trade.get("hash", "")
    if tx_hash == ZERO_HASH:
        return None
    return f"{trade['coin']}|{trade['side']}|{get_taker(trade)}|{tx_hash}"


def aggregate_trades(trades: list[dict]) -> dict:
    """Merge a group of trades sharing the same agg_key into one summary."""
    total_sz = sum(float(t["sz"]) for t in trades)
    total_notional = sum(notional(t) for t in trades)
    vwap = total_notional / total_sz if total_sz else 0
    first = trades[0]
    return {
        "coin": first["coin"],
        "side": first["side"],
        "px": str(vwap),
        "sz": str(total_sz),
        "time": first["time"],
        "hash": first.get("hash", ""),
        "users": first["users"],
        "_notional": total_notional,
        "_taker": get_taker(first),
    }


async def _subscribe_all(ws):
    for coin in COINS:
        await ws.send(json.dumps({
            "method": "subscribe",
            "subscription": {"type": "trades", "coin": coin},
        }))


# ---------------------------------------------------------------------------
# Main event loop
# ---------------------------------------------------------------------------

async def trade_monitor(config: dict, dry_run: bool = False):
    position_mode = config["position_mode"]
    min_notional = config["min_notional_usd"]

    while True:
        try:
            async with connect(HYPERLIQUID_WS) as ws:
                await _subscribe_all(ws)
                print("[green]Connected to Hyperliquid WS — monitoring Paragon trades")

                pending: dict[str, dict] = {}

                def flush_pending():
                    now = time.time()
                    ready = []
                    expired = [
                        k
                        for k, v in pending.items()
                        if now - v["last_seen"] >= AGGREGATE_WINDOW_S
                    ]
                    for k in expired:
                        group = pending.pop(k)
                        ready.append(aggregate_trades(group["trades"]))
                    return ready

                async def process_aggregated(agg: dict):
                    total = agg["_notional"]
                    if total < min_notional:
                        return

                    coin = agg["coin"]
                    direction = get_direction(agg)
                    taker = agg["_taker"]
                    trade_time = agg["time"]
                    tx_hash = agg.get("hash")

                    title = "Paragon Trade!"

                    if position_mode == "strict_open":
                        fill = await get_fill_info(
                            taker, coin, trade_time, tx_hash, agg["side"]
                        )
                        fill_dir = fill["dir"] if fill else None
                        start_pos = fill["start_position"] if fill else ""
                        title = classify_position(fill_dir, start_pos)
                        if title is None:
                            return

                    leverage = await get_leverage(taker, coin)

                    if dry_run:
                        msg = format_message(
                            coin, direction, total, leverage, title, tx_hash
                        )
                        print(f"\n{'='*50}")
                        print(msg)
                        print(f"{'='*50}\n")
                    else:
                        try:
                            await send_message_to_channel(
                                coin, direction, total, leverage, title, tx_hash
                            )
                        except Exception as e:
                            print(f"[red]Discord error: {type(e).__name__}: {e}[/red]")

                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except TimeoutError:
                        for agg in flush_pending():
                            await process_aggregated(agg)
                        continue

                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        print("[yellow]Skipping malformed WS message[/yellow]")
                        continue

                    if data.get("channel") != "trades":
                        continue

                    trades = data.get("data", [])
                    for trade in trades:
                        if trade.get("coin") not in COINS:
                            continue
                        if not validate_trade(trade):
                            continue

                        key = agg_key(trade)
                        if key is None:
                            agg = aggregate_trades([trade])
                            await process_aggregated(agg)
                            continue

                        if key not in pending:
                            pending[key] = {"trades": [], "last_seen": 0}
                        pending[key]["trades"].append(trade)
                        pending[key]["last_seen"] = time.time()

                    for agg in flush_pending():
                        await process_aggregated(agg)

        except (websockets.exceptions.ConnectionClosed, OSError) as e:
            print(f"[red]WebSocket connection lost: {e}. Reconnecting in 5s...[/red]")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[red]Unexpected error: {type(e).__name__}: {e}[/red]")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

async def _fetch_one_trade(timeout_s: float = 15) -> dict | None:
    """Returns a trade dict on success, None on clean timeout. Raises on connection error."""
    async with connect(HYPERLIQUID_WS) as ws:
        await _subscribe_all(ws)
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
                data = json.loads(raw)
                if data.get("channel") == "trades" and data.get("data"):
                    for t in data["data"]:
                        if validate_trade(t) and t.get("coin") in COINS:
                            return t
        except TimeoutError:
            return None


async def smoke_test() -> int:
    print("[bold]Running smoke test...[/bold]\n")

    print("1. Fetching Paragon metadata from Hyperliquid API...")
    meta = await get_meta("para")
    if not meta:
        print("[red]  FAIL: could not reach Hyperliquid API[/red]")
        return 1

    universe = meta[0].get("universe", []) if isinstance(meta, list) else []
    found = {a["name"] for a in universe if a["name"] in COINS}
    expected = set(COINS)
    if found != expected:
        missing = expected - found
        print(f"[red]  FAIL: missing tickers — {missing}[/red]")
        return 1
    print(f"[green]  OK: all tickers found — {', '.join(sorted(found))}[/green]")

    print("\n2. Connecting to Hyperliquid WS (15s timeout)...")
    try:
        trade = await _fetch_one_trade(timeout_s=15)
    except Exception as e:
        print(f"[red]  FAIL: WebSocket connection error — {e}[/red]")
        return 1
    if trade:
        taker = get_taker(trade)
        coin = trade["coin"]
        lev = await get_leverage(taker, coin)
        direction = get_direction(trade)
        ntl = notional(trade)
        msg = format_message(coin, direction, ntl, lev, "Paragon Trade!", trade.get("hash"))
        print(f"[green]  OK: live trade captured[/green]")
        print(msg)
    else:
        print("  INFO: no trades in 15s (low volume expected for Paragon)")

    print("\n3. Sample message formatting:\n")
    samples = [
        ("para:BTCD", "LONG", 2500.0, "5", "Paragon Trade!"),
        ("para:AVGO", "SHORT", 150.0, "20", "New Paragon Position!"),
        ("para:OTHERS", "LONG", 50000.0, None, "Paragon Trade!"),
        ("para:TOTAL2", "SHORT", 100.0, "3.2", "Paragon Position Flipped!"),
    ]
    for coin, direction, size, leverage, title in samples:
        msg = format_message(coin, direction, size, leverage, title)
        color = "green" if direction == "LONG" else "red"
        print(f"[{color}]--- {display_name(coin)} ---[/{color}]")
        print(msg)
        print()

    print("[bold green]Smoke test passed.[/bold green]")
    return 0


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

async def main():
    args = parse_args()

    if args.once:
        validate_config(require_discord=False)
        code = await smoke_test()
        sys.exit(code)

    config = validate_config(require_discord=not args.dry_run)
    await trade_monitor(config, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
