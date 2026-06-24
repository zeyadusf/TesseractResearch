"""
app/tools/search/providers/base.py
Abstract base class for all search providers.
"""
from app.core.logging import get_logger
from app.core.config import get_setting

from abc import ABC, abstractmethod
from app.models.search_tool import SearchResults


class BaseSearchProvider(ABC):

    def __init__(self):
        self.logger = get_logger(self.__class__.__module__)
        self.config = get_setting()

    @abstractmethod
    async def _search(self, query: str, max_results: int) -> SearchResults:
        """Core search logic — implement per provider."""
        ...

    @property
    @abstractmethod
    def is_returns_score(self) -> bool:
        pass

    async def search(self, query: str, max_results: int = 5) -> SearchResults:
        """
        Public method — handles logging and error handling.
        Subclasses implement _search() only.
        """
        
        try:
            results = await self._search(query, max_results)
            self.logger.info(f"query={query} -> {len(results.results)} results")
            return results
        
        except Exception as e:
            self.logger.exception(f"Search failed | query='{query}': exception -> {e}")
            return SearchResults()
        
    