"""
app/api/routers/research_router.py

REST + SSE endpoints for TesseractResearch:

  POST   /research                → start_research (blocks until approval interrupt)
  GET    /research/{id}           → get session state
  POST   /research/{id}/approve   → HITL resume (blocks until graph finishes)
  GET    /research/{id}/report    → fetch final report
  GET    /research/{id}/events    → SSE stream of step progress
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.dependencies import get_research_service
from app.service.research_service import ResearchService

logger = get_logger("ResearchRouter")

router = APIRouter(prefix="/research", tags=["research"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class StartResearchRequest(BaseModel):
    query: str = Field(..., min_length=10, max_length=2000, description="Research query")


class StartResearchResponse(BaseModel):
    session_id: str
    message: str = (
        "Research is paused at approval step. "
        "Review search results then POST /{id}/approve."
    )


class SessionStateResponse(BaseModel):
    session_id: str
    current_step: str
    status: str
    approval_required: bool
    errors: list[str]


class ApproveRequest(BaseModel):
    approved: bool = Field(..., description="True to approve, False to reject search results")


class ApproveResponse(BaseModel):
    session_id: str
    decision: str
    message: str


class ReportResponse(BaseModel):
    session_id: str
    report: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=StartResearchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new research session",
)
async def start_research(
    body: StartResearchRequest,
    service: ResearchService = Depends(get_research_service),
) -> StartResearchResponse:
    """
    Creates a DB session and runs the graph until it hits the approval
    interrupt (planner → search → pause).

    Blocks until the graph suspends — typically a few seconds.
    Returns session_id once the graph is waiting for human approval.
    """
    try:
        session_id = await service.start_research(body.query)
    except Exception as exc:
        logger.exception("Failed to start research", extra={"query": body.query})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start research: {exc}",
        ) from exc

    return StartResearchResponse(session_id=session_id)


@router.get(
    "/{session_id}",
    response_model=SessionStateResponse,
    summary="Get current session state",
)
async def get_session_state(
    session_id: str,
    service: ResearchService = Depends(get_research_service),
) -> SessionStateResponse:
    """Returns current_step, status, approval_required, and any errors."""
    _validate_uuid(session_id)
    try:
        state = await service.get_state(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to get state", extra={"session_id": session_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return SessionStateResponse(
        session_id=session_id,
        current_step=state.get("current_step", "unknown"),
        status=str(state.get("status", "unknown")),
        approval_required=bool(state.get("approval_required", False)),
        errors=state.get("errors", []),
    )


@router.post(
    "/{session_id}/approve",
    response_model=ApproveResponse,
    summary="Approve or reject search results (HITL)",
)
async def approve_research(
    session_id: str,
    body: ApproveRequest,
    service: ResearchService = Depends(get_research_service),
) -> ApproveResponse:
    """
    Resumes the paused graph and blocks until it reaches END.

    - approved=true  → scraper → analyzer → report → done
    - approved=false → session marked failed → END

    Returns once the graph finishes — client can then fetch the report.
    """
    _validate_uuid(session_id)
    try:
        await service.approve(session_id, body.approved)
    except Exception as exc:
        logger.exception("Failed to process approval", extra={"session_id": session_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    decision = "approved" if body.approved else "rejected"
    message = (
        "Research approved. Report is ready — fetch it via GET /{id}/report."
        if body.approved
        else "Research rejected. Session marked as failed."
    )
    return ApproveResponse(session_id=session_id, decision=decision, message=message)


@router.get(
    "/{session_id}/report",
    response_model=ReportResponse,
    summary="Fetch the final research report",
)
async def get_report(
    session_id: str,
    service: ResearchService = Depends(get_research_service),
) -> ReportResponse:
    """Returns the persisted report. 404 if not yet complete."""
    _validate_uuid(session_id)
    try:
        report = await service.get_report(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to get report", extra={"session_id": session_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return ReportResponse(session_id=session_id, report=report)


@router.get(
    "/{session_id}/events",
    summary="SSE stream of research progress",
    response_class=StreamingResponse,
)
async def stream_events(
    session_id: str,
    service: ResearchService = Depends(get_research_service),
) -> StreamingResponse:
    """
    Server-Sent Events stream. Polls LangGraph checkpoint state every 2 s
    and emits an event whenever `current_step` changes.

    Event format (text/event-stream):
        data: {"step": "<node_name>", "status": "<session_status>", "approval_required": <bool>}

    Terminal steps: "done", "completed", or "failed" — client should close the connection.
    """
    _validate_uuid(session_id)
    return StreamingResponse(
        _sse_generator(session_id, service),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------

_TERMINAL_STEPS = {"done", "failed", "completed"}
_POLL_INTERVAL  = 2.0   # seconds between checkpoint polls
_MAX_POLLS      = 450   # 15 min timeout (450 × 2 s)


async def _sse_generator(
    session_id: str,
    service: ResearchService,
) -> AsyncGenerator[str, None]:
    """
    Polls graph state and yields SSE events on step transitions.
    Sends a keepalive comment every poll to prevent proxy timeouts.
    Terminates when step reaches a terminal value or on error.
    """
    last_step: str | None = None
    polls = 0

    yield ": connected\n\n"

    while polls < _MAX_POLLS:
        polls += 1
        await asyncio.sleep(_POLL_INTERVAL)

        try:
            state = await service.get_state(session_id)
        except ValueError:
            yield ": waiting\n\n"
            continue
        except Exception as exc:
            logger.exception("SSE state poll failed", extra={"session_id": session_id})
            yield _sse_event({"error": str(exc), "step": "error"})
            return

        current_step: str   = state.get("current_step", "unknown")
        session_status: str = str(state.get("status", "unknown"))
        approval_required: bool = bool(state.get("approval_required", False))

        if current_step != last_step:
            last_step = current_step
            yield _sse_event({
                "step": current_step,
                "status": session_status,
                "approval_required": approval_required,
            })

        if current_step in _TERMINAL_STEPS or session_status in _TERMINAL_STEPS:
            return

        yield ": heartbeat\n\n"

    yield _sse_event({"step": "timeout", "status": "unknown", "approval_required": False})


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_uuid(value: str) -> None:
    try:
        uuid.UUID(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid session_id format: {value!r}",
        )