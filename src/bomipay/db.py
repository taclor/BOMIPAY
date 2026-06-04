import uuid
from sqlalchemy import CHAR, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .config import settings


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True
    python_type = uuid.UUID

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if isinstance(value, bytes):
            value = value.decode()
        if not isinstance(value, str):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        if isinstance(value, bytes):
            value = value.decode()
        try:
            return uuid.UUID(value)
        except Exception:
            return value


engine = create_async_engine(
    settings.database_url,
    future=True,
    echo=False,
    pool_size=20,  # Number of connections to keep in pool
    max_overflow=10,  # Additional connections when pool is saturated
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Test connections before using them
)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

# Import models so metadata includes all table definitions when create_all is invoked.
from . import models  # noqa: F401


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
