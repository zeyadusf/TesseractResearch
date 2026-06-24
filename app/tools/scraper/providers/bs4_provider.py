"""
app/tools/scraper/providers/bs4.py
BeautifulSoup scraper provider — no API key, last resort.
Works on static pages only, no JavaScript rendering.
"""

import httpx
from bs4 import BeautifulSoup
from pydantic import ValidationError

from app.models.scraper_tool import ScrapeResult
from app.tools.scraper.base import BaseScraperProvider


class BS4Provider(BaseScraperProvider):

    def __init__(self):
        super().__init__()

    async def _scrape(self, url: str) -> ScrapeResult:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title else ""
        markdown = soup.get_text(separator="\n", strip=True)

        try:
            return ScrapeResult(url=url, markdown=markdown, title=title or None)
        except ValidationError:
            self.logger.exception(f"VALIDATION ERROR: markdown too short for url='{url}'")
            return ScrapeResult.model_construct(url=url, markdown="", error="failed")