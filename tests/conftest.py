import pytest_asyncio
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql+asyncpg://aidarmaratbekov@localhost:5432/taskmanager"

test_engine = create_async_engine(TEST_DATABASE_URL, pool_size=5, max_overflow=0)
test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_infra():
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Patch redis_client used in main.py to one on the current event loop
    import app.main as main_module
    test_redis = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    main_module.redis_client = test_redis

    # Also patch the engine used by /ready probe
    import app.main as m
    m.engine = test_engine

    yield

    await test_redis.aclose()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_tables():
    yield
    async with test_session() as session:
        await session.execute(text("DELETE FROM tasks"))
        await session.commit()


async def override_get_db():
    async with test_session() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
