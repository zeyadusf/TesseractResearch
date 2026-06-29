"""
app/service/research_service.py

Orchestrates all research session lifecycle:
  - start_research()  → creates DB session, runs graph, saves report
  - approve()         → resumes HITL interrupt via Command
  - get_state()       → reads current LangGraph checkpoint state
  - get_report()      → fetches persisted report from DB
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

from langgraph.types import Command

from app.agent.state import AgentState

from app.core.config import get_setting
from app.core.logging import get_logger

from app.db.connection import SessionLocal
from app.db.repositories.research_sessions import SessionRepository

from app.models.enums.session_status import SessionStatus

from app.service.report_service import ReportService

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

settings = get_setting()
logger = get_logger(__name__)


class ResearchService:
    """
    Single entry point for all research session operations.

    The compiled graph is injected at construction time (stored on app.state
    during lifespan startup) so every request shares the same checkpointer
    connection pool.
    """

    def __init__(self, graph: "CompiledStateGraph") -> None:
        self._graph = graph
        self._report_service = ReportService()

# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

    async def start_research(self, query: str) -> str:
        """
        1. Persist a new session row → obtain session_id (thread_id).
        2. Fire the graph asynchronously (non-blocking for the HTTP response).
        3. Graph runs planner → search → pauses at approval interrupt.
        4. Caller gets session_id immediately; client polls /events for progress.

        Returns
        -------
        str
            The session_id (UUID string) that acts as LangGraph thread_id.
        """
        session_id = await self._create_session(query)
        initial_state: AgentState = {
            "session_id": session_id,
            "user_query": query,
            "research_plan": "",
            "current_step": "planner",
            "search_results": None,          # type: ignore[typeddict-item]
            "scraped_content": [],
            "approval_required": False,
            "approval_response": None,
            "analysis": "",
            "final_report": "",
            "errors": [],
            "status": SessionStatus.RUNNING,
        }
        # Run in background — HTTP returns immediately with session_id.
        # The graph suspends itself at the approval interrupt; client resumes
        # via POST /research/{id}/approve when ready.
        asyncio.create_task(
            self._run_graph(session_id, initial_state),
            name=f"research-{session_id}",
        )
        logger.info("Research session started", extra={"session_id": session_id})
        return session_id

    async def approve(self, session_id: str, approved: bool) -> None:
        """
        Resume the graph after the HITL interrupt.

        Parameters
        ----------
        session_id:
            Must match an existing thread_id in the checkpointer.
        approved:
            True  → resume="approved"
            False → resume="rejected"
        """
        decision = "approved" if approved else "rejected"
        config = {"configurable": {"thread_id": session_id}}

        logger.info(
            "Resuming graph after HITL",
            extra={"session_id": session_id, "decision": decision},
        )
        # Fire the continuation in a background task so the HTTP 200 returns
        # immediately.  The graph will run scraper → analyzer → report and
        # then call _finalize().
        asyncio.create_task(
            self._resume_graph(session_id, decision, config),
            name=f"approve-{session_id}",
        )

    async def get_state(self, session_id: str) -> dict[str, Any]:
        """
        Return the current LangGraph checkpoint values for the session.

        Raises
        ------
        ValueError
            If no checkpoint exists for this session_id (unknown session).
        """
        config = {"configurable": {"thread_id": session_id}}
        snapshot = await self._graph.aget_state(config)
        if snapshot is None:
            raise ValueError(f"No state found for session_id={session_id!r}")
        return dict(snapshot.values)

# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

    async def _create_session(self, query: str) -> str:
        """Insert a new session row and return its UUID string."""
        async with SessionLocal() as db:
            repo = SessionRepository(db)
            session = await repo.create(query)
            return str(session.id)

# TODO: In a future version (after adding an evaluator and conditional nodes), this logic may need to be updated to validate the status.
    async def _run_graph(self, session_id: str, initial_state: AgentState) -> None:
        """
        Execute the graph from START.

        The graph will pause at the approval interrupt; _resume_graph() picks
        it up afterward.  If the graph raises before the interrupt (e.g. search
        failure) we mark the session as failed.
        """
        config = {"configurable": {"thread_id": session_id}}
        try:
            result: AgentState = await self._graph.ainvoke(initial_state, config=config)
            # Graph only reaches here if it runs to END without an interrupt.
            # Normal flow: graph pauses at approval, so this branch fires only
            # when approval is skipped (unlikely with interrupt_before=["approval"]).
            # Guard anyway:
            if result.get("final_report"):
                await self._report_service.save_report(
                    uuid.UUID(session_id), result["final_report"]
                )
        except Exception as exc:
            logger.exception(
                "Graph execution failed before approval",
                extra={"session_id": session_id, "error": str(exc)},
            )
            await self._report_service.save_failed(
                uuid.UUID(session_id), [str(exc)]
            )

# TODO: in new version (will add evaluator and conditional node) may be edit logic
    async def _resume_graph(self, session_id: str, decision: str, config: dict[str, Any]) -> None:
        """
        Resume graph execution after the HITL interrupt.

        On rejection → mark failed immediately, route_after_approval make graph END.
        On approval  → run scraper → analyzer → report → save report.
        On exception → mark failed with error details.

        """
        try:
            result: AgentState = await self._graph.ainvoke(
                Command(resume=decision), config=config
            )

            errors: list[str] = result.get("errors", [])
            final_report: str = result.get("final_report", "")

            if decision == "rejected":
                # route_after_approval → END, final_report will be empty
                await self._report_service.save_failed(
                    uuid.UUID(session_id),
                    ["Research rejected by user at approval step."],
                )
                return

            if final_report:
                await self._report_service.save_report(
                    uuid.UUID(session_id), final_report
                )
                if errors:
                    logger.warning(
                        "Report saved with partial errors",
                        extra={"session_id": session_id, "errors": errors},
                    )
            else:
                await self._report_service.save_failed(
                    uuid.UUID(session_id),
                    errors or ["Report generation returned empty content."],
                )

        except Exception as exc:
            logger.exception(
                "Graph execution failed after approval",
                extra={"session_id": session_id, "error": str(exc)},
            )
            await self._report_service.save_failed(
                uuid.UUID(session_id), [str(exc)]
            )