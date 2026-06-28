"""
app/db/repositories/reports.py
Repository for research reports CRUD operations.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.schema.reports import Reports

logger = get_logger(__name__)


class ReportRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, session_id: uuid.UUID, content: str) -> Reports:
        report = Reports(
            id=uuid.uuid4(),
            session_id=session_id,
            content=content,
        )
        self.db.add(report)
        await self.db.flush()
        await self.db.refresh(report)
        logger.debug(f"Report created for session: {session_id}")
        return report

    async def get_by_session_id(self, session_id: uuid.UUID) -> Reports | None:
        result = await self.db.execute(
            select(Reports)
            .where(Reports.session_id == session_id)
            .order_by(Reports.created_at.desc())
        )
        return result.scalar_one_or_none()