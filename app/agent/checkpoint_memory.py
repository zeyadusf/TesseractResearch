from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import get_setting
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_db_url() -> str:
    db_url = get_setting().DATABASE_URL
    if "?ssl" in db_url:
        db_url = db_url[:db_url.find("?ssl")]
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if db_url.startswith("postgres+asyncpg://"):
        return db_url.replace("postgres+asyncpg://", "postgres://", 1)
    return db_url


async def create_checkpointer() -> tuple[AsyncPostgresSaver, object]:
    """
    يفتح connection وبيرجع (checkpointer, ctx).
    الـ caller (lifespan) لازم يحتفظ بالـ ctx عشان يقفل الـ connection في الـ shutdown:
        checkpointer, ctx = await create_checkpointer()
        ...
        await ctx.__aexit__(None, None, None)
    """
    logger.info("create_checkpointer | initializing AsyncPostgresSaver")
    ctx = AsyncPostgresSaver.from_conn_string(_get_db_url())
    checkpointer = await ctx.__aenter__()
    return checkpointer, ctx