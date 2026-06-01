# backend/tests/conftest.py
from __future__ import annotations

import asyncio
import uuid
from collections import deque
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agents.llm_client import FakeLLMClient
from core.config import Settings, get_settings as _original_get_settings
from db.models import Base


# ---------- event loop ----------

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ---------- Settings (test configuration) ----------

@pytest.fixture(autouse=True)
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patches get_settings globally so tools like banxico don't read a real .env.

    Patches the canonical source (core.config) so it works for any tool module.
    Tests with their own fake_settings can still call cache_clear() on
    the original saved function.
    """
    from core import config as config_mod
    from agents.tools import banxico as banxico_mod
    from agents.tools import tavily as tavily_mod

    fake_settings = Settings(
        _env_file=None,
        anthropic_api_key="test-key",
        anthropic_model="claude-3-5-sonnet-20241022",
        tavily_api_key="test-tavily",
        banxico_token="test-banxico-token",
        database_url="postgresql+asyncpg://test:test@localhost/test",
        secret_key="test-secret-key-that-is-at-least-32-characters-long-yes!",
        allowed_ips="127.0.0.1",
        app_user_id="00000000-0000-0000-0000-000000000001",
    )
    # Clear the original cached function
    _original_get_settings.cache_clear()
    # Patch in core.config (canonical source) so all tools use it
    monkeypatch.setattr(config_mod, "get_settings", lambda: fake_settings)
    # Also patch in banxico and tavily modules (they import get_settings locally)
    monkeypatch.setattr(banxico_mod, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(tavily_mod, "get_settings", lambda: fake_settings)
    yield


# ---------- DB in-memory (SQLite for tests) ----------

@pytest_asyncio.fixture
async def fake_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        # Needed for nested-transaction (savepoint) support in SQLite.
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Use a persistent connection so the savepoint survives the session lifecycle.
    conn = await engine.connect()
    # Outer transaction — never committed; holds all test data.
    await conn.begin()
    # Savepoint — code under test may rollback/commit against this nested tx.
    nested = await conn.begin_nested()

    maker = async_sessionmaker(
        bind=conn,
        expire_on_commit=False,
        class_=AsyncSession,
        join_transaction_mode="create_savepoint",
    )
    async with maker() as session:
        yield session

    # Roll back everything — no data leaks between tests.
    await conn.rollback()
    await conn.close()
    await engine.dispose()


# ---------- FakeLLMClient ----------

@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


# ---------- FakeMarkitdown ----------

class FakeMarkitdown:
    def __init__(self) -> None:
        self._registry: dict[str, str] = {}

    def register(self, path: str, markdown: str) -> None:
        self._registry[path] = markdown

    def convert(self, path: str):
        class _Result:
            def __init__(self, text: str) -> None:
                self.text_content = text
        return _Result(self._registry.get(path, ""))


@pytest.fixture
def fake_markitdown() -> FakeMarkitdown:
    return FakeMarkitdown()


# ---------- FakeStorage (in-memory filesystem) ----------

class FakeStorage:
    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}

    def write(self, path: str, data: bytes) -> None:
        self._files[path] = data

    def exists(self, path: str) -> bool:
        return path in self._files

    def read(self, path: str) -> bytes:
        return self._files[path]


@pytest.fixture
def fake_storage() -> FakeStorage:
    return FakeStorage()
