"""
app/models/search_tool.py
Pydantic models for search tool results.
"""

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float
    provider:str


class SearchResults(BaseModel):
    results: list[SearchResult] = Field(default_factory=list)