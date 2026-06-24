"""
test_scrapers.py
Manual test for all scraper providers.
Saves markdown output to test_results/ directory.
Run from project root: python test_scrapers.py
"""

import asyncio
from pathlib import Path

from app.tools.scraper.providers.firecrawl_provider import FirecrawlProvider
from app.tools.scraper.providers.jina_provider import JinaProvider
from app.tools.scraper.providers.bs4_provider import BS4Provider

TEST_URL = "https://en.wikipedia.org/wiki/Graphics_processing_unit"
OUTPUT_DIR = Path("./test/test_results/scrapers")

PROVIDERS = [
    FirecrawlProvider(),
    JinaProvider(),
    BS4Provider(),
]


async def test_provider(provider, url: str):
    print("=" * 60)
    print(f"🚀 Testing Provider: {provider.__class__.__name__}")
    print(f"🔗 URL: {url}")
    print("=" * 60)

    result = await provider.scrape(url)

    if result.error:
        print(f"❌ FAILED: {result.error}")
    else:
        md_len = len(result.markdown) if result.markdown else 0
        preview = result.markdown[:300] if result.markdown else "(empty)"

        # Save to file
        output_file = OUTPUT_DIR / f"{provider.__class__.__name__.lower()}.md"
        output_file.write_text(
            f"# {provider.__class__.__name__}\n\n"
            f"**URL:** {result.url}\n"
            f"**Title:** {result.title}\n"
            f"**MD Length:** {md_len} chars\n\n"
            f"---\n\n"
            f"{result.markdown}",
            encoding="utf-8",
        )

        print(f"✅ SUCCESS")
        print(f"📄 Title   : {result.title}")
        print(f"📏 MD len  : {md_len} chars")
        print(f"💾 Saved to: {output_file}")
        print(f"\n--- Markdown preview ---\n{preview}\n...")

    print()


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for provider in PROVIDERS:
        await test_provider(provider, TEST_URL)


asyncio.run(main())