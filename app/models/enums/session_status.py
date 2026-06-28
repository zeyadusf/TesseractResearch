"""
app/models/enums/session_status.py
"""
from enum import Enum


class SessionStatus(str, Enum):
    RUNNING = "running"
    WAITING_APPROVAL = "awaiting_approval"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"