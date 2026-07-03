import re

from langchain_core.messages import SystemMessage, HumanMessage

from app.models.enums.nodes_prompt import Prompts
from app.agent.state import AgentState
from app.core.dependencies import get_llm_dispatcher
from app.core.logging import get_logger

logger = get_logger(__name__)

# Char budget per source when falling back to raw content (analyzer failed).
# Smaller than analyzer_node's MAX_CHARS_PER_SOURCE since this content goes
# straight into the report prompt unsummarized, alongside report instructions.
FALLBACK_MAX_CHARS_PER_SOURCE = 4500


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


def _extract_priority_content(markdown: str, budget: int) -> str:
    """
    Naive [:budget] truncation cuts off code blocks that appear after long
    preambles (common in dev blogs/docs). Keep every fenced code block intact
    regardless of position, then fill remaining budget with prose — so the
    model actually sees API/pattern specifics instead of just the intro.
    """
    code_blocks = re.findall(r"```[\s\S]*?```", markdown or "")
    code_text = "\n\n".join(code_blocks)
    remaining_budget = max(budget - len(code_text), 500)
    prose = re.sub(r"```[\s\S]*?```", "", markdown or "")[:remaining_budget]
    if code_text:
        return f"{prose}\n\n[CODE/CONFIG EXAMPLES FROM THIS SOURCE]\n{code_text}"
    return prose


def _build_raw_source_dump(state: AgentState) -> str:
    """Used only when analysis_failed=True — raw scraped_content, code-priority trimmed."""
    scraped_content = state.get("scraped_content") or []
    if not scraped_content:
        return "No scraped content available."
    parts = []
    for i, result in enumerate(scraped_content, start=1):
        content = _extract_priority_content(result.markdown, FALLBACK_MAX_CHARS_PER_SOURCE)
        parts.append(f"--- SOURCE {i}: {result.title or result.url} ---\nURL: {result.url}\n{content}")
    return "\n\n".join(parts)


async def report_node(state: AgentState) -> dict:
    logger.info("report_node | session=%s", state["session_id"])
    errors: list[str] = list(state.get("errors") or [])

    sources_text = _build_sources_section(state)
    skipped_text = _build_skipped_section(state)
    analysis_failed = state.get("analysis_failed", False) or not state.get("analysis")

    if analysis_failed:
        logger.warning("report_node | analysis missing/failed — using raw scraped_content fallback")
        analysis_block = (
            "NOTE: Structured analysis generation FAILED for this run. You must do BOTH "
            "the analysis (cross-referencing raw sources for concrete facts, code, and "
            "specific mechanisms) AND the report writing yourself from the RAW SCRAPED "
            "SOURCE CONTENT below. Every pattern name you use must be one a source "
            "actually describes — do NOT infer a pattern name from a title/headline alone. "
            "State in the report's Notes section that analysis generation failed and this "
            "report was built directly from raw sources.\n\n"
            f"RAW SCRAPED SOURCE CONTENT:\n{_build_raw_source_dump(state)}"
        )
    else:
        analysis_block = state["analysis"]

    try:
        dispatcher = get_llm_dispatcher()
        # Heavier combined task (analysis + writing) needs the stronger
        # "analyzer" tier model, not the lighter "report" model, when the
        # analyzer itself already failed.
        llm = dispatcher.get_llm("report")
        messages = [
            SystemMessage(content=Prompts.REPORT),
            HumanMessage(
                content=(
                    f"User query: {state['user_query']}\n\n"
                    f"Analysis:\n{analysis_block}\n\n"
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
        # Fallback: assemble a basic report from whatever we have directly
        final_report = (
            f"# Research Report\n\n"
            f"**Query:** {state['user_query']}\n\n"
            f"## Analysis\n\n{state.get('analysis') or 'No analysis available — generation failed.'}\n\n"
            f"## Sources\n\n{sources_text}\n\n"
            f"## Notes\n\nReport generation also failed; this is a minimal fallback.\n"
            f"Skipped sources:\n{skipped_text}"
        )

    return {
        "final_report": final_report,
        "current_step": "done",
        "status": "completed",
        "errors": errors,
    }