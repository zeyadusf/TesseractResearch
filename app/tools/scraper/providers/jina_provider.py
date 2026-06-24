"""
app/tools/scraper/providers/jina.py
Jina Reader scraper provider — no API key needed.
Returns markdown via simple HTTP GET to r.jina.ai/{url}.

- limit -> 500 ReqPerMin, trade off  avg latency 7.9s  
"""

import httpx
from pydantic import ValidationError

from app.models.scraper_tool import ScrapeResult
from app.tools.scraper.base import BaseScraperProvider


class JinaProvider(BaseScraperProvider):

    JINA_BASE = "https://r.jina.ai/"
    def __init__(self):
        super().__init__()
    
    async def _scrape(self, url: str) -> ScrapeResult:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.JINA_BASE}{url}",
                headers={"Accept": "text/markdown"},
                timeout=15.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            markdown = response.text

        try:
            return ScrapeResult(url=url, markdown=markdown)
        except ValidationError:
            self.logger.exception(f"VALIDATION ERROR: markdown too short for url='{url}'")
            return ScrapeResult.model_construct(url=url, markdown="", error="failed")