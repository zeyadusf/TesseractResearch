
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import get_setting

config = get_setting()

postgres_conn = (
    f'postgresql+asyncpg://{config.POSTGRES_USERNAME}:'
    f'{config.POSTGRES_PASSWORD}@{config.POSTGRES_HOST}:'
    f'{config.POSTGRES_PORT}/{config.POSTGRES_DB}'
    f'?ssl=require'
)

engine = create_async_engine(
    postgres_conn,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    
    echo=config.DEBUG 
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)
