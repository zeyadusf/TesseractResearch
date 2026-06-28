"""
app/tools/scraper/utils.py
Markdown post-processing utilities for scraped content.
"""

import re

from app.core.config import get_setting


def clean_markdown(markdown: str) -> str:
    """
    Strips images from markdown if STRIP_IMAGES=True in config.
    Set STRIP_IMAGES=False when using a multimodal model.
    """
    if not get_setting().STRIP_IMAGES:
        return markdown

    # Remove ![alt](url) syntax
    markdown = re.sub(r'!\[.*?\]\(.*?\)', '', markdown)
    # Remove <img ...> HTML tags
    markdown = re.sub(r'<img[^>]+>', '', markdown)

    return markdown.strip()


def truncate_markdown(markdown: str, max_chars: int) -> str:
    """
    Truncates markdown to max_chars.
    Cuts at the last newline before the limit to avoid breaking mid-sentence.

    Rule of thumb: 4 chars ≈ 1 token
    Default MAX_CHARS_PER_SOURCE=16000 ≈ 4K tokens per source
    5 sources × 16K = 80K chars ≈ 20K tokens for the analyzer
    """
    if len(markdown) <= max_chars:
        return markdown

    truncated = markdown[:max_chars]
    last_newline = truncated.rfind("\n")
    return truncated[:last_newline] if last_newline > 0 else truncated