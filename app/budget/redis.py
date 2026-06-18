"""Redis client for budget operations with graceful fallback."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BudgetRedisClient:
    """Redis client for atomic budget operations.

    Graceful degradation: if Redis is unavailable or not configured,
    _available=False and all operations return defaults (0.0).
    """

    def __init__(self, redis_url: str = ""):
        self._redis_url = redis_url
        self._client = None
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    async def initialize(self):
        """Connect to Redis. Sets _available=False on failure."""
        if not self._redis_url:
            logger.info("BudgetRedisClient: no URL configured, budget checks disabled")
            self._available = False
            return

        try:
            import redis.asyncio  # noqa: F401
        except ImportError:
            logger.warning("BudgetRedisClient: redis-py not installed, budget checks disabled")
            self._available = False
            return

        try:
            self._client = redis.asyncio.Redis.from_url(
                self._redis_url, decode_responses=True
            )
            await self._client.ping()
            self._available = True
            logger.info("BudgetRedisClient: connected to %s", self._redis_url)
        except Exception as exc:
            logger.warning("BudgetRedisClient: connection failed (%s), budget checks disabled", exc)
            self._client = None
            self._available = False

    async def get_consumed(self, user_id: int, period: str) -> float:
        if not self._available or self._client is None:
            return 0.0
        val = await self._client.get(f"budget:consumed:{user_id}:{period}")
        return float(val) if val else 0.0

    async def get_frozen(self, user_id: int, period: str) -> float:
        if not self._available or self._client is None:
            return 0.0
        val = await self._client.get(f"budget:frozen:{user_id}:{period}")
        return float(val) if val else 0.0

    async def freeze(self, user_id: int, period: str, amount: float) -> float:
        if not self._available or self._client is None:
            return 0.0
        key = f"budget:frozen:{user_id}:{period}"

        result = await self._client.incrbyfloat(key, amount)
        return float(result)

    async def settle(
        self, user_id: int, period: str, frozen_amount: float, actual_cost: float
    ):
        """Atomic: unfreeze frozen_amount, deduct actual_cost from consumed.

        Returns (new_consumed, new_frozen).
        """
        if not self._available or self._client is None:
            return 0.0, 0.0

        pipe = self._client.pipeline()
        pipe.incrbyfloat(f"budget:frozen:{user_id}:{period}", -frozen_amount)
        pipe.incrbyfloat(f"budget:consumed:{user_id}:{period}", actual_cost)
        results = await pipe.execute()
        return float(results[1]), max(0.0, float(results[0]))

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
            self._available = False
