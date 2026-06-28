from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.nodes import (
    planner_node,
    search_node,
    approval_node,
    route_after_approval,
    scraper_node,
    analyzer_node,
    report_node,
)
from app.agent.checkpoint_memory import get_checkpointer
from app.core.logging import get_logger

logger = get_logger(__name__)


async def build_graph():
    """
    Build and compile the TesseractResearch agent graph.

    Graph flow:
        START → planner → search → approval (HITL interrupt) → scraper → analyzer → report → END

    Returns a compiled LangGraph CompiledStateGraph with AsyncPostgresSaver checkpointing.
    The checkpointer enables:
      - State persistence across process restarts
      - HITL: graph suspends at approval_node, state is saved, resumes on resume command
      - Session isolation via thread_id = session_id
    """
    checkpointer = await get_checkpointer()

    # Create checkpoint tables if they don't exist yet (idempotent)
    await checkpointer.setup()
    logger.info("build_graph | checkpoint tables ready")

    builder = StateGraph(AgentState)

    
    # Register all nodes
    builder.add_node("planner", planner_node)
    builder.add_node("search", search_node)
    builder.add_node("approval", approval_node)
    builder.add_node("scraper", scraper_node)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("report", report_node)

    # Wire the edges 
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "search")
    builder.add_edge("search", "approval")

    builder.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "approved": "scraper",
            "rejected": END,
        },
    )

    builder.add_edge("scraper", "analyzer")
    builder.add_edge("analyzer", "report")
    builder.add_edge("report", END)

    graph = builder.compile(checkpointer=checkpointer)

    graph = builder.compile(checkpointer=checkpointer, interrupt_before=["approval"])

    logger.info("build_graph | graph compiled successfully")
    return graph