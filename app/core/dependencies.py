from __future__ import annotations
from app.db.connection import SessionLocal

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

