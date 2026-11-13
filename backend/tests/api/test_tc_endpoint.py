"""Tests para GET /api/v1/tc."""
from __future__ import annotations

from tests.conftest import from_ip

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from core.config import Settings, get_settings as _original_get_settings
import db.session as session_module


@pytest.fixture
def fake_settings():
    return Settings(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        database_url="postgresql+psycopg://kisabella_app:pw@db:5432/test",
        allowed_ips="127.0.0.1",
        next_public_api_url="http://localhost:3000",
        app_user_id="00000000-0000-0000-0000-000000000001",
    )


@pytest.fixture
def app(monkeypatch, fake_settings):
    """App con get_settings mockeado."""
    _original_get_settings.cache_clear()

    async def _fake_dispose():
        return None

    monkeypatch.setattr(session_module, "dispose_engine", _fake_dispose)

    # Override get_settings en los módulos que la importaron
    for mod_name in ("main", "api.v1.exchange_rate"):
        mod = __import__(mod_name, fromlist=["get_settings"])
        if hasattr(mod, "get_settings"):
            monkeypatch.setattr(mod, "get_settings", lambda: fake_settings)

    import main as main_module

    return main_module.create_app()


@pytest.fixture
def client(app):
    return from_ip(app, "127.0.0.1")


def test_get_tc_returns_rate(client, monkeypatch):
    """GET /api/v1/tc retorna rate y source cuando Banxico responde."""
    monkeypatch.setattr(
        "api.v1.exchange_rate.get_usd_mxn",
        AsyncMock(return_value=(Decimal("17.1234"), "banxico")),
    )
    resp = client.get("/api/v1/tc")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rate"] == pytest.approx(17.1234, rel=1e-4)
    assert body["source"] == "banxico"
    assert "date" in body


def test_get_tc_returns_503_on_error(client, monkeypatch):
    """GET /api/v1/tc retorna 503 si Banxico falla y no hay cache."""
    monkeypatch.setattr(
        "api.v1.exchange_rate.get_usd_mxn",
        AsyncMock(side_effect=Exception("sin red")),
    )
    resp = client.get("/api/v1/tc")
    assert resp.status_code == 503
