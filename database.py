import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://myuser:mypassword@localhost:5432/mydb"
)

# Pool math: with gunicorn workers = (2 * CPU) + 1 = 17
# Each worker gets its own pool. Total connections = workers * (pool_size + max_overflow)
# PostgreSQL max_connections = 300
# 17 workers * (10 + 5) = 255 — fits within 300 with headroom for admin/pgadmin
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=10,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
