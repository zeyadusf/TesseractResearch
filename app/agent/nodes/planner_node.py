from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.state import AgentState
from app.models.enums.nodes_prompt import Prompts 
from app.core.dependencies import get_llm_dispatcher

from app.core.logging import get_logger
logger = get_logger(__name__)



async def planner_node(state: AgentState) -> dict:
    logger.debug("planner_node | session=%s | query=%s", state["session_id"], state["user_query"])
    try:
        dispatcher = get_llm_dispatcher()
        llm = dispatcher.get_llm("planner")

        messages = [
            SystemMessage(content=Prompts.PLANNER),
            HumanMessage(content=f"Research query: {state['user_query']}"),
        ]
        response = await llm.ainvoke(messages)
        research_plan = response.content.strip()
        logger.info("planner_node | plan generated | length=%d chars", len(research_plan))
        return {
            "research_plan": research_plan,
            "current_step": "search",
        }
    except Exception as exc:
        logger.error("planner_node | error: %s", exc, exc_info=True)
        errors = list(state.get("errors") or [])
        errors.append(f"planner_node failed: {exc}")
        return {
            "research_plan": f"Research plan for: {state['user_query']}",
            "current_step": "search",
            "errors": errors,
        }