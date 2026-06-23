from __future__ import annotations

from app.db.schema.sqlalchemy_base import SqlAlchemyBase

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Text, DateTime ,ForeignKey,func,Index
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
import uuid 

class Reports(SqlAlchemyBase):

    __tablename__ = "reports"

    id:Mapped[uuid.UUID]=mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    session_id:Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    content:Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at:Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default= func.now(),
        nullable=False,
    )

    session: Mapped["Sessions"] = relationship(#type:ignore
        "Sessions", back_populates="reports"
)
    
    __table_args__ = (
        Index("ix_reports_session_id", "session_id"),
    )