import asyncio
import os
import pathlib
import sys

db_file = pathlib.Path("test.db")
if db_file.exists():
    db_file.unlink()

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("JWT_REFRESH_TOKEN_EXPIRE_SECONDS", "604800")
os.environ.setdefault("PROVIDER_ENCRYPTION_KEY", "test-provider-encryption-key-1234567890")
os.environ.setdefault("PAYSTACK_WEBHOOK_SECRET", "test-paystack-secret")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from bomipay.db import Base, get_db
from bomipay.main import app
from bomipay.worker import app as celery_app

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="session")
def celery_config():
    """Configure Celery for testing - use eager mode to execute tasks synchronously."""
    return {
        "broker_url": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        "result_backend": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        "task_always_eager": True,
        "task_eager_propagates": True,
    }


@pytest.fixture(scope="session")
def celery_app_for_test():
    """Provide Celery app configured for testing."""
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    return celery_app
