import asyncio

import httpx

API_URL = "https://api.hyperliquid.xyz/info"

_semaphore = asyncio.Semaphore(10)


async def _post(payload: dict, timeout: float = 10) -> dict | list:
    async with _semaphore:
        async with httpx.AsyncClient() as client:
            resp = await client.post(API_URL, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()


async def get_meta(dex: str = "para") -> list | None:
    try:
        return await _post({"type": "metaAndAssetCtxs", "dex": dex})
    except Exception:
        return None


async def get_leverage(user: str, coin: str) -> str | None:
    try:
        state = await _post(
            {"type": "clearinghouseState", "user": user, "dex": "para"}
        )
    except Exception:
        return None

    for pos in state.get("assetPositions", []):
        p = pos.get("position", {})
        if p.get("coin") == coin:
            lev = p.get("leverage", {})
            return lev.get("value")
    return None


async def get_fill_direction(
    user: str, coin: str, trade_time_ms: int
) -> str | None:
    """Query userFillsByTime for strict_open mode."""
    try:
        fills = await _post(
            {
                "type": "userFillsByTime",
                "user": user,
                "startTime": trade_time_ms - 2000,
                "endTime": trade_time_ms + 2000,
            }
        )
    except Exception:
        return None

    if not fills:
        return None
    for fill in fills:
        if fill.get("coin") == coin:
            return fill.get("dir")
    return None
