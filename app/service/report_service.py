"""
app/service/report_service.py

Handles all post-graph DB writes:
  - save_report()  → insert Report row + mark Session "completed"
  - save_failed()  → mark Session "failed"
  - get_report()   → fetch persisted report content

Called by ResearchService AFTER graph.ainvoke() returns — never inside nodes.

Architecture notes:
  - DB session is injected (DI) — never opened internally per-call
  - Caller (ResearchService) owns commit/rollback; this service only flushes
  - Both writes in save_report() happen in the same injected session
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.repositories.reports import ReportRepository
from app.db.repositories.research_sessions import SessionRepository
from app.models.enums.session_status import SessionStatus

logger = get_logger("ReportService")


class ReportService:

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._report_repo = ReportRepository(db)
        self._session_repo = SessionRepository(db)

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

    async def save_report(self, session_id: uuid.UUID, final_report: str) -> None:
        """
        Persist the finished report and mark the session as completed.

        Both writes happen in the same injected session so the DB is never
        left in a state where a report exists but the session is still "running".
        Caller owns the commit.
        """
        await self._report_repo.create(session_id, final_report)
        await self._session_repo.update_status(session_id, SessionStatus.COMPLETED)
        await self._db.flush()

        logger.info(
            "Report saved and session completed",
            extra={"session_id": str(session_id)},
        )

    async def save_failed(
        self, session_id: uuid.UUID, errors: list[str]
    ) -> None:
        """
        Mark the session as failed.

        Errors are logged for observability but not persisted to a separate
        table — they live in the LangGraph checkpoint (state["errors"])
        and in the application logs.
        Caller owns the commit.
        """
        await self._session_repo.update_status(session_id, SessionStatus.FAILED)
        await self._db.flush()

        logger.error(
            "Session marked as failed",
            extra={"session_id": str(session_id), "errors": errors},
        )