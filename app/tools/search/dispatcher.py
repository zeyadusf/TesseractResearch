"""
app/tools/search/dispatcher.py
Search dispatcher with Redis-based usage tracking per provider.
"""

from app.core.logging import get_logger
from app.core.config import get_setting
from app.models.search_tool import SearchResults
from app.tools.search.base import BaseSearchProvider
from app.tools.search.providers.tavily_provider import TavilyProvider
from app.tools.search.providers.serper_provider import SerperProvider
from app.tools.search.providers.duckduckgo_provider import DuckDuckGoProvider
from app.tools.usage_tracker import ProviderUsageTracker

config = get_setting()
class SearchDispatcher:
    """
    Dispatches search requests across providers based on Redis credit usage.

    Zones per provider:
        green  → use primary freely
        yellow → round-robin between primary and next fallback
        red    → skip to next provider immediately

    DuckDuckGo is always last resort — free, no credits, no tracker.
    """

    def __init__(
        self,
        tavily_limit: int = 1000,
        serper_limit: int = 2500,
    ):
        self.logger = get_logger(__name__)

        self._trackers = {
            "tavily":ProviderUsageTracker(
            provider_name="tavily",
            monthly_limit=tavily_limit,
            reset_strategy="monthly",
            soft_threshold_pct=1.0,
            hard_threshold_pct=1.0,
        ),
            "serper":ProviderUsageTracker(
            provider_name="serper",
            monthly_limit=serper_limit,
            reset_strategy="monthly",
            soft_threshold_pct=0.4,
            hard_threshold_pct=0.65,
        ),
        }

        self._providers = {
            'tavily' : TavilyProvider(),
            'serper' : SerperProvider(),
            'ddg'    : DuckDuckGoProvider(),
        }

    async def _pick_provider(self) -> BaseSearchProvider:
        tavily_zone = await self._trackers['tavily'].get_zone()
    
        if tavily_zone != "red":
            return self._providers['tavily']

        # Tavily is red — check Serper
        serper_zone = await self._trackers['serper'].get_zone()

        if serper_zone in ("green", "yellow"):
            return self._providers['serper']

        # Both exhausted — fall to free DDG
        self.logger.warning(
            "Both Tavily and Serper exhausted — falling back to DuckDuckGo"
        )
        return self._providers['ddg']

    async def search(self, query: str, max_results: int = config.SEARCH_MAX_RESULTS) -> SearchResults:
        provider = await self._pick_provider()
        results = await provider.search(query, max_results)

        if results.results:
            # Only increment after a successful call
            if isinstance(provider, TavilyProvider):
                await self._trackers['tavily'].increment()
            elif isinstance(provider, SerperProvider):
                await self._trackers['serper'].increment()
            return results

        # Provider returned empty — try next in chain
        self.logger.warning(
            f"[SearchDispatcher] {provider.__class__.__name__} returned empty, trying fallback chain..."
        )

        for fallback in [self._providers["serper"],self._providers["ddg"]]:
            if fallback is provider:
                continue
            results = await fallback.search(query, max_results)
            if results.results:
                if isinstance(fallback, SerperProvider):
                    await self._trackers['serper'].increment()
                return results

        self.logger.error("[SearchDispatcher] All providers failed.")
        return SearchResults()

    async def aclose(self) -> None:
        await self._trackers['tavily'].aclose()
        await self._trackers['serper'].aclose()