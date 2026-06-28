
from app.agent.state import AgentState
from app.core.config import get_setting
from app.core.dependencies import get_search_dispatcher
from app.core.logging import get_logger
from app.models.search_tool import SearchResults

logger = get_logger(__name__)


async def search_node(state: AgentState) -> dict:
    try:
        dispatcher =  get_search_dispatcher()
        max_results = get_setting().SEARCH_MAX_RESULTS

        # Use user_query directly — research_plan is context for the agent,
        # not a search string. We derive a focused query from the plan.
        query = state["user_query"]
        logger.info("search_node | session=%s | query=%s | max_results=%d",
                                state["session_id"], query, max_results)

        search_results: SearchResults = await dispatcher.search(query, max_results=max_results)
        logger.debug("search_node | results=%d", len(search_results.results))

        return {
            "search_results": search_results,
            "current_step": "approval",
        }
    except Exception as exc:
        logger.error("search_node | error: %s", exc, exc_info=True)
        errors = list(state.get("errors") or [])
        errors.append(f"search_node failed: {exc}")
        return {
            "search_results": SearchResults(),
            "current_step": "approval",
            "errors": errors,
        }