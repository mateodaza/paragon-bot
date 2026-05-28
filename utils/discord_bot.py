import os

import hikari

from configs.tickers import display_name

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

_channel_raw = os.getenv("CHANNEL_ID", "0") or "0"
CHANNEL_ID = int(_channel_raw) if _channel_raw.isdigit() else 0

_max_raw = os.getenv("MAX_EMOJIS", "80") or "80"
MAX_EMOJIS = int(_max_raw) if _max_raw.isdigit() else 80
INCLUDE_TX_LINK = os.getenv("INCLUDE_TX_LINK", "false").lower() == "true"

_rest: hikari.RESTApp | None = None


async def _get_rest() -> hikari.RESTApp:
    global _rest
    if _rest is None:
        _rest = hikari.RESTApp()
        await _rest.start()
    return _rest


async def send_message_to_channel(
    coin: str,
    direction: str,
    notional_usd: float,
    leverage: str | None,
    title: str,
    tx_hash: str | None = None,
):
    rest = await _get_rest()

    message = format_message(
        coin, direction, notional_usd, leverage, title, tx_hash
    )
    color = (
        hikari.Color(0x00CC66) if direction == "LONG" else hikari.Color(0xFF4444)
    )

    async with rest.acquire(DISCORD_BOT_TOKEN, "Bot") as client:
        await client.create_message(
            CHANNEL_ID,
            embed=hikari.Embed(description=message, color=color),
        )


def format_message(
    coin: str,
    direction: str,
    notional_usd: float,
    leverage: str | None,
    title: str,
    tx_hash: str | None = None,
) -> str:
    emoji_count = min(max(int(notional_usd / 100), 1), MAX_EMOJIS)
    emoji_str = "⚡️" * emoji_count

    ticker = display_name(coin)
    lev_str = f"{leverage}x" if leverage else "Unknown"
    size_str = f"${notional_usd:,.2f}"

    lines = [
        f"**{title}**",
        emoji_str,
        f"**Ticker:** {ticker}",
        f"**Direction:** {direction}",
        f"**Size:** {size_str}",
        f"**Leverage:** {lev_str}",
    ]

    if INCLUDE_TX_LINK and tx_hash:
        lines.append(f"[TX](https://app.hyperliquid.xyz/explorer/tx/{tx_hash})")

    return "\n".join(lines)
