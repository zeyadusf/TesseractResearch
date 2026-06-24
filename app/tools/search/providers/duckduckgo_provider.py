"""
app/tools/search/providers/duckduckgo_provider.py
DuckDuckGo provider — free, no API key, last resort fallback.
Uses asyncio.to_thread to run sync DDGS in async context.
Includes retry with exponential backoff for rate limit handling.
"""

import asyncio

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException

from app.models.search_tool import SearchResult, SearchResults
from app.tools.search.base import BaseSearchProvider


class DuckDuckGoProvider(BaseSearchProvider):

    def __init__(self):
        super().__init__()
        self.logger.debug("DuckDuckGo Search runing...")
    
    async def _search(self, query: str, max_results: int) -> SearchResults:
        def _run() -> list[dict]:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        raw = []
        for attempt in range(3):
            try:
                raw = await asyncio.to_thread(_run)
                break
            except DuckDuckGoSearchException as e:
                if attempt < 2:
                    wait = 2 ** attempt  # 1s → 2s
                    self.logger.warning(
                        f"[ Rate limited (attempt {attempt + 1}/3), "
                        f"retrying in {wait}s... error={e}"
                    )
                    await asyncio.sleep(wait)
                else:
                    self.logger.error(
                        f"[Rate limited after 3 attempts, giving up."
                    )
                    return SearchResults()

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                content=r.get("body", ""),
                score=0.0,
            )
            for r in raw
        ]

        return SearchResults(results=results)

    @property
    def is_returns_score(self) -> bool:
        return False
    


# # ── Manual test ──────────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     import json

#     async def _test():
#         provider = DuckDuckGoProvider()
#         results = await provider.search("GPU cloud providers")
#         print(json.dumps([r.model_dump() for r in results.results], indent=2))
#         print(f"\nTotal results: {len(results.results)}")

#     asyncio.run(_test())
    
if __name__ == "__main__":
    import asyncio

    async def main():

        provider = DuckDuckGoProvider()

        query = "GPU cloud providers"

        print("\n" + "=" * 60)
        print(f"🚀 Testing Provider: {provider.__class__.__name__}")
        print(f"🔎 Query: {query}")
        print("=" * 60 + "\n")

        results = await provider.search(query)

        if not results or not results.results:
            print("❌ No results returned")
            return

        print(f"✅ Total Results: {len(results.results)}\n")

        for i, r in enumerate(results.results, start=1):

            print("-" * 60)
            print(f"Result #{i}")
            print(f"Title: {getattr(r, 'title', 'N/A')}")
            print(f"URL:   {getattr(r, 'url', 'N/A')}")
            print(f"Score: {getattr(r, 'score', 'N/A')}")
            print(f"Source:{getattr(r, 'source', 'N/A')}")
            print("-" * 60 + "\n")

    asyncio.run(main())