TICKERS: dict[str, dict] = {
    "para:BTCD": {
        "display_name": "BTC.D",
        "trade_url": "https://app.hyperliquid.xyz/trade/para:BTC.D",
    },
    "para:AVGO": {
        "display_name": "AVGO",
        "trade_url": "https://app.hyperliquid.xyz/trade/para:AVGO",
    },
    "para:OTHERS": {
        "display_name": "OTHERS",
        "trade_url": "https://app.hyperliquid.xyz/trade/para:OTHERS",
    },
    "para:TOTAL2": {
        "display_name": "TOTAL2",
        "trade_url": "https://app.hyperliquid.xyz/trade/para:TOTAL2",
    },
}

COINS = list(TICKERS.keys())


def display_name(coin: str) -> str:
    return TICKERS.get(coin, {}).get("display_name", coin)


def trade_url(coin: str) -> str:
    return TICKERS.get(coin, {}).get("trade_url", "")
