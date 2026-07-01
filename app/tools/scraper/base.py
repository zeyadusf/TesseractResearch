"""
app/tools/scraper/providers/base.py
Abstract base class for all scraper providers.
"""

from abc import ABC, abstractmethod
from langsmith import traceable

from app.models.scraper_tool import ScrapeResult
from app.core.config import get_setting
from app.core.logging import get_logger

class BaseScraperProvider(ABC):

    def __init__(self):
        self.logger = get_logger(self.__class__.__module__)
        self.config = get_setting()
    
    @traceable(name="scraper", run_type="tool")
    async def scrape(self, url: str) -> ScrapeResult:
        """
        Public method — handles logging and error handling.
        Subclasses implement _scrape() only.
        """
        try:
            result = await self._scrape(url)
            if result.error:
                self.logger.error(f"FAILED url='{url}': {result.error}")
            else:
                self.logger.info(f"url='{url}' → {len(result.markdown or '')} chars")
            return result
        except Exception as e:
            self.logger.exception(f"ERROR url='{url}': e => {e}")
            return ScrapeResult.model_construct(url=url, markdown="", error="failed")

    @abstractmethod
    async def _scrape(self, url: str) -> ScrapeResult:
        """Core scrape logic — implement per provider."""
        ...