"""
test_search.py
Manual test for all search providers.
Saves results output to test_results/search/ directory.
Run from project root: python test_search.py
"""

import asyncio
import json
from pathlib import Path

from app.tools.search.providers.tavily_provider import TavilyProvider
from app.tools.search.providers.serper_provider import SerperProvider

TEST_QUERY = "GPU cloud providers"
OUTPUT_DIR = Path("./test/test_results/search")

PROVIDERS = [
    TavilyProvider(),
    SerperProvider(),
]


async def test_provider(provider, query: str):
    print("=" * 60)
    print(f"🚀 Testing Provider: {provider.__class__.__name__}")
    print(f"🔎 Query: {query}")
    print("=" * 60)

    results = await provider.search(query)

    if not results.results:
        print("❌ No results returned")
    else:
        # Save to markdown file
        output_file = OUTPUT_DIR / f"{provider.__class__.__name__.lower()}.md"
        lines = [
            f"# {provider.__class__.__name__}\n",
            f"**Query:** {query}\n",
            f"**Total Results:** {len(results.results)}\n\n",
            "---\n\n",
        ]
        for i, r in enumerate(results.results, 1):
            lines.append(f"## {i}. {r.title}\n")
            lines.append(f"- **URL:** {r.url}\n")
            lines.append(f"- **Score:** {r.score}\n")
            lines.append(f"- **Snippet:** {r.content}\n\n")

        output_file.write_text("".join(lines), encoding="utf-8")

        print(f"✅ SUCCESS — {len(results.results)} results")
        print(f"💾 Saved to: {output_file}\n")

        for i, r in enumerate(results.results, 1):
            print(f"  {i}. {r.title}")
            print(f"     URL    : {r.url}")
            print(f"     Score  : {r.score}")
            print(f"     Snippet: {r.content[:100]}...")
            print()

    print()


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for provider in PROVIDERS:
        await test_provider(provider, TEST_QUERY)


asyncio.run(main())