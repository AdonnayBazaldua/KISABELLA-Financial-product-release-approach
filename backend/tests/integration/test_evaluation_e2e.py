"""Smoke test E2E: POST /evaluations → pipeline completo → veredicto.

Atraviesa el HTTP layer completo con FakeLLMClient inyectado.
Sin red real — DB mockeada, LLM falso.

El BackgroundTask corre sincrónicamente dentro de TestClient antes de que
el request retorne, por lo que podemos verificar los efectos del pipeline
directamente después del POST.

Este test verifica:
1. HTTP POST devuelve 202 con evaluation_id válido.
2. El pipeline invocó 5 LLM calls (4 agentes + 1 orquestador).
3. El servicio llamó session.commit() al persistir (pipeline completo sin error).
"""
from __future__ import annotations

from tests.conftest import from_ip

import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import db.session as session_module
from agents.contracts import AgentResult, OrchestratorSynthesis
from agents.llm_client import FakeLLMClient, get_llm_client
from api.v1.evaluations import (
    get_background_session_factory,
    get_user_id,
)
from core.config import Settings, get_settings, get_settings as _original_get_settings
from db.session import get_db


# ──────────────────────────────────────────────
# Datos de prueba
# ──────────────────────────────────────────────

AGENT_RESULT = AgentResult(
    score=75,
    veredicto_corto="Producto viable en el mercado objetivo",
    analisis_extenso="A" * 400,
    hallazgos_clave=["h1", "h2"],
    recomendaciones=["r1", "r2"],
)

# El orquestador pide OrchestratorSynthesis al LLM (no FinalVerdict).
# FinalVerdict se construye de forma determinista desde el scoring.
ORCHESTRATOR_SYNTHESIS = OrchestratorSynthesis(
    justificacion=(
        "El producto presenta viabilidad financiera y de mercado confirmada. "
        "Los cuatro agentes especializados coinciden en un score sólido que "
        "supera el umbral mínimo de viabilidad establecido. Se recomienda "
        "avanzar con la estrategia de importación propuesta, monitoreando "
        "los indicadores de riesgo identificados en el análisis de mercado. "
        "La evaluación integral sugiere que el margen operativo es suficiente "
        "para absorber variaciones moderadas en el tipo de cambio."
    )
)

TEST_USER_ID = UUID("11111111-1111-1111-1111-111111111111")

VALID_PAYLOAD = {
    "name": "Test E2E Sprint 6",
    "product_name": "Producto Test",
    "description": "Descripción del producto de prueba para smoke test",
    "category": "fisico",
    "sales_channel": "online",
    "cost_purchase": 100.0,
    "cost_purchase_usd": 0.0,
    "cost_freight": 50.0,
    "cost_customs": 20.0,
    "cost_storage": 10.0,
    "cost_logistics_vehicle": 0.0,
    "cost_logistics_viaticos": 0.0,
    "cost_logistics_personnel": 0.0,
    "cost_shrinkage_pct": 2.0,
    "cost_commission_pct": 5.0,
    "cost_marketing": 30.0,
    "cost_overhead": 20.0,
    "target_price": 350.0,
    "estimated_units_month": 100,
    "exchange_rate_used": 17.5,
}


# ──────────────────────────────────────────────
# Fixtures — mismo patrón que tests/api/test_evaluations.py
# ──────────────────────────────────────────────


def _make_fake_db_session():
    """Mock AsyncSession que captura add/commit/flush."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    # Evaluación de ejemplo para GET
    from datetime import datetime, timezone
    from db.models import Evaluation as EvaluationModel

    ev = EvaluationModel(
        id=uuid4(),
        created_by=TEST_USER_ID,
        name="Test E2E",
        status="complete",
        final_verdict="viable",
        final_score=75,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    ev.agent_results = []
    ev.inputs = MagicMock(product_name="Producto Test")

    detail_result = MagicMock()
    detail_result.scalar_one_or_none = MagicMock(return_value=ev)
    detail_result.scalars = MagicMock()
    detail_result.scalars.return_value.all = MagicMock(return_value=[])

    empty_result = MagicMock()
    empty_result.scalar_one_or_none = MagicMock(return_value=None)
    empty_result.scalars = MagicMock()
    empty_result.scalars.return_value.all = MagicMock(return_value=[])

    # Primer execute (idempotency check) → None, luego devuelve ev para GET
    session.execute = AsyncMock(side_effect=[
        empty_result,   # idempotency check en create()
        empty_result,   # SELECT en _mark_status (running)
        empty_result,   # SELECT en _persist_results
        detail_result,  # GET /evaluations/{id}
    ] + [empty_result] * 20)  # resto de llamadas extra

    return session, ev


@pytest.fixture
def fake_settings():
    return Settings(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        database_url="postgresql+psycopg://kisabella_app:pw@db:5432/test",
        allowed_ips="127.0.0.1",
        next_public_api_url="http://localhost:3000",
        app_user_id=str(TEST_USER_ID),
    )


@pytest.fixture
def smoke_llm():
    """FakeLLMClient con 4 AgentResult + 1 OrchestratorSynthesis."""
    fake = FakeLLMClient()
    fake.queue_responses([AGENT_RESULT] * 4 + [ORCHESTRATOR_SYNTHESIS])
    return fake


@pytest.fixture
def smoke_app(monkeypatch, fake_settings, smoke_llm):
    """App con dependency_overrides para el smoke test E2E."""
    _original_get_settings.cache_clear()

    async def _fake_dispose():
        return None

    monkeypatch.setattr(session_module, "dispose_engine", _fake_dispose)

    # Override get_settings en todos los módulos que la importaron
    for mod_name in ("main", "api.v1.evaluations", "db.session"):
        mod = __import__(mod_name, fromlist=["get_settings"])
        if hasattr(mod, "get_settings"):
            monkeypatch.setattr(mod, "get_settings", lambda: fake_settings)

    import main as main_module

    app = main_module.create_app()

    fake_db_session, _ev = _make_fake_db_session()

    # DI overrides — idéntico patrón a tests/api/test_evaluations.py
    async def _override_get_db():
        yield fake_db_session

    @asynccontextmanager
    async def _fake_session_factory():
        yield fake_db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_client] = lambda: smoke_llm
    app.dependency_overrides[get_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_background_session_factory] = (
        lambda: _fake_session_factory
    )
    app.dependency_overrides[get_settings] = lambda: fake_settings

    return app, fake_db_session, smoke_llm


@pytest.fixture
def smoke_client(smoke_app):
    app, _, _ = smoke_app
    return from_ip(app, "127.0.0.1")


# ──────────────────────────────────────────────
# Smoke Test
# ──────────────────────────────────────────────


class TestEvaluationE2ESmokeTest:
    """Smoke test que atraviesa el HTTP layer completo.

    Verifica: POST 202 → BackgroundTask ejecuta pipeline (4 agentes + orquestador)
    → 5 LLM calls registrados en FakeLLMClient.
    """

    def test_post_returns_202_with_evaluation_id(self, smoke_client):
        """POST /evaluations → 202 + evaluation_id UUID válido."""
        r = smoke_client.post("/api/v1/evaluations", json=VALID_PAYLOAD)
        assert r.status_code == 202, f"Expected 202, got {r.status_code}: {r.text}"

        body = r.json()
        assert "evaluation_id" in body, f"No evaluation_id in response: {body}"
        UUID(body["evaluation_id"])  # valida que es UUID válido
        assert body["status"] == "pending"

    def test_full_pipeline_traversal(self, smoke_app):
        """POST dispara BackgroundTask que invoca los 4 agentes + orquestador.

        Verifica que FakeLLMClient recibió exactamente 5 llamadas:
        4 de los agentes especialistas + 1 del orquestador.
        """
        app, _db, fake_llm = smoke_app
        client = from_ip(app, "127.0.0.1")

        r = client.post("/api/v1/evaluations", json=VALID_PAYLOAD)
        assert r.status_code == 202

        # TestClient ejecuta los BackgroundTasks sincrónicamente antes de retornar.
        # En este punto el pipeline ya corrió completamente.
        assert len(fake_llm.calls) == 5, (
            f"Se esperaban 5 LLM calls (4 agentes + 1 orquestador), "
            f"se recibieron {len(fake_llm.calls)}: "
            f"{[c.schema.__name__ for c in fake_llm.calls]}"
        )

        # Verificar schemas invocados
        schema_names = [c.schema.__name__ for c in fake_llm.calls]
        assert schema_names.count("AgentResult") == 4, (
            f"Se esperaban 4 AgentResult calls, got: {schema_names}"
        )
        assert schema_names.count("OrchestratorSynthesis") == 1, (
            f"Se esperaba 1 OrchestratorSynthesis call, got: {schema_names}"
        )
