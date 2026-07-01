"""
app/service/research_service.py

Orchestrates all research session lifecycle:
  - start_research()  → creates DB session, runs graph until approval interrupt
  - approve()         → resumes HITL interrupt via Command, runs to completion
  - get_state()       → reads current LangGraph checkpoint state
  - get_report()      → fetches persisted report from DB

Architecture notes:
  - DB session is injected (DI) — never opened internally per-call
  - No asyncio.create_task — graph runs in the same coroutine context
    so LangGraph interrupt() works correctly without context errors
  - start_research() blocks until the graph hits the approval interrupt
  - approve() blocks until the graph runs to completion
  - Caller (router) owns commit/rollback; service only flushes

Tracing notes:
  - LangSmith's automatic env-var-based tracer auto-detection is broken
    in the current langsmith/langchain-core version combo installed in
    this project (auto-detection silently fails inside langchain_core's
    _configure(), swallowed via the stdlib `logging` module, invisible
    in our loguru-based logs). We work around this by passing a
    LangChainTracer explicitly via config["callbacks"] on every
    graph.ainvoke() call instead of relying on LANGSMITH_TRACING=true
    auto-detection.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from langchain_core.tracers import LangChainTracer
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.core.config import get_setting
from app.core.logging import get_logger
from app.db.repositories.research_sessions import SessionRepository
from app.db.repositories.reports import ReportRepository
from app.models.enums.session_status import SessionStatus
from app.service.report_service import ReportService

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

settings = get_setting()
logger = get_logger(__name__)

# Explicit LangChainTracer — bypasses the broken env-var auto-detection.
# Created once at module load; safe to share across requests since
# LangChainTracer itself is stateless per-invocation (each call gets its
# own run tree from the config passed to ainvoke()).
_tracer = LangChainTracer(project_name=settings.LANGSMITH_PROJECT)


class ResearchService:
    """
    Single entry point for all research session operations.

    Parameters
    ----------
    graph:
        Compiled LangGraph instance — injected at construction time
        (stored on app.state during lifespan startup) so every request
        shares the same checkpointer connection pool.
    db:
        Async SQLAlchemy session — injected per-request via FastAPI DI.
        Caller is responsible for commit/rollback; this service only flushes.

    Flow
    ----
    POST /research
        start_research() → _create_session() → _run_graph()
        Graph runs: planner → search → hits interrupt() → suspends
        HTTP response returns with session_id once graph is suspended.

    GET /research/{id}/events
        SSE polls get_state() every 2 s to stream step progress to client.

    POST /research/{id}/approve
        approve() → _resume_graph()
        Graph resumes: scraper → analyzer → report → END
        HTTP response returns once graph finishes.
    """

    def __init__(self, graph: "CompiledStateGraph", db: AsyncSession) -> None:
        self._graph = graph
        self._db = db
        self._repo = SessionRepository(db)
        self._report_repo = ReportRepository(db)

        self._report_service = ReportService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_research(self, query: str) -> str:
        """
        Create a session row then run the graph until it hits the approval
        interrupt.  Blocks until the interrupt suspends the graph.

        The HTTP request stays open during planner + search execution
        (typically a few seconds).  The SSE stream is available immediately
        after this returns for the client to follow progress.

        Returns
        -------
        str
            The session_id (UUID string) that acts as LangGraph thread_id.

        Raises
        ------
        Exception
            Re-raises any error from DB creation or graph execution.
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

        # Blocking — runs in the same coroutine context so LangGraph's
        # interrupt() propagates correctly without RuntimeError.
        # Returns once the graph hits interrupt() at the approval node.
        await self._run_until_interrupt(session_id, initial_state)

        logger.info("Research session started — awaiting approval", extra={"session_id": session_id})
        return session_id

    async def approve(self, session_id: str, approved: bool) -> None:
        """
        Resume the graph after the HITL interrupt and run to completion.
        Blocks until the graph reaches END.

        Parameters
        ----------
        session_id:
            Must match an existing thread_id in the checkpointer.
        approved:
            True  → resume="approved" → scraper → analyzer → report
            False → resume="rejected" → session marked failed → END

        Raises
        ------
        Exception
            Re-raises any error from graph execution or report persistence.
        """
        decision = "approved" if approved else "rejected"
        config = {
            "configurable": {"thread_id": session_id},
            "run_name": f"research-resume-{session_id}",
            "tags": ["tesseract-research"],
            "callbacks": [_tracer],
        }

        logger.info(
            "Resuming graph after HITL",
            extra={"session_id": session_id, "decision": decision},
        )

        await self._resume_graph(session_id, decision, config)

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
    
    
    async def get_report(self, session_id: str) -> str:
        """
        Fetch the persisted final report from the database.

        Raises
        ------
        ValueError
            If no report has been saved yet for this session.
        """
        report = await self._report_repo.get_by_session_id(uuid.UUID(session_id))
        if report is None:
            raise ValueError(f"No report found for session_id={session_id!r}")
        return report.content

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _create_session(self, query: str) -> str:
        """
        Insert a new session row inside the injected transaction.

        No commit here — the router owns the transaction boundary and
        will commit after start_research() returns successfully.
        """
        try:
            session = await self._repo.create(query)
            await self._db.flush()
            logger.info("Session row created", extra={"session_id": str(session.id)})
            return str(session.id)

        except Exception as exc:
            logger.error(
                "Failed to create session row for query=%r: %s",
                query,
                exc,
                exc_info=True,
            )
            raise

    # TODO: In a future version (after adding an evaluator + conditional nodes)
    #       this logic may need to validate the resulting status field.
    async def _run_until_interrupt(
        self, session_id: str, initial_state: AgentState
    ) -> None:
        """
        Run the graph from START in the caller's coroutine context.

        The graph suspends itself when it hits interrupt() at the approval
        node — ainvoke() returns at that point with a GraphInterrupt value.
        We intentionally do NOT save a report here; that happens in
        _resume_graph() after the human approves.

        On any exception before the interrupt we mark the session as failed.
        """
        config = {
            "configurable": {"thread_id": session_id},
            "run_name": f"research-{session_id}",
            "tags": ["tesseract-research"],
            "callbacks": [_tracer],
        }
        try:
            await self._graph.ainvoke(initial_state, config=config)
            # ainvoke() returns here when the graph hits interrupt().
            # If it somehow reaches END without interrupting (edge case),
            # there is nothing to save yet — approval was skipped.

        except Exception as exc:
            logger.error(
                "Graph execution failed before approval interrupt — session=%s error=%s",
                session_id,
                exc,
                exc_info=True,
                extra={"session_id": session_id, "error_type": type(exc).__name__},
            )
            try:
                await self._report_service.save_failed(
                    uuid.UUID(session_id), [str(exc)]
                )
            except Exception as update_err:
                logger.error(
                    "Failed to mark session %s as failed: %s",
                    session_id,
                    update_err,
                )
            raise

    # TODO: in new version (will add evaluator + conditional node) may edit logic
    async def _resume_graph(
        self, session_id: str, decision: str, config: dict[str, Any]
    ) -> None:
        """
        Resume graph execution after the HITL interrupt and run to END.

        On rejection → mark failed immediately (route_after_approval → END).
        On approval  → run scraper → analyzer → report → save report.
        On exception → mark failed + re-raise so the router returns 500.
        """
        try:
            result: AgentState = await self._graph.ainvoke(
                Command(resume=decision), config=config
            )

            errors: list[str] = result.get("errors", [])
            final_report: str = result.get("final_report", "")

            if decision == "rejected":
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
                        "Report saved with partial errors — session=%s errors=%s",
                        session_id,
                        errors,
                        extra={"session_id": session_id, "errors": errors},
                    )
            else:
                await self._report_service.save_failed(
                    uuid.UUID(session_id),
                    errors or ["Report generation returned empty content."],
                )

        except Exception as exc:
            logger.error(
                "Graph execution failed after approval — session=%s error=%s",
                session_id,
                exc,
                exc_info=True,
                extra={"session_id": session_id, "error_type": type(exc).__name__},
            )
            try:
                await self._report_service.save_failed(
                    uuid.UUID(session_id), [str(exc)]
                )
            except Exception as update_err:
                logger.error(
                    "Failed to mark session %s as failed after approval: %s",
                    session_id,
                    update_err,
                )
            raise