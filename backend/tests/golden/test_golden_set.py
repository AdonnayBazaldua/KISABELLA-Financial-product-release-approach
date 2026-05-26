"""Regression tests con golden set — 5 escenarios end-to-end con FakeLLMClient."""

from datetime import datetime, timezone

import pytest

from agents.contracts import (
    AgentResult,
    EvaluationInputs,
    FinalVerdict,
    TCMetadata,
)
from agents.llm_client import FakeLLMClient
from agents.pipeline import run_evaluation
from tests.golden.fixtures import GOLDEN_FIXTURES


def _make_agent_result(score: int = 75) -> AgentResult:
    """Construye un AgentResult válido para usar en FakeLLMClient."""
    return AgentResult(
        score=score,
        veredicto_corto="veredicto de prueba golden set",
        analisis_extenso="a" * 400,
        hallazgos_clave=["hallazgo de prueba"],
        recomendaciones=["recomendacion de prueba"],
    )


def _inputs_from_fixture(fixture: dict) -> EvaluationInputs:
    raw = fixture["inputs"].copy()
    raw["exchange_rate_at"] = datetime(2026, 5, 25, tzinfo=timezone.utc)
    raw["tc_source"] = "user_provided"
    return EvaluationInputs(**raw)


def _tc_meta() -> TCMetadata:
    return TCMetadata(
        rate=19.5,
        source="user_provided",
        fetched_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize(
    "fixture",
    GOLDEN_FIXTURES,
    ids=[f["id"] for f in GOLDEN_FIXTURES],
)
@pytest.mark.asyncio
async def test_golden_pipeline(fixture):
    """Pipeline completo produce veredicto en rango esperado."""
    llm = FakeLLMClient()
    # Queue 4 responses — una por agente (financiero ignora el score via calc override).
    # Orden de ejecución paralela no garantizado, pero los 4 agentes hacen 1 call cada uno.
    llm.queue_responses([_make_agent_result(score=75) for _ in range(4)])

    inputs = _inputs_from_fixture(fixture)

    state = await run_evaluation(inputs, _tc_meta(), llm)

    verdict: FinalVerdict = state["final_verdict"]
    assert verdict is not None, f"No verdict for fixture {fixture['id']}"

    lo, hi = fixture["expected_score_range"]
    assert lo <= verdict.score_final <= hi, (
        f"Score {verdict.score_final} fuera de rango [{lo}, {hi}] "
        f"para fixture {fixture['id']}"
    )

    # Verify verdict is one of the valid literals
    assert verdict.veredicto in ("viable", "viable_con_ajustes", "no_viable"), (
        f"Veredicto inválido: {verdict.veredicto}"
    )

    # Verify all 4 agent results present
    agent_results = state.get("agent_results", {})
    assert len(agent_results) == 4, (
        f"Expected 4 agent results, got {len(agent_results)}"
    )
    for name in ("financiero", "mercado", "riesgo", "estrategia"):
        assert name in agent_results, f"Missing agent: {name}"
