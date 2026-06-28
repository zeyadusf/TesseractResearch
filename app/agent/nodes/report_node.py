from uuid import UUID

from langchain_core.messages import SystemMessage, HumanMessage

from app.models.enums.nodes_prompt import Prompts
from app.agent.state import AgentState
from app.core.dependencies import get_llm_dispatcher
from app.core.logging import get_logger

logger = get_logger(__name__)

def _build_sources_section(state: AgentState) -> str:
    """Format sources list from search results and scraped content."""
    lines: list[str] = []

    search_results = state.get("search_results")
    if search_results and search_results.results:
        for r in search_results.results:
            lines.append(f"- [{r.title}]({r.url})")

    return "\n".join(lines) if lines else "No sources available."


def _build_skipped_section(state: AgentState) -> str:
    """Extract skipped-URL notes from errors list."""
    errors = state.get("errors") or []
    skipped = [e for e in errors if "paywall" in e.lower() or "scrape failed" in e.lower()]
    if not skipped:
        return "None."
    return "\n".join(f"- {s}" for s in skipped)


async def report_node(state: AgentState) -> dict:
    logger.info("report_node | session=%s", state["session_id"])
    errors: list[str] = list(state.get("errors") or [])

    sources_text = _build_sources_section(state)
    skipped_text = _build_skipped_section(state)

    try:
        dispatcher = get_llm_dispatcher()
        llm = dispatcher.get_llm("report")
        messages = [
            SystemMessage(content=Prompts.REPORT),
            HumanMessage(
                content=(
                    f"User query: {state['user_query']}\n\n"
                    f"Analysis:\n{state.get('analysis', 'No analysis available.')}\n\n"
                    f"Sources consulted:\n{sources_text}\n\n"
                    f"Skipped sources:\n{skipped_text}"
                )
            ),
        ]
        response = await llm.ainvoke(messages)
        final_report = response.content.strip()
        logger.info("report_node | report generated | length=%d chars", len(final_report))
    except Exception as exc:
        logger.error("report_node | LLM error: %s", exc, exc_info=True)
        errors.append(f"report_node LLM failed: {exc}")
        # Fallback: assemble a basic report from analysis directly
        final_report = (
            f"# Research Report\n\n"
            f"**Query:** {state['user_query']}\n\n"
            f"## Analysis\n\n{state.get('analysis', 'No analysis available.')}\n\n"
            f"## Sources\n\n{sources_text}\n\n"
            f"## Notes\n\nSkipped sources:\n{skipped_text}"
        )

    return {
        "final_report": final_report,
        "current_step": "done",
        "status": "completed",
        "errors": errors,
    }

