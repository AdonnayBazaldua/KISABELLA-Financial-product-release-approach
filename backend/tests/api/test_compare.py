"""Tests del endpoint GET /api/v1/evaluations/compare."""

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
from core.config import Settings, get_settings, get_settings as _original_get_settings
from db.models import AgentResult as AgentResultRow
from db.models import Evaluation as EvaluationModel
from db.session import get_db


# ===== Helpers =====


TEST_USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def _agent_result_fixture(score: int = 75) -> AgentResult:
    return AgentResult(
        score=score,
        veredicto_corto="veredicto de prueba",
        analisis_extenso="x" * 400,
        hallazgos_clave=["hallazgo"],
        recomendaciones=["recomendacion"],
    )


def _make_complete_evaluation(eval_id: UUID | None = None) -> EvaluationModel:
    """Crea un mock de Evaluation completa con agent_results e inputs."""
    eid = eval_id or uuid4()
    ev = EvaluationModel(
        id=eid,
        created_by=TEST_USER_ID,
        name="Test completa",
        status="complete",
        final_verdict="viable",
        final_score=78,
        final_summary="Producto viable",
        error_message=None,
        warn_flags=[],
        requires_human_review=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    # Mock agent_results (4 agentes)
    ev.agent_results = [
        MagicMock(
            agent_name=name,
            score=75,
            veredicto_corto="ok",
            analisis_extenso="a" * 400,
            hallazgos_clave=["h1"],
            recomendaciones=["r1"],
        )
        for name in ("financiero", "mercado", "riesgo", "estrategia")
    ]
    ev.inputs = MagicMock(product_name="Smartwatch X1")
    return ev


def _make_pending_evaluation(eval_id: UUID | None = None) -> EvaluationModel:
    """Crea un mock de Evaluation en status pending."""
    eid = eval_id or uuid4()
    ev = EvaluationModel(
        id=eid,
        created_by=TEST_USER_ID,
        name="Test pendiente",
        status="pending",
        final_verdict=None,
        final_score=None,
        final_summary=None,
        error_message=None,
        warn_flags=[],
        requires_human_review=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    ev.agent_results = []
    ev.inputs = MagicMock(product_name="Producto pendiente")
    return ev


# ===== Fixtures =====


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
    """Mock AsyncSession por defecto retorna None (not found)."""
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
    _original_get_settings.cache_clear()

    async def _fake_dispose():
        return None

    monkeypatch.setattr(session_module, "dispose_engine", _fake_dispose)

    for mod_name in ("main", "api.v1.evaluations", "db.session"):
        mod = __import__(mod_name, fromlist=["get_settings"])
        if hasattr(mod, "get_settings"):
            monkeypatch.setattr(mod, "get_settings", lambda: fake_settings)

    import main as main_module

    app = main_module.create_app()

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


class TestCompareValidation:
    """Tests de validacion de input del endpoint compare."""

    def test_single_id_returns_400(self, client):
        """1 ID es insuficiente para comparar."""
        single_id = str(uuid4())
        r = client.get(f"/api/v1/evaluations/compare?ids={single_id}")
        assert r.status_code == 400

    def test_four_ids_returns_400(self, client):
        """4 IDs exceden el maximo de 3."""
        ids = ",".join(str(uuid4()) for _ in range(4))
        r = client.get(f"/api/v1/evaluations/compare?ids={ids}")
        assert r.status_code == 400

    def test_invalid_uuid_returns_400(self, client):
        """UUIDs malformados producen 400."""
        r = client.get("/api/v1/evaluations/compare?ids=not-a-uuid,also-bad")
        assert r.status_code == 400

    def test_empty_ids_returns_400(self, client):
        """Parametro ids vacio produce 400 (0 IDs < 2)."""
        r = client.get("/api/v1/evaluations/compare?ids=")
        assert r.status_code == 400

    def test_missing_ids_param_returns_422(self, client):
        """Sin parametro ids produce 422 (required query param)."""
        r = client.get("/api/v1/evaluations/compare")
        assert r.status_code == 422


class TestCompareNotFound:
    """Tests cuando evaluaciones no existen."""

    def test_nonexistent_ids_returns_404(self, client):
        """2 IDs que no existen en DB producen 404."""
        ids = ",".join(str(uuid4()) for _ in range(2))
        r = client.get(f"/api/v1/evaluations/compare?ids={ids}")
        assert r.status_code == 404


class TestCompareIncomplete:
    """Tests cuando evaluaciones existen pero no estan completas."""

    def test_pending_evaluation_returns_400(self, client, fake_db_session):
        """Una evaluacion pendiente produce 400."""
        pending_ev = _make_pending_evaluation()
        complete_ev = _make_complete_evaluation()

        call_count = 0
        evaluations = [pending_ev, complete_ev]

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count < len(evaluations):
                result.scalar_one_or_none = MagicMock(
                    return_value=evaluations[call_count]
                )
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            call_count += 1
            return result

        fake_db_session.execute = AsyncMock(side_effect=_side_effect)

        ids = f"{pending_ev.id},{complete_ev.id}"
        r = client.get(f"/api/v1/evaluations/compare?ids={ids}")
        assert r.status_code == 400
        assert "no esta completa" in r.json()["detail"]


class TestCompareSuccess:
    """Tests del happy path."""

    def test_two_complete_evaluations_returns_200(self, client, fake_db_session):
        """2 evaluaciones completas retornan 200 con lista de 2 details."""
        ev1 = _make_complete_evaluation()
        ev2 = _make_complete_evaluation()

        call_count = 0
        evaluations = [ev1, ev2]

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count < len(evaluations):
                result.scalar_one_or_none = MagicMock(
                    return_value=evaluations[call_count]
                )
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            call_count += 1
            return result

        fake_db_session.execute = AsyncMock(side_effect=_side_effect)

        ids = f"{ev1.id},{ev2.id}"
        r = client.get(f"/api/v1/evaluations/compare?ids={ids}")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert len(body) == 2
        assert body[0]["id"] == str(ev1.id)
        assert body[1]["id"] == str(ev2.id)
        assert body[0]["status"] == "complete"
        assert body[1]["status"] == "complete"

    def test_three_complete_evaluations_returns_200(self, client, fake_db_session):
        """3 evaluaciones completas retornan 200 con lista de 3 details."""
        ev1 = _make_complete_evaluation()
        ev2 = _make_complete_evaluation()
        ev3 = _make_complete_evaluation()

        call_count = 0
        evaluations = [ev1, ev2, ev3]

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count < len(evaluations):
                result.scalar_one_or_none = MagicMock(
                    return_value=evaluations[call_count]
                )
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            call_count += 1
            return result

        fake_db_session.execute = AsyncMock(side_effect=_side_effect)

        ids = f"{ev1.id},{ev2.id},{ev3.id}"
        r = client.get(f"/api/v1/evaluations/compare?ids={ids}")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 3

    def test_response_contains_agent_results(self, client, fake_db_session):
        """Cada evaluacion en la respuesta incluye agent_results y progress."""
        ev1 = _make_complete_evaluation()
        ev2 = _make_complete_evaluation()

        call_count = 0
        evaluations = [ev1, ev2]

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count < len(evaluations):
                result.scalar_one_or_none = MagicMock(
                    return_value=evaluations[call_count]
                )
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            call_count += 1
            return result

        fake_db_session.execute = AsyncMock(side_effect=_side_effect)

        ids = f"{ev1.id},{ev2.id}"
        r = client.get(f"/api/v1/evaluations/compare?ids={ids}")
        assert r.status_code == 200
        body = r.json()
        for detail in body:
            assert "agent_results" in detail
            assert "progress" in detail
            assert len(detail["agent_results"]) == 4
            assert set(detail["progress"].keys()) == {
                "financiero",
                "mercado",
                "riesgo",
                "estrategia",
            }


class TestCompareRouteOrder:
    """Verifica que /compare no sea capturado por /{eval_id}."""

    def test_compare_route_not_captured_by_eval_id(self, client):
        """GET /evaluations/compare NO debe matchear como eval_id UUID."""
        # If route order is wrong, this would return 422 (invalid UUID)
        # instead of the expected behavior from our compare endpoint
        r = client.get("/api/v1/evaluations/compare?ids=not-a-uuid,also-bad")
        # Should be 400 from our endpoint, not 422 from UUID parsing of "compare"
        assert r.status_code == 400
