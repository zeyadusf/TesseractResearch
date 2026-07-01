"""
app/db/repositories/research_sessions.py
Repository for research sessions CRUD operations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.schema.research_sessions import Sessions

logger = get_logger(__name__)


class SessionRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, query: str) -> Sessions:
        session = Sessions(
            id=uuid.uuid4(),
            query=query,
            status="running",
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        logger.info(f"Session created: {session.id}")
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> Sessions | None:
        result = await self.db.execute(
            select(Sessions).where(Sessions.id == session_id)
        )
        return result.scalar_one_or_none()

    async def update_status(self, session_id: uuid.UUID, status: str) -> Sessions | None:
        result = await self.db.execute(
            update(Sessions)
            .where(Sessions.id == session_id)
            .values(
                status=status,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(Sessions)
        )
        await self.db.flush()

        updated = result.scalar_one_or_none()

        if updated is None:
            logger.warning(f"Session {session_id} not found — update skipped")
            return None

        logger.info(f"Session {session_id} status → {status}")
        return updated