"""
app/tools/scraper/providers/firecrawl.py
Firecrawl scraper provider.
"""

from firecrawl import AsyncFirecrawlApp
from pydantic import ValidationError

from app.models.scraper_tool import ScrapeResult
from app.tools.scraper.base import BaseScraperProvider


class FirecrawlProvider(BaseScraperProvider):

    def __init__(self):
        super().__init__()

    async def _scrape(self, url: str) -> ScrapeResult:
        api_key = self.config.FIRECRAWL_API_KEY
        if not api_key:
            raise ValueError("FIRECRAWL_API_KEY is not set.")

        app = AsyncFirecrawlApp(api_key=api_key)
        response = await app.scrape_url(url=url, formats=["markdown"])

        metadata = getattr(response, "metadata", {}) or {}
        title = metadata.get("title", "") or metadata.get("ogTitle", "")

        try:
            return ScrapeResult(
                url=url,
                markdown=getattr(response, "markdown", ""),
                title=title or None,
            )
        except ValidationError:
            self.logger.exception(f"VALIDATION ERROR: markdown too short for url='{url}'")
            return ScrapeResult.model_construct(url=url, markdown="", error="failed")