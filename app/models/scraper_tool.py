"""
app/models/scraper_tool.py
Pydantic models for scraper tool results.
"""

from pydantic import BaseModel,Field


class ScrapeResult(BaseModel):
    url: str
    markdown: str = Field(...,min_length=50)
    title: str | None = None
    error: str | None = None