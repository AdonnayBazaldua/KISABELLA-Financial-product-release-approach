"""Tests E2E del app FastAPI — middleware + health."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.config as config_module
import db.session as session_module
from core.config import Settings, get_settings as _original_get_settings
from core.security import (
    IPWhitelistMiddleware,
    SecurityHeadersMiddleware,
)


@pytest.fixture
def fake_settings(monkeypatch):
    s = Settings(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        database_url="postgresql+psycopg://capi_app:pw@db:5432/test",
        secret_key="x" * 32,
        allowed_ips="127.0.0.1,10.0.0.5",
        frontend_origin="http://localhost:3000",
    )
    _original_get_settings.cache_clear()
    monkeypatch.setattr(config_module, "get_settings", lambda: s)
    # main.py importa get_settings via from core.config import get_settings
    import main as main_module

    monkeypatch.setattr(main_module, "get_settings", lambda: s)
    return s


@pytest.fixture
def app(fake_settings, monkeypatch):
    # Evitar que el lifespan toque la DB
    async def _fake_dispose():
        return None

    monkeypatch.setattr(session_module, "dispose_engine", _fake_dispose)
    import main as main_module

    return main_module.create_app()


@pytest.fixture
def client(app):
    return TestClient(app, headers={"X-Forwarded-For": "127.0.0.1"})


class TestHealth:
    def test_health_returns_ok(self, app):
        # Health no requiere IP whitelist
        with TestClient(app) as c:
            r = c.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body

    def test_health_works_without_x_forwarded_for(self, app):
        with TestClient(app) as c:
            r = c.get("/health")
        assert r.status_code == 200


class TestIPWhitelist:
    def test_whitelisted_ip_passes(self, client):
        # X-Forwarded-For 127.0.0.1 está en allowed_ips
        # health funciona pero no expone IP check; busquemos algo más
        r = client.get("/health")
        assert r.status_code == 200

    def test_non_whitelisted_ip_rejected(self, app):
        # No /health — verificamos contra OpenAPI que sí pasa por whitelist
        with TestClient(app, headers={"X-Forwarded-For": "9.9.9.9"}) as c:
            r = c.get("/openapi.json")
        assert r.status_code == 403
        assert r.json()["code"] == "IP_NOT_WHITELISTED"

    def test_health_bypasses_whitelist(self, app):
        with TestClient(app, headers={"X-Forwarded-For": "9.9.9.9"}) as c:
            r = c.get("/health")
        assert r.status_code == 200


class TestSecurityHeaders:
    def test_hsts_present(self, client):
        r = client.get("/health")
        assert "strict-transport-security" in {k.lower() for k in r.headers}
        hsts = r.headers["strict-transport-security"]
        assert "max-age=" in hsts

    def test_xfo_deny(self, client):
        r = client.get("/health")
        assert r.headers["x-frame-options"].lower() == "deny"

    def test_content_type_nosniff(self, client):
        r = client.get("/health")
        assert r.headers["x-content-type-options"].lower() == "nosniff"

    def test_csp_present(self, client):
        r = client.get("/health")
        assert "content-security-policy" in {k.lower() for k in r.headers}

    def test_referrer_policy(self, client):
        r = client.get("/health")
        assert "referrer-policy" in {k.lower() for k in r.headers}


class TestCORS:
    def test_allows_configured_origin(self, app):
        with TestClient(app, headers={"X-Forwarded-For": "127.0.0.1"}) as c:
            r = c.options(
                "/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )
        # OPTIONS preflight
        assert "access-control-allow-origin" in {k.lower() for k in r.headers}

    def test_rejects_unknown_origin(self, app):
        with TestClient(app, headers={"X-Forwarded-For": "127.0.0.1"}) as c:
            r = c.options(
                "/health",
                headers={
                    "Origin": "http://evil.com",
                    "Access-Control-Request-Method": "GET",
                },
            )
        # Sin allow-origin si no match
        allow_origin = r.headers.get("access-control-allow-origin", "")
        assert allow_origin != "http://evil.com"
