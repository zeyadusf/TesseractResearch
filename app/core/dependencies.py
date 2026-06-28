from __future__ import annotations
from functools import lru_cache

from app.db.connection import SessionLocal
from app.llm.dispatcher import LLMDispatcher
from app.tools.search.dispatcher import SearchDispatcher
from app.tools.scraper.dispatcher import ScraperDispatcher

async def get_async_session() :
    try:
        async with SessionLocal() as session:
            yield session
            await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.commit()
        await session.close()

@lru_cache(maxsize=1)
def get_search_dispatcher() -> SearchDispatcher:
    return SearchDispatcher()

@lru_cache(maxsize=1)
def get_scraper_dispatcher() -> ScraperDispatcher:
    return ScraperDispatcher()


@lru_cache(maxsize=1)
def get_llm_dispatcher() -> LLMDispatcher:
    return LLMDispatcher()



async def close_dispatchers() -> None:
    """
    Called in FastAPI lifespan shutdown.
    Closes all Redis connections held by the dispatchers.
    """
    await get_search_dispatcher().aclose()
    await get_scraper_dispatcher().aclose()