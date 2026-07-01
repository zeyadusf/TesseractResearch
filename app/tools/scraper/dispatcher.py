"""
app/tools/scraper/dispatcher.py
Scraper dispatcher with Redis-based usage tracking per provider.
"""

from app.core.logging import get_logger
from app.models.scraper_tool import ScrapeResult
from app.tools.scraper.base import BaseScraperProvider
from app.tools.scraper.providers.firecrawl_provider import FirecrawlProvider
from app.tools.scraper.providers.jina_provider import JinaProvider
from app.tools.scraper.providers.bs4_provider import BS4Provider
from app.tools.usage_tracker import ProviderUsageTracker


class ScraperDispatcher:
    """
    Dispatches scrape requests across providers based on Redis credit usage.

    Zones per provider:
        green  → use primary freely
        yellow → round-robin between primary and next fallback
        red    → skip to next provider immediately

    Firecrawl free tier: one-time 1000 credits, no monthly reset.
    Jina and BS4 are free — no tracker needed.
    """

    def __init__(self, firecrawl_limit: int = 1000):
        self.logger = get_logger(__name__)

        self._firecrawl :BaseScraperProvider = None
        self._jina :BaseScraperProvider = None
        self._bs4 :BaseScraperProvider = None

        self._firecrawl_tracker = ProviderUsageTracker(
            provider_name="firecrawl",
            monthly_limit=firecrawl_limit,
            reset_strategy="monthly",          # one-time lifetime credits
            soft_threshold_pct=0.8,
            hard_threshold_pct=0.95,
        )

        self._round_robin_toggle: bool = False

    async def _pick_provider(self) -> BaseScraperProvider:
        firecrawl_zone = await self._firecrawl_tracker.get_zone()

        if firecrawl_zone == "green":
            if self._firecrawl == None:self._firecrawl = FirecrawlProvider()
            return self._firecrawl

        if firecrawl_zone == "yellow":
            self._round_robin_toggle = not self._round_robin_toggle
            if self._round_robin_toggle:
                if self._firecrawl == None:self._firecrawl = FirecrawlProvider()
                return self._firecrawl
            # fall through to Jina

        # Firecrawl is red or lost round-robin — use Jina
        self.logger.warning(
            "Firecrawl limit reached — falling back to Jina"
        )
        if self._jina == None: self._jina = JinaProvider()

        return self._jina

    async def scrape(self, url: str) -> ScrapeResult:
        provider = await self._pick_provider()
        result = await provider.scrape(url)

        if not result.error:
            if isinstance(provider, FirecrawlProvider):
                await self._firecrawl_tracker.increment()
            return result

        # Provider failed — try next in chain
        self.logger.warning(
            f"[ScraperDispatcher] {provider.__class__.__name__} failed for url='{url}', "
            f"trying fallback chain..."
        )
        if self._bs4 == None : self._bs4 = BS4Provider()
        if self._jina == None : self._jina =JinaProvider()

        for fallback in [self._jina, self._bs4]:
            if fallback is provider:
                continue
            result = await fallback.scrape(url)
            if not result.error:
                return result

        self.logger.error(f"[ScraperDispatcher] All providers failed for url='{url}'.")
        return ScrapeResult.model_construct(url=url, markdown="", error="failed")

    async def aclose(self) -> None:
        await self._firecrawl_tracker.aclose()