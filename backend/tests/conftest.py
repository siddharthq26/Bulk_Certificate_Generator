"""
Shared pytest fixtures for all tests.

Uses an in-memory SQLite database (via aiosqlite) to keep tests
fast and hermetic — no external services required.
"""
import os
import tempfile
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

# ── Set up test environment variables before importing app ─────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("SYNC_DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("CERT_STORAGE_PATH", tempfile.mkdtemp())
os.environ.setdefault("DEBUG", "True")

from app.main import app
from app.db.database import Base, get_db

# ── In-memory async SQLite engine for tests ────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_bulk_cert.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Create all tables once for the test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()
    for db_name in ["test_bulk_cert.db", "test.db"]:
        if os.path.exists(db_name):
            try:
                os.remove(db_name)
            except OSError:
                pass


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Truncate tables before each test for isolation."""
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def db_session():
    """Provide a test database session."""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    """
    Async test client with DB dependency overridden to use test DB.
    Celery tasks are mocked to run eagerly (synchronously in-process).
    """
    async def override_get_db():
        async with TestingSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    # Mock Celery task to avoid needing a real broker in tests
    with patch(
        "app.api.routes.jobs.generate_certificates_for_job"
    ) as mock_task:
        mock_result = MagicMock()
        mock_result.id = "test-task-id-1234"
        mock_task.delay.return_value = mock_result
        
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac, mock_task

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_no_mock(db_session):
    """Client without Celery mock — for testing actual task logic."""
    async def override_get_db():
        async with TestingSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Reusable sample data ──────────────────────────────────────────────────────

@pytest.fixture
def valid_job_payload():
    return {
        "event_name": "Python Mastery Workshop",
        "issued_by": "Tech Academy",
        "recipients": [
            {
                "name": "Alice Johnson",
                "email": "alice@example.com",
                "course_name": "Advanced Python",
                "completion_date": "2024-06-15",
            },
            {
                "name": "Bob Smith",
                "email": "bob@example.com",
                "course_name": "Advanced Python",
                "completion_date": "2024-06-15",
            },
        ],
    }


@pytest.fixture
def single_recipient_payload():
    return {
        "event_name": "Data Science Bootcamp",
        "issued_by": "DataCorp",
        "recipients": [
            {
                "name": "Carol White",
                "email": "carol@example.com",
                "completion_date": "2024-07-01",
            }
        ],
    }
