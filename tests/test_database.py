import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_engine, get_sessionmaker, DATABASE_URL


# --- Fix event loop issue ---
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session (and all tests in the session)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_sessionmaker_creation()-> None:
    """Test if get_sessionmaker() correctly creates an async session."""
    with patch("database.get_engine", new_callable=AsyncMock):
        session_maker = get_sessionmaker()
        assert session_maker is not None
        assert callable(session_maker)


def test_database_url()-> None:
    """Test if DATABASE_URL is correctly loaded."""
    assert isinstance(DATABASE_URL, str)
    assert DATABASE_URL.startswith("postgresql")  # Ensure it's a PostgreSQL URL

@pytest.mark.asyncio
async def test_engine_creation()-> None:
    """Test if get_engine() correctly creates an async engine."""
    with patch("database.create_async_engine", new_callable=AsyncMock) as mock_create_engine:
        engine = get_engine()
        assert engine is not None
        mock_create_engine.assert_called_once_with(DATABASE_URL, future=True, echo=True)

@pytest.mark.asyncio
async def test_sessionmaker_uses_correct_engine()-> None:
    """Test if sessionmaker is correctly bound to the async engine."""
    mock_engine = AsyncMock()
    with patch("database.get_engine", return_value=mock_engine):
        session_maker = get_sessionmaker()
        assert session_maker.kw["bind"] == mock_engine  # Ensure the session is using the mock engine

@pytest.mark.asyncio
async def test_sessionmaker_returns_async_session()-> None:
    """Ensure get_sessionmaker() produces an async session."""
    mock_engine = AsyncMock()
    with patch("database.get_engine", return_value=mock_engine):
        session_maker = get_sessionmaker()
        async_session = session_maker()  # Call the sessionmaker to produce a session
        assert isinstance(async_session, AsyncSession)  # ✅ Check against AsyncSession, NOT AsyncMock

