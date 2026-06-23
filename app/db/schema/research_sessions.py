from __future__ import annotations

from  app.db.schema.sqlalchemy_base import SqlAlchemyBase
from typing import List
from sqlalchemy.orm import Mapped,mapped_column,relationship
from sqlalchemy import Text,String,DateTime,func,Index
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

class Sessions(SqlAlchemyBase):

    __tablename__ = "sessions"

    id:Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    query:Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status:Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='running',
    )

    created_at:Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default= func.now(),
        nullable=False,
    )

    updated_at:Mapped[datetime] = mapped_column(
        DateTime(timezone = True),
        server_default = func.now(),
        onupdate = func.now(),
        nullable = False,
    )

    # I will rely on the postgres checkpointer for the  langGraph
    # workflow_checkpoint:Mapped[List["Workflow_Checkpoints"]] = relationship( # type: ignore
    #     "Workflow_Checkpoints" , back_populates="session", cascade="all, delete-orphan"
    # )

    reports:Mapped[List["Reports"]] = relationship( # type: ignore
        "Reports" , back_populates="session", cascade="all, delete-orphan"
    )


    __table_args__ = (
        Index("ix_sessions_created_at", "created_at"),
    )