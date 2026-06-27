import re

from app.core.config import get_setting


def clean_markdown(markdown: str) -> str:
    """
    Post-process scraped markdown content.

    When STRIP_IMAGES=True (default):
      - Removes inline markdown images: ![alt](url)
      - Removes HTML img tags: <img ...>

    When STRIP_IMAGES=False (multimodal model):
      - Returns markdown unchanged.

    This utility is called in scraper_node on every accepted ScrapeResult
    before it enters the agent state.
    """
    if not get_setting().STRIP_IMAGES:
        return markdown

    # Remove markdown image syntax: ![alt text](url)
    markdown = re.sub(r'!\[.*?\]\(.*?\)', '', markdown)
    # Remove HTML img tags: <img src="..." alt="..." />
    markdown = re.sub(r'<img[^>]+>', '', markdown)

    return markdown.strip()