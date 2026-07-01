"""
app/dependencies.py

FastAPI dependency functions for the entire application.

Lifecycle
---------
- Dispatchers (Search, Scraper, LLM) → singletons via lru_cache,
  created once at first call and closed in lifespan shutdown.
- DB session → per-request, opened and closed by get_async_session().
- ResearchService → per-request, injected with graph + db session.
"""

from __future__ import annotations

from functools import lru_cache
from typing import AsyncGenerator, TYPE_CHECKING

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import SessionLocal
from app.llm.dispatcher import LLMDispatcher
from app.tools.search.dispatcher import SearchDispatcher
from app.tools.scraper.dispatcher import ScraperDispatcher

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph
    from app.service.research_service import ResearchService


# ---------------------------------------------------------------------------
# DB session — per-request
# ---------------------------------------------------------------------------

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields one AsyncSession per request.
    Commit is handled here — service layer only flushes.
    Rollback on any unhandled exception.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Singletons — created once, shared across all requests
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_search_dispatcher() -> SearchDispatcher:
    return SearchDispatcher()

@lru_cache(maxsize=1)
def get_scraper_dispatcher() -> ScraperDispatcher:
    return ScraperDispatcher()


@lru_cache(maxsize=1)
def get_llm_dispatcher() -> LLMDispatcher:
    return LLMDispatcher()


# ---------------------------------------------------------------------------
# ResearchService — per-request, injected with graph + db
# ---------------------------------------------------------------------------

def get_research_service(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
) -> "ResearchService":
    """
    Builds a ResearchService for each request.

    The compiled graph is pulled from app.state (set during lifespan startup)
    so the checkpointer connection pool is shared across all requests.
    The DB session is per-request — injected and managed by get_async_session().
    """
    from app.service.research_service import ResearchService

    graph: CompiledStateGraph | None = getattr(request.app.state, "graph", None)
    if graph is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Research graph not initialised.",
        )

    return ResearchService(graph=graph, db=db)


# ---------------------------------------------------------------------------
# Lifespan shutdown
# ---------------------------------------------------------------------------

async def close_dispatchers() -> None:
    """
    Called in FastAPI lifespan shutdown.
    Closes all Redis connections held by the dispatchers.
    """
    await get_search_dispatcher().aclose()
    await get_scraper_dispatcher().aclose()