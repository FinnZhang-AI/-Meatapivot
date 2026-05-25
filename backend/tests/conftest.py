"""Pytest configuration for Meatapivot backend tests."""

import pytest
import asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.services.database import Base

# Use in-memory SQLite for unit tests
TEST_DATABASE_URL = "postgresql+asyncpg://knowledge:knowledge123@localhost:5432/knowledge_db_test"

# Create async engine for tests
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

TestAsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for tests."""
    async with TestAsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client():
    """Provide a FastAPI test client."""
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)
    except Exception as e:
        pytest.skip(f"Backend dependencies not available: {e}")


# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)
