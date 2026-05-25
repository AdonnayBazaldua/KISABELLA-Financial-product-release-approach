"""Tests E2E del endpoint /api/v1/evaluations."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import core.config as config_module
import db.session as session_module
from agents.contracts import AgentResult
from agents.llm_client import FakeLLMClient, get_llm_client
from api.v1.evaluations import (
    get_background_session_factory,
    get_user_id,
)
from core.config import Settings, get_settings
from db.session import get_db


# ===== Fixtures =====


def _valid_payload(**overrides) -> dict:
    base = {
        "name": "Evaluación test",
        "product_name": "Smartwatch X1",
        "category": "fisico",
        "cost_purchase": "250.00",
        "cost_freight": "30.00",
        "cost_customs": "50.00",
        "target_price": "599.00",
        "estimated_units_month": 100,
        "exchange_rate_used": "19.8500",
    }
    base.update(overrides)
    return base


def _agent_result_fixture(score: int = 75) -> AgentResult:
    return AgentResult(
        score=score,
        veredicto_corto="veredicto de prueba",
        analisis_extenso="x" * 400,
        hallazgos_clave=["hallazgo"],
        recomendaciones=["recomendacion"],
    )


TEST_USER_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def fake_settings():
    return Settings(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        database_url="postgresql+psycopg://capi_app:pw@db:5432/test",
        secret_key="x" * 32,
        allowed_ips="127.0.0.1",
        next_public_api_url="http://localhost:3000",
        app_user_id=str(TEST_USER_ID),
    )


@pytest.fixture
def fake_db_session():
    """Mock AsyncSession que captura add() y soporta execute/commit."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    empty_result = MagicMock()
    empty_result.scalar_one_or_none = MagicMock(return_value=None)
    empty_result.scalars = MagicMock()
    empty_result.scalars.return_value.all = MagicMock(return_value=[])
    session.execute = AsyncMock(return_value=empty_result)
    return session


@pytest.fixture
def fake_llm():
    fake = FakeLLMClient()
    fake.queue_responses([_agent_result_fixture(score=80 - i * 5) for i in range(4)])
    return fake


@pytest.fixture
def app(monkeypatch, fake_settings, fake_db_session, fake_llm):
    """App con dependency_overrides para todas las deps externas."""
    config_module.get_settings.cache_clear()

    async def _fake_dispose():
        return None

    monkeypatch.setattr(session_module, "dispose_engine", _fake_dispose)

    # Override get_settings en TODOS los módulos que la importaron
    for mod_name in ("main", "api.v1.evaluations", "db.session"):
        mod = __import__(mod_name, fromlist=["get_settings"])
        if hasattr(mod, "get_settings"):
            monkeypatch.setattr(mod, "get_settings", lambda: fake_settings)

    import main as main_module

    app = main_module.create_app()

    # DI overrides
    async def _override_get_db():
        yield fake_db_session

    @asynccontextmanager
    async def _fake_session_factory():
        yield fake_db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    app.dependency_overrides[get_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_background_session_factory] = (
        lambda: _fake_session_factory
    )
    app.dependency_overrides[get_settings] = lambda: fake_settings

    return app


@pytest.fixture
def client(app):
    return TestClient(app, headers={"X-Forwarded-For": "127.0.0.1"})


# ===== Tests =====


class TestCreateEvaluation:
    def test_returns_202(self, client):
        r = client.post("/api/v1/evaluations", json=_valid_payload())
        assert r.status_code == 202

    def test_response_shape(self, client):
        r = client.post("/api/v1/evaluations", json=_valid_payload())
        body = r.json()
        assert "evaluation_id" in body
        assert body["status"] == "pending"
        UUID(body["evaluation_id"])

    def test_inserts_evaluation_and_inputs(self, client, fake_db_session):
        client.post("/api/v1/evaluations", json=_valid_payload())
        # session.add se llamó 2 veces (Evaluation + EvaluationInput)
        assert fake_db_session.add.call_count >= 2
        fake_db_session.flush.assert_awaited()

    def test_validates_required_fields(self, client):
        payload = _valid_payload()
        del payload["product_name"]
        r = client.post("/api/v1/evaluations", json=payload)
        assert r.status_code == 422

    def test_rejects_negative_target_price(self, client):
        r = client.post(
            "/api/v1/evaluations", json=_valid_payload(target_price="-1.00")
        )
        assert r.status_code == 422

    def test_rejects_zero_target_price(self, client):
        r = client.post(
            "/api/v1/evaluations", json=_valid_payload(target_price="0.00")
        )
        assert r.status_code == 422

    def test_rejects_zero_units(self, client):
        r = client.post(
            "/api/v1/evaluations", json=_valid_payload(estimated_units_month=0)
        )
        assert r.status_code == 422

    def test_rejects_extra_fields(self, client):
        r = client.post(
            "/api/v1/evaluations", json=_valid_payload(unknown_field="hack")
        )
        assert r.status_code == 422

    def test_rejects_invalid_category(self, client):
        r = client.post(
            "/api/v1/evaluations", json=_valid_payload(category="digital")
        )
        assert r.status_code == 422


class TestGetEvaluation:
    def test_returns_404_when_not_found(self, client):
        eval_id = str(uuid4())
        r = client.get(f"/api/v1/evaluations/{eval_id}")
        assert r.status_code == 404

    def test_returns_detail_when_found(self, client, fake_db_session):
        from db.models import Evaluation as EvaluationModel

        ev = EvaluationModel(
            id=uuid4(),
            created_by=TEST_USER_ID,
            name="Test",
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        ev.agent_results = []
        ev.inputs = MagicMock(product_name="Smartwatch")

        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=ev)
        fake_db_session.execute = AsyncMock(return_value=result_mock)

        r = client.get(f"/api/v1/evaluations/{ev.id}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == str(ev.id)
        assert body["status"] == "pending"
        assert set(body["progress"].keys()) == {
            "financiero",
            "mercado",
            "riesgo",
            "estrategia",
        }


class TestListEvaluations:
    def test_empty_list(self, client):
        r = client.get("/api/v1/evaluations")
        assert r.status_code == 200
        assert r.json() == []

    def test_rejects_invalid_limit(self, client):
        r = client.get("/api/v1/evaluations?limit=0")
        assert r.status_code == 400

    def test_rejects_invalid_offset(self, client):
        r = client.get("/api/v1/evaluations?offset=-1")
        assert r.status_code == 400


class TestBackgroundTaskRegistered:
    def test_background_task_added_on_post(self, monkeypatch, client):
        captured = []
        from fastapi import BackgroundTasks

        original = BackgroundTasks.add_task

        def spy_add(self, fn, *args, **kw):
            captured.append((fn, args))
            return original(self, fn, *args, **kw)

        monkeypatch.setattr(BackgroundTasks, "add_task", spy_add)

        r = client.post("/api/v1/evaluations", json=_valid_payload())
        assert r.status_code == 202
        assert len(captured) == 1
        fn, args = captured[0]
        assert callable(fn)
        assert isinstance(args[0], UUID)
