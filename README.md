# Paragon Bot

Discord bot that monitors [Paragon](https://paragon.trade) perpetual trades on Hyperliquid and posts notifications.

Tracks: **BTC.D**, **AVGO**, **OTHERS**, **TOTAL2**

No Hyperliquid API key needed — all endpoints are public.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Rust-based Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → name it (e.g. "Paragon Trades")
2. Go to **Bot** tab → **Reset Token** → copy the token → this is your `DISCORD_BOT_TOKEN`
3. Under **Bot** → **Privileged Gateway Intents** → nothing extra needed (we use REST, not gateway)
4. Go to **OAuth2** → **URL Generator** → check **bot** scope → check **Send Messages** permission
5. Copy the generated URL → open it in browser → invite the bot to your server
6. In Discord: **Settings → Advanced → Enable Developer Mode** → right-click the target channel → **Copy Channel ID** → this is your `CHANNEL_ID`

## Install & Run

```bash
git clone <repo-url> && cd paragon-bot
cp .env.example .env
# Paste DISCORD_BOT_TOKEN and CHANNEL_ID into .env

# Smoke test — verifies Hyperliquid API + WS connectivity, exits nonzero on failure
uv run python main.py --dry-run --once

# Dry run — streams live trades to terminal (no Discord posting)
uv run python main.py --dry-run

# Production
uv run python main.py
```

## Test

```bash
uv run --extra dev pytest
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_BOT_TOKEN` | Yes | — | From Discord Developer Portal → Bot → Token |
| `CHANNEL_ID` | Yes | — | Right-click channel → Copy Channel ID |
| `MIN_NOTIONAL_USD` | No | `100` | Minimum trade size (USD) to trigger a notification |
| `MAX_EMOJIS` | No | `80` | Max ⚡️ emojis per message |
| `INCLUDE_TX_LINK` | No | `false` | Include Hyperliquid TX link (exposes wallet activity) |
| `POSITION_MODE` | No | `trade_activity` | `trade_activity` or `strict_open` |

### Position Modes

- **`trade_activity`** — Reports all trades above threshold. Direction inferred from taker side.
- **`strict_open`** — Only reports confirmed position activity via `userFillsByTime`: new opens (`startPosition == 0`), increases (adding to existing), and flips (reversing direction). Closes are filtered out. Adds one REST call per trade.

## Deploy

### Railway (recommended)

Easiest option — no server management, ~$5/mo. This is a background worker (no web port or public domain needed).

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Add `DISCORD_BOT_TOKEN` and `CHANNEL_ID` in **Variables**
4. Set **Start Command** in service settings to: `uv run python main.py`

Or commit a `railway.json` to the repo root:
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "deploy": {
    "startCommand": "uv run python main.py"
  }
}
```

### VPS (systemd)

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
journalctl -fu paragon-bot  # tail logs
```
