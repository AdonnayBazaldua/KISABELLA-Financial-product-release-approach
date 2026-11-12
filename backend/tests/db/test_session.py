"""Tests unitarios de db.session (mockean engine).

Tests de integración con Postgres real viven en test_rls_integration.py
(marcados con @pytest.mark.integration — skip por default).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import db.session as session_module
from db.session import dispose_engine, get_db


def _reset_module_state():
    """Limpia el state global del módulo entre tests."""
    session_module._engine = None
    session_module._session_maker = None


@pytest.fixture(autouse=True)
def _clean_state():
    _reset_module_state()
    yield
    _reset_module_state()


def _patch_settings(monkeypatch):
    """Mockea get_settings para evitar leer .env real."""
    from core.config import Settings

    fake_settings = Settings(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        database_url="postgresql+psycopg://kisabella_app:pw@db:5432/test",
    )
    monkeypatch.setattr(
        session_module, "get_settings", lambda: fake_settings
    )
    return fake_settings


class TestEnsureEngine:
    def test_creates_engine_on_first_call(self, monkeypatch):
        _patch_settings(monkeypatch)
        mock_engine = MagicMock()
        mock_maker = MagicMock()

        with patch(
            "db.session.create_async_engine", return_value=mock_engine
        ) as mock_create, patch(
            "db.session.async_sessionmaker", return_value=mock_maker
        ) as mock_sm:
            result = session_module._ensure_engine()

        assert result is mock_maker
        mock_create.assert_called_once()
        mock_sm.assert_called_once()

    def test_idempotent(self, monkeypatch):
        _patch_settings(monkeypatch)
        mock_engine = MagicMock()
        mock_maker = MagicMock()

        with patch(
            "db.session.create_async_engine", return_value=mock_engine
        ) as mock_create, patch(
            "db.session.async_sessionmaker", return_value=mock_maker
        ):
            session_module._ensure_engine()
            session_module._ensure_engine()
            session_module._ensure_engine()

        # create_async_engine se llamó solo una vez (singleton)
        assert mock_create.call_count == 1

    def test_uses_database_url_from_settings(self, monkeypatch):
        settings = _patch_settings(monkeypatch)
        with patch(
            "db.session.create_async_engine"
        ) as mock_create, patch("db.session.async_sessionmaker"):
            session_module._ensure_engine()

        # Primer arg posicional = database_url
        assert mock_create.call_args.args[0] == settings.database_url

    def test_pool_config(self, monkeypatch):
        _patch_settings(monkeypatch)
        with patch(
            "db.session.create_async_engine"
        ) as mock_create, patch("db.session.async_sessionmaker"):
            session_module._ensure_engine()

        kwargs = mock_create.call_args.kwargs
        assert kwargs["pool_pre_ping"] is True
        assert kwargs["pool_size"] == 5


class TestGetDb:
    def test_rls_listener_uses_bindparams(self, monkeypatch):
        """Critical: bindparams, NO f-string. ADR-008."""
        settings = _patch_settings(monkeypatch)
        conn = MagicMock()

        session_module._set_rls_user(None, None, conn)

        sql_text, params = conn.execute.call_args.args
        assert ":uid" in str(sql_text)
        assert settings.app_user_id not in str(sql_text)  # NO interpolada
        assert params == {"uid": settings.app_user_id}

    async def test_commits_on_success(self, monkeypatch):
        _patch_settings(monkeypatch)

        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session
        mock_cm.__aexit__.return_value = None
        mock_maker = MagicMock(return_value=mock_cm)
        monkeypatch.setattr(session_module, "_ensure_engine", lambda: mock_maker)

        async for _ in get_db():
            pass

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_called()

    async def test_rollback_on_exception(self, monkeypatch):
        """FastAPI llama gen.athrow() en excepción del handler — simulamos eso."""
        _patch_settings(monkeypatch)

        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session
        mock_cm.__aexit__.return_value = None
        mock_maker = MagicMock(return_value=mock_cm)
        monkeypatch.setattr(session_module, "_ensure_engine", lambda: mock_maker)

        gen = get_db()
        # Avanzar al yield
        await gen.__anext__()

        # Simular excepción del handler — FastAPI usa athrow() para propagarla
        with pytest.raises(RuntimeError, match="boom"):
            await gen.athrow(RuntimeError("boom"))

        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_called()


class TestDisposeEngine:
    async def test_dispose_when_engine_exists(self, monkeypatch):
        mock_engine = AsyncMock()
        session_module._engine = mock_engine
        session_module._session_maker = MagicMock()

        await dispose_engine()

        mock_engine.dispose.assert_awaited_once()
        assert session_module._engine is None
        assert session_module._session_maker is None

    async def test_dispose_idempotent_when_no_engine(self):
        # State limpio por fixture autouse
        assert session_module._engine is None
        # No debe crashear
        await dispose_engine()
        assert session_module._engine is None
