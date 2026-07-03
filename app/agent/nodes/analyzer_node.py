from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.state import AgentState
from app.core.dependencies import get_llm_dispatcher
from app.core.config import get_setting
from app.core.logging import get_logger
from app.models.enums.nodes_prompt import Prompts
logger = get_logger(__name__)
config = get_setting()

# Max chars to include from each source to avoid exceeding context window.
# llama-3.1-8b-instant context: 128k tokens ≈ 500k chars total budget.
# With up to 5 sources: 60k chars each leaves comfortable headroom.


async def analyzer_node(state: AgentState) -> dict:
    logger.info("analyzer_node | session=%s", state["session_id"])
    errors: list[str] = list(state.get("errors") or [])

    scraped_content = state.get("scraped_content") or []
    if not scraped_content:
        logger.warning("analyzer_node | no scraped content available")
        return {
            "analysis": "",
            "analysis_failed": True,
            "current_step": "report",
            "errors": errors,
        }

    # Build context block for the LLM
    context_parts: list[str] = []
    for i, result in enumerate(scraped_content, start=1):
        truncated = result.markdown[:config.MAX_CHARS_PER_SOURCE]
        source_block = (
            f"--- SOURCE {i}: {result.title or result.url} ---\n"
            f"URL: {result.url}\n"
            f"{truncated}\n"
        )
        context_parts.append(source_block)

    context = "\n".join(context_parts)
    total_chars = len(context)
    logger.info(
        "analyzer_node | sources=%d | context_chars=%d",
        len(scraped_content),
        total_chars,
    )

    try:
        dispatcher = get_llm_dispatcher()
        messages = [
            SystemMessage(content=Prompts.ANALYZER),
            HumanMessage(
                content=(
                    f"Research query: {state['user_query']}\n\n"
                    f"Research plan:\n{state.get('research_plan', '')}\n\n"
                    f"Scraped content from {len(scraped_content)} sources:\n\n"
                    f"{context}"
                )
            ),
        ]
        # ainvoke_with_fallback retries the same messages on the fallback
        # provider if the primary raises at call time (rate limit, quota,
        # 4xx/5xx) — unlike get_llm(), which only guards construction and
        # never catches runtime failures.
        analysis = await dispatcher.ainvoke_with_fallback("analyzer", messages)
        logger.info("analyzer_node | analysis generated | length=%d chars", len(analysis))
        return {
            "analysis": analysis,
            "analysis_failed": False,
            "current_step": "report",
            "errors": errors,
        }
    except Exception as exc:
        logger.error("analyzer_node | error: %s", exc, exc_info=True)
        errors.append(f"analyzer_node failed: {exc}")
        # NOTE: no fake "Analysis could not be generated..." string here.
        # report_node checks `analysis_failed` explicitly and falls back to
        # raw scraped_content instead of building a prompt around this text.
        # Reaching this block means BOTH primary and fallback already failed.
        return {
            "analysis": "",
            "analysis_failed": True,
            "current_step": "report",
            "errors": errors,
        }