"""
app/agent/nodes/scraper.py
Scraper node — fetches and cleans content from approved search result URLs.
"""

import re

from app.agent.state import AgentState
from app.core.config import get_setting
from app.core.dependencies import get_scraper_dispatcher
from app.core.logging import get_logger
from app.models.scraper_tool import ScrapeResult
from app.tools.scraper.utils import clean_markdown, truncate_markdown

logger = get_logger(__name__)

# Keywords that indicate a page is paywalled or requires login.
# Checked against the first 2000 chars of returned markdown (case-insensitive).
_PAYWALL_PATTERNS: list[re.Pattern] = [
    re.compile(r, re.IGNORECASE)
    for r in [
        r"subscribe\s+to\s+(read|continue|access)",
        r"this\s+content\s+is\s+(only\s+)?available\s+to\s+(subscribers|members)",
        r"create\s+a\s+free\s+account\s+to\s+(read|continue)",
        r"sign\s+in\s+to\s+(read|continue|access)",
        r"you\s+have\s+reached\s+your\s+(free\s+)?article\s+limit",
        r"already\s+a\s+subscriber\?",
        r"paywall",
        r"register\s+to\s+read",
    ]
]


def _is_paywalled(markdown: str) -> bool:
    sample = markdown[:2000]
    return any(p.search(sample) for p in _PAYWALL_PATTERNS)


async def scraper_node(state: AgentState) -> dict:
    logger.info("scraper_node | session=%s", state["session_id"])

    search_results = state.get("search_results")
    if not search_results or not search_results.results:
        logger.warning("scraper_node | no search results to scrape")
        return {"scraped_content": [], "current_step": "analyze"}

    dispatcher = get_scraper_dispatcher()
    target = get_setting().SCRAPER_TARGET_SOURCES
    max_chars = get_setting().MAX_CHARS_PER_SOURCE
    errors: list[str] = list(state.get("errors") or [])
    valid_results: list[ScrapeResult] = []
    skipped_urls: list[str] = []

    urls = [r.url for r in search_results.results]
    logger.info("scraper_node | urls to attempt=%d | target=%d", len(urls), target)

    for url in urls:
        if len(valid_results) >= target:
            logger.info("scraper_node | target reached (%d sources), stopping early", target)
            break

        logger.info("scraper_node | scraping %s", url)
        result: ScrapeResult = await dispatcher.scrape(url)

        # Skip failed scrapes
        if result.error:
            logger.warning("scraper_node | scrape failed | url=%s | error=%s", url, result.error)
            skipped_urls.append(url)
            errors.append(f"scrape failed [{url}]: {result.error}")
            continue

        # Skip paywalled content
        if _is_paywalled(result.markdown):
            logger.warning("scraper_node | paywall detected | url=%s", url)
            skipped_urls.append(url)
            errors.append(f"paywall detected, skipped: {url}")
            continue

        # Clean markdown (strip images if configured) then truncate
        cleaned_markdown = clean_markdown(result.markdown)
        cleaned_markdown = truncate_markdown(cleaned_markdown, max_chars)

        valid_result = result.model_copy(update={"markdown": cleaned_markdown})
        valid_results.append(valid_result)
        logger.info(
            "scraper_node | accepted | url=%s | chars=%d",
            url,
            len(cleaned_markdown),
        )

    if skipped_urls:
        logger.info("scraper_node | skipped %d urls", len(skipped_urls))

    logger.info("scraper_node | valid sources collected=%d", len(valid_results))
    return {
        "scraped_content": valid_results,
        "current_step": "analyze",
        "errors": errors,
    }