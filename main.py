import argparse
import asyncio
import json
import os
import sys
import time

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

MIN_NOTIONAL_USD = float(os.getenv("MIN_NOTIONAL_USD", "100"))
POSITION_MODE = os.getenv("POSITION_MODE", "trade_activity")
AGGREGATE_WINDOW_S = 0.5

ZERO_HASH = "0x" + "0" * 64

_OPEN_DIRS = {"Open Long", "Open Short", "Long > Short", "Short > Long"}
_SKIP_DIRS = {"Close Long", "Close Short"}


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


# ---------------------------------------------------------------------------
# Main event loop
# ---------------------------------------------------------------------------

async def trade_monitor(dry_run: bool = False):
    while True:
        try:
            async with connect(HYPERLIQUID_WS) as ws:
                for coin in COINS:
                    sub = {
                        "method": "subscribe",
                        "subscription": {"type": "trades", "coin": coin},
                    }
                    await ws.send(json.dumps(sub))

                print("[green]Connected to Hyperliquid WS — monitoring Paragon trades")

                pending: dict[str, dict] = {}

                async def flush_pending():
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
                    if total < MIN_NOTIONAL_USD:
                        return

                    coin = agg["coin"]
                    direction = get_direction(agg)
                    taker = agg["_taker"]
                    trade_time = agg["time"]
                    tx_hash = agg.get("hash")

                    title = "Paragon Trade!"

                    if POSITION_MODE == "strict_open":
                        fill = await get_fill_info(
                            taker, coin, trade_time, tx_hash, agg["side"]
                        )
                        if fill is None:
                            return
                        fill_dir = fill["dir"]
                        if fill_dir in _SKIP_DIRS or fill_dir not in _OPEN_DIRS:
                            return
                        if fill["start_position"] in ("0.0", "0", ""):
                            title = "New Paragon Position!"
                        else:
                            title = "Paragon Position Increased!"

                    leverage = await get_leverage(taker, coin)

                    if dry_run:
                        msg = format_message(
                            coin, direction, total, leverage, title, tx_hash
                        )
                        print(f"\n{'='*50}")
                        print(msg)
                        print(f"{'='*50}\n")
                    else:
                        await send_message_to_channel(
                            coin, direction, total, leverage, title, tx_hash
                        )

                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except TimeoutError:
                        for agg in await flush_pending():
                            await process_aggregated(agg)
                        continue

                    data = json.loads(raw)
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

                    for agg in await flush_pending():
                        await process_aggregated(agg)

        except Exception as e:
            print(f"[red]WebSocket error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

async def _fetch_one_trade(timeout_s: float = 15) -> dict | None:
    try:
        async with connect(HYPERLIQUID_WS) as ws:
            for coin in COINS:
                await ws.send(json.dumps({
                    "method": "subscribe",
                    "subscription": {"type": "trades", "coin": coin},
                }))
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
                data = json.loads(raw)
                if data.get("channel") == "trades" and data.get("data"):
                    for t in data["data"]:
                        if validate_trade(t) and t.get("coin") in COINS:
                            return t
    except (TimeoutError, Exception):
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
    trade = await _fetch_one_trade(timeout_s=15)
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
        ("para:TOTAL2", "SHORT", 100.0, "3.2", "Paragon Position Increased!"),
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
        code = await smoke_test()
        sys.exit(code)
    await trade_monitor(dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
