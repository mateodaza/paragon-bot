import asyncio
import time

import httpx

API_URL = "https://api.hyperliquid.xyz/info"

_client: httpx.AsyncClient | None = None
_semaphore = asyncio.Semaphore(5)


class _RateLimiter:
    """Token bucket: 1200 weight/min = 20 weight/sec."""

    def __init__(self, capacity: float = 1200.0, refill_rate: float = 20.0):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, weight: float):
        async with self._lock:
            self._refill()
            while self.tokens < weight:
                wait = (weight - self.tokens) / self.refill_rate
                await asyncio.sleep(wait)
                self._refill()
            self.tokens -= weight

    def _refill(self):
        now = time.monotonic()
        self.tokens = min(
            self.capacity, self.tokens + (now - self._last) * self.refill_rate
        )
        self._last = now


_rate = _RateLimiter()


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=10)
    return _client


async def _post(payload: dict, weight: float = 2.0) -> dict | list:
    await _rate.acquire(weight)
    async with _semaphore:
        client = await _get_client()
        resp = await client.post(API_URL, json=payload)
        resp.raise_for_status()
        return resp.json()


async def get_meta(dex: str = "para") -> list | None:
    try:
        return await _post({"type": "metaAndAssetCtxs", "dex": dex}, weight=20.0)
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


async def get_fill_info(
    user: str, coin: str, trade_time_ms: int, tx_hash: str, side: str
) -> dict | None:
    """Match a specific fill by coin + hash + side. Returns {dir, start_position}."""
    try:
        fills = await _post(
            {
                "type": "userFillsByTime",
                "user": user,
                "startTime": trade_time_ms - 2000,
                "endTime": trade_time_ms + 2000,
            },
            weight=20.0,
        )
    except Exception:
        return None

    if not fills:
        return None
    for fill in fills:
        if (
            fill.get("coin") == coin
            and fill.get("hash") == tx_hash
            and fill.get("side") == side
        ):
            return {
                "dir": fill.get("dir"),
                "start_position": fill.get("startPosition", ""),
            }
    return None
