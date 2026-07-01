"""
app/agent/graph.py

Builds and compiles the TesseractResearch LangGraph agent.

Graph flow:
    START → planner → search → approval (HITL interrupt) → scraper → analyzer → report → END

Notes:
  - Checkpointer is injected from main.py lifespan — never opened here.
  - build_graph() returns only the compiled graph; checkpointer lifetime
    is managed entirely by the caller (lifespan startup/shutdown).
"""

from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    analyzer_node,
    approval_node,
    planner_node,
    report_node,
    route_after_approval,
    scraper_node,
    search_node,
)
from app.agent.state import AgentState
from app.core.logging import get_logger

logger = get_logger(__name__)


async def build_graph(checkpointer: AsyncPostgresSaver):
    """
    Build and compile the TesseractResearch agent graph.

    Parameters
    ----------
    checkpointer:
        Open AsyncPostgresSaver instance — injected from lifespan startup.
        Caller owns the connection lifetime.

    Returns
    -------
    CompiledStateGraph
        Ready-to-use graph with checkpointing enabled.
    """
    builder = StateGraph(AgentState)

    # ── Nodes ──────────────────────────────────────────────────────────────
    builder.add_node("planner",  planner_node)
    builder.add_node("search",   search_node)
    builder.add_node("approval", approval_node)
    builder.add_node("scraper",  scraper_node)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("report",   report_node)

    # ── Edges ──────────────────────────────────────────────────────────────
    builder.add_edge(START,     "planner")
    builder.add_edge("planner", "search")
    builder.add_edge("search",  "approval")

    builder.add_conditional_edges(
        "approval",
        route_after_approval,
        {"approved": "scraper", "rejected": END},
    )

    builder.add_edge("scraper",  "analyzer")
    builder.add_edge("analyzer", "report")
    builder.add_edge("report",   END)

    # ── Compile ────────────────────────────────────────────────────────────
    graph = builder.compile(checkpointer=checkpointer)
    logger.info("build_graph | graph compiled successfully")
    return graph