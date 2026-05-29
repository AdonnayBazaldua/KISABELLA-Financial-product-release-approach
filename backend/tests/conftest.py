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
from db.models import Base


# ---------- event loop ----------

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ---------- DB in-memory (SQLite for tests) ----------

@pytest_asyncio.fixture
async def fake_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
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
