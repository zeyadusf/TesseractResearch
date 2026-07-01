"""
app/agent/nodes/approval_node.py
Human-in-the-Loop approval node.
"""

from typing import Literal
from langgraph.types import interrupt
from app.agent.state import AgentState
from app.core.logging import get_logger

logger = get_logger(__name__)


async def approval_node(state: AgentState) -> dict:
    """
    Suspends graph execution via interrupt() and waits for human decision.
    Graph resumes when Command(resume="approved"|"rejected") is sent.
    interrupt() return value is the resume payload — no manual state tracking needed.
    """
    search_results = state.get("search_results")
    results = search_results.results if search_results else []

    logger.info(
        "approval_node | session=%s | pausing for HITL | results=%d",
        state["session_id"],
        len(results),
    )

    results_summary = [
        {"title": r.title, "url": r.url, "score": r.score}
        for r in results
    ]

    approval_response: Literal["approved", "rejected"] = interrupt(
        {
            "message": "Please review the search results and approve or reject.",
            "results": results_summary,
        }
    )

    logger.info(
        "approval_node | session=%s | resumed | response=%s",
        state["session_id"],
        approval_response,
    )

    return {
        "approval_required": False,
        "approval_response": approval_response,
        "current_step": "scrape",
    }


def route_after_approval(state: AgentState) -> Literal["approved", "rejected"]:
    return state["approval_response"]