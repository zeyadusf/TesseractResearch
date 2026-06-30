from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import get_setting
from app.core.logging import get_logger

logger = get_logger(__name__)

def _get_db_url() -> str:
    db_url = get_setting().DATABASE_URL
    if db_url.find('?ssl'):
        db_url= db_url[:db_url.find('?ssl')]
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif db_url.startswith("postgres+asyncpg://"):
        return db_url.replace("postgres+asyncpg://", "postgres://", 1)
    
    return 
    
@asynccontextmanager
async def get_checkpointer():
    """
    Async context manager — يفتح connection، يديك الـ checkpointer، ويقفل لما تخلص.
    
    Usage:
        async with get_checkpointer() as checkpointer:
            await checkpointer.setup()
    """
    logger.info("get_checkpointer | initializing AsyncPostgresSaver")
    async with AsyncPostgresSaver.from_conn_string(_get_db_url()) as checkpointer:
        yield checkpointer