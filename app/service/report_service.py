"""
app/service/report_service.py

Handles all post-graph DB writes:
  - save_report()  → insert Report row + mark Session "completed"
  - save_failed()  → mark Session "failed"

Called by ResearchService AFTER graph.ainvoke() returns — never inside nodes.
"""

from __future__ import annotations

import uuid

from app.core.logging import get_logger
from app.db.connection import SessionLocal
from app.db.repositories.reports import ReportRepository
from app.db.repositories.research_sessions import SessionRepository
from app.models.enums.session_status import SessionStatus

logger = get_logger("ReportService")


class ReportService:
    
    async def get_report(self, session_id: str) -> str:
        """
        Fetch the persisted final report from the database.

        Raises
        ------
        ValueError
            If no report has been saved yet for this session.
        """
        async with SessionLocal() as db:
            repo = ReportRepository(db)
            report = await repo.get_by_session_id(uuid.UUID(session_id))
        if report is None:
            raise ValueError(f"No report found for session_id={session_id!r}")
        return report.content
    
    async def save_report(self, session_id: uuid.UUID, final_report: str) -> None:
        """
        Persist the finished report and mark the session as completed.

        Both writes happen in a single transaction so the DB is never left in
        a state where a report exists but the session is still "running".
        """
        async with SessionLocal() as db:
            async with db.begin():
                report_repo = ReportRepository(db)
                session_repo = SessionRepository(db)

                await report_repo.create(session_id, final_report)
                await session_repo.update_status(session_id, SessionStatus.COMPLETED)

        logger.info(
            "Report saved and session completed",
            extra={"session_id": str(session_id)},
        )

    async def save_failed(
        self, session_id: uuid.UUID, errors: list[str]
    ) -> None:
        """
        Mark the session as failed. Errors are logged for observability but
        not persisted to a separate table — they live in the LangGraph
        checkpoint (state["errors"]) and in the application logs.
        """
        async with SessionLocal() as db:
            async with db.begin():
                session_repo = SessionRepository(db)
                await session_repo.update_status(session_id, SessionStatus.FAILED)

        logger.error(
            "Session marked as failed",
            extra={"session_id": str(session_id), "errors": errors},
        )