import os

import hikari
from dotenv import load_dotenv

from configs.tickers import display_name, trade_url

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

MAX_EMOJIS = int(os.getenv("MAX_EMOJIS", "80"))
INCLUDE_TX_LINK = os.getenv("INCLUDE_TX_LINK", "false").lower() == "true"


async def send_message_to_channel(
    coin: str,
    direction: str,
    notional_usd: float,
    leverage: str | None,
    title: str,
    tx_hash: str | None = None,
):
    rest = hikari.RESTApp()
    await rest.start()

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

    await rest.close()


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
        url = trade_url(coin)
        lines.append(f"[TX](https://app.hyperliquid.xyz/explorer/tx/{tx_hash})")
    elif tx_hash and not INCLUDE_TX_LINK:
        pass

    return "\n".join(lines)
