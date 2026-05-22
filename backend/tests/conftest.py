from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from db.database import get_session
from main import app


def _make_fake_session():
    """Return an AsyncMock posing as an SQLAlchemy AsyncSession with empty results."""
    session = AsyncMock()
    empty_scalars = MagicMock()
    empty_scalars.all.return_value = []
    empty_scalars.scalar_one_or_none = MagicMock(return_value=None)
    execute_result = MagicMock()
    execute_result.scalars.return_value = empty_scalars
    execute_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def fake_session():
    return _make_fake_session()


@pytest.fixture
async def client(fake_session):
    async def _override_get_session():
        yield fake_session

    app.dependency_overrides[get_session] = _override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
