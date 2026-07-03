"""
app/agent/state.py
"""
from typing import TypedDict

from app.models.enums.session_status import SessionStatus
from app.models.scraper_tool import ScrapeResult
from app.models.search_tool import SearchResults


class AgentState(TypedDict):
    #   Core inputs
    session_id: str
    user_query: str

    #  Planning
    research_plan: str
    current_step: str

    #   Search & Scrape                            
    search_results: SearchResults
    scraped_content: list[ScrapeResult]

    #   HITL Approval
    approval_required: bool
    # "approved" | "partial:{url},{url}" | "rejected"
    approval_response: str | None

    #   Analysis & Report
    analysis: str
    analysis_failed: bool 
    final_report: str          

    #   Meta
    errors: list[str]
    status: SessionStatus