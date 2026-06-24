"""
app/tools/search/providers/tavily.py
Tavily search provider.
"""
from tavily import AsyncTavilyClient

from app.models.search_tool import SearchResult, SearchResults
from app.tools.search.base import BaseSearchProvider


class TavilyProvider(BaseSearchProvider):

    def __init__(self):
        super().__init__()
        self.logger.debug("Tavily Search running...")

    async def _search(self, query: str, max_results: int) -> SearchResults:
        
        api_key = self.config.TAVILY_API_KEY

        if not api_key:
            raise ValueError("TAVILY_API_KEY is not set.")

        client = AsyncTavilyClient(api_key=api_key)
        
        response = await client.search(
            query=query,
            max_results=max_results,
            include_answer=False,
            include_raw_content=False,
        )

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                score=r.get("score", 0.0),
                provider="tavily"
            )
            for r in response.get("results", [])
        ]

        return SearchResults(results=results)
    
    @property
    def is_returns_score(self) -> bool:
        return True
    


if __name__ == "__main__":
    import asyncio

    async def main():

        provider = TavilyProvider()

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