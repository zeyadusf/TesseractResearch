"""
app/agent/nodes/approval.py
Human-in-the-Loop approval node.
"""

from langgraph.types import interrupt
from typing import Literal

from app.agent.state import AgentState
from app.core.logging import get_logger

logger = get_logger(__name__)


async def approval_node(state: AgentState) -> dict:
    """
    Human-in-the-Loop node. Pauses graph execution and surfaces search results
    to the user. Resumes when POST /research/{id}/approve is called.

    interrupt() serializes the current state into the checkpoint and suspends
    the graph. When resumed via Command(resume=...), execution continues from
    the line after interrupt().
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

    # interrupt() suspends execution here.
    # Value passed in is returned to the API caller as the interrupt payload.
    # Graph resumes after this line once Command(resume="approved"|"rejected")
    # is sent via POST /research/{id}/approve.
    approval_response:  Literal["approved", "rejected"] = interrupt(
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

def route_after_approval(state: AgentState):
    if state["approval_response"] == "approved":
        return "approved"

    return "rejected"