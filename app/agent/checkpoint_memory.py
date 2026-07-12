from psycopg_pool import AsyncConnectionPool
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


async def create_checkpointer() -> tuple[AsyncPostgresSaver, AsyncConnectionPool]:
    """
    يفتح connection pool وبيرجع (checkpointer, pool).
    الـ caller (lifespan) لازم يحتفظ بالـ pool عشان يقفله في الـ shutdown:
        checkpointer, pool = await create_checkpointer()
        ...
        await pool.close()

    بنستخدم AsyncConnectionPool بدل connection واحدة (from_conn_string) عشان:
    - نتجنب الاعتماد على connection واحدة تفضل مفتوحة طول عمر الـ app
      وتموت بصمت لو الـ provider أو الـ NAT قفلها بعد فترة idle
      (نفس مشكلة الـ Redis EOF/Timeout اللي واجهناها قبل كده).
    - نضيف TCP keepalives عشان نمنع اعتبار الـ connection idle من الأساس.
    - الـ pool بيدير أكتر من connection وبيقدر يستبدل أي connection ميتة
      بدل ما ينفجر جوه aget_tuple في نص request حقيقي.
    """
    logger.info("create_checkpointer | initializing AsyncConnectionPool + AsyncPostgresSaver")

    db_url = _get_db_url()

    pool = AsyncConnectionPool(
        conninfo=db_url,
        min_size=1,
        max_size=10,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
        open=False,
    )
    await pool.open()

    checkpointer = AsyncPostgresSaver(pool)

    # لو أول مرة بتشغل الجداول دي (checkpoints, writes, ...):
    # لازم يتشغل مرة واحدة بس (مش كل startup)، فاعتبرها migration منفصلة.
    # await checkpointer.setup()

    logger.info("create_checkpointer | pool opened min_size=1 max_size=10")
    return checkpointer, pool