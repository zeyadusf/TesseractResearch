"""
app/tools/search/providers/serper.py
Serper (Google Search) provider — fallback for Tavily.
"""


import httpx

from app.models.search_tool import SearchResult, SearchResults
from app.tools.search.base import BaseSearchProvider


class SerperProvider(BaseSearchProvider):

    SERPER_URL = "https://google.serper.dev/search"
    
    def __init__(self):
        super().__init__()
        self.logger.debug("Serper Search runing...")

    async def _search(self, query: str, max_results: int) -> SearchResults:
        api_key = self.config.SERPER_API_KEY
        if not api_key:
            raise ValueError("SERPER_API_KEY is not set.")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.SERPER_URL,
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": max_results},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                content=r.get("snippet", ""),
                score=0.0,  # Serper doesn't provide relevance scores
                provider="serper"

            )
            for r in data.get("organic", [])[:max_results]
        ]

        return SearchResults(results=results)
    
    @property
    def is_returns_score(self) -> bool:
        return False
    

if __name__ == "__main__":
    import asyncio

    async def main():

        provider = SerperProvider()

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
            print(f"Provider:{getattr(r, 'provider', 'N/A')} ")
            print("-" * 60 + "\n")

    asyncio.run(main())