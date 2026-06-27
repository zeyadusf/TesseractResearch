from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


from app.core.config import get_setting
from app.core.logging import get_logger

logger = get_logger(__name__)


async def get_checkpointer() -> AsyncPostgresSaver:
    """
    Create and return a configured AsyncPostgresSaver.

    LangGraph's AsyncPostgresSaver uses the raw asyncpg connection string
    (postgresql+asyncpg://...) — strip the SQLAlchemy dialect prefix so
    asyncpg gets a plain postgresql:// or postgres:// URL.

    The caller is responsible for using this as an async context manager OR
    calling .setup() once during app startup to create the checkpoint tables.
    """
    db_url = get_setting().DATABASE_URL

    # SQLAlchemy uses "postgresql+asyncpg://..." but asyncpg expects "postgresql://..."
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif db_url.startswith("postgres+asyncpg://"):
        db_url = db_url.replace("postgres+asyncpg://", "postgres://", 1)

    logger.info("get_checkpointer | initializing AsyncPostgresSaver")
    checkpointer = AsyncPostgresSaver.from_conn_string(db_url)
    return checkpointer