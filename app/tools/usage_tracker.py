"""
app/tools/usage_tracker.py
Redis-based usage tracker for API providers with monthly and one-time reset strategies.
"""

from datetime import datetime, timezone
from typing import Literal

import redis.asyncio as aioredis

from app.core.config import get_setting
from app.core.logging import get_logger

config = get_setting()
ResetStrategy = Literal["monthly", "none"]


class ProviderUsageTracker:
    """
    Tracks API credit usage per provider in Redis.

    Reset strategies:
        - "monthly" : resets on the 1st of each month (Tavily, Serper)
        - "none"    : never resets — one-time lifetime credits (Firecrawl free tier)
    """

    def __init__(
        self,
        provider_name: str,
        monthly_limit: int,
        reset_strategy: ResetStrategy,
        soft_threshold_pct: float = 0.8,
        hard_threshold_pct: float = 0.95,
    ):
        self.provider_name = provider_name
        self.monthly_limit = monthly_limit
        self.reset_strategy = reset_strategy
        self.soft_threshold = int(monthly_limit * soft_threshold_pct)
        self.hard_threshold = int(monthly_limit * hard_threshold_pct)

        self._redis = aioredis.from_url(config.REDIS_URL,
                                            decode_responses=True,
                                            ssl_cert_reqs=None,  )
        
        self.logger = get_logger(f"UsageTracker.{provider_name}")

        # Redis keys
        self._count_key = f"{provider_name.lower()}:credit_count"
        self._reset_key = f"{provider_name.lower()}:last_reset_month"

    def _current_month(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    async def _check_monthly_reset(self) -> None:
        """Reset counter if we're in a new month (monthly strategy only)."""
        if self.reset_strategy != "monthly":
            return

        current_month = self._current_month()
        last_reset = await self._redis.get(self._reset_key)

        if last_reset != current_month:
            self.logger.info(
                f"[{self.provider_name}] Monthly reset triggered "
                f"(last={last_reset}, current={current_month})"
            )
            await self._redis.set(self._count_key, 0)
            await self._redis.set(self._reset_key, current_month)

    async def get_count(self) -> int:
        await self._check_monthly_reset()
        count = await self._redis.get(self._count_key)
        return int(count) if count else 0

    async def increment(self) -> int:
        count = await self._redis.incr(self._count_key)
        remaining = self.monthly_limit - count
        self.logger.debug(
            f"[{self.provider_name}] credits used: {count}/{self.monthly_limit} "
            f"(remaining: {remaining})"
        )
        return count

    async def get_zone(self) -> Literal["green", "yellow", "red"]:
        """
        Returns the current usage zone:
            green  → below soft threshold  → use primary freely
            yellow → soft to hard          → round-robin with fallback
            red    → above hard threshold  → skip to fallback immediately
        """
        count = await self.get_count()

        if count >= self.hard_threshold:
            self.logger.warning(
                f"[{self.provider_name}] RED zone "
                f"({count}/{self.monthly_limit}) — switching to fallback"
            )
            return "red"

        if count >= self.soft_threshold:
            self.logger.warning(
                f"[{self.provider_name}] YELLOW zone "
                f"({count}/{self.monthly_limit}) — round-robin active"
            )
            return "yellow"

        return "green"

    async def aclose(self) -> None:
        await self._redis.aclose()