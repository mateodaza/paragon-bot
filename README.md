# Paragon Bot

Discord bot that monitors [Paragon](https://paragon.trade) perpetual trades on Hyperliquid and posts notifications.

Tracks: **BTC.D**, **AVGO**, **OTHERS**, **TOTAL2**

## Setup

```bash
# Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and configure
git clone <repo-url> && cd paragon-bot
cp .env.example .env
# Edit .env with your Discord bot token and channel ID
```

## Run

```bash
# Smoke test — verifies API connectivity and message formatting
uv run python main.py --dry-run --once

# Dry run — prints to terminal instead of Discord
uv run python main.py --dry-run

# Production
uv run python main.py
```

## Test

```bash
uv run pytest
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_BOT_TOKEN` | Yes | — | Discord bot token |
| `CHANNEL_ID` | Yes | — | Discord channel ID |
| `MIN_NOTIONAL_USD` | No | `100` | Minimum trade size to notify |
| `MAX_EMOJIS` | No | `80` | Max ⚡️ per message |
| `INCLUDE_TX_LINK` | No | `false` | Include Hyperliquid TX link (exposes wallet) |
| `POSITION_MODE` | No | `trade_activity` | `trade_activity` or `strict_open` |

### Position Modes

- **`trade_activity`** — Reports all trades above threshold. Direction inferred from taker side.
- **`strict_open`** — Only reports confirmed position activity via `userFillsByTime`: new opens (`startPosition == 0`), increases (adding to existing), and flips (reversing direction). Closes are filtered out. Adds one REST call per trade.

## Deploy (systemd)

```ini
# /etc/systemd/system/paragon-bot.service
[Unit]
Description=Paragon Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/paragon-bot
Environment=PATH=/root/.local/bin:/usr/bin
ExecStart=/root/.local/bin/uv run python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable paragon-bot
sudo systemctl start paragon-bot
journalctl -fu paragon-bot  # logs
```
