# I will rely on the postgres checkpointer for the  langGraph


# from __future__ import annotations

# from app.db.schema.sqlalchemy_base import SqlAlchemyBase

# from sqlalchemy.orm import Mapped, mapped_column, relationship
# from sqlalchemy import String, DateTime ,ForeignKey,func
# from datetime import datetime
# from sqlalchemy.dialects.postgresql import UUID ,JSONB
# import uuid 
# import json

# class Workflow_Checkpoints(SqlAlchemyBase):

#     __tablename__ = "workflow_checkpoints"

#     id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)

#     session_id:Mapped[uuid.UUID] = mapped_column(
#         UUID(as_uuid=True),
#         ForeignKey("sessions.id", ondelete="CASCADE"),
#         nullable=False,
#     )

#     thread_id:Mapped[str] = mapped_column(
#         String(100),
#         nullable=False,
#         default=None,
#     )

#     checkpoint:Mapped[dict] = mapped_column(
#         JSONB,nullable=False,default=dict
#     )

#     created_at:Mapped[datetime] = mapped_column(
#         DateTime(timezone=True),
#         server_default= func.now(),
#         nullable=False,
#     )


#     session:Mapped["Sessions"] = relationship( #type:ignore
#         "Sessions", back_populates="workflow_checkpoint"
#     )