"""Tests E2E del pipeline LangGraph con FakeLLMClient."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from agents.contracts import (
    AgentError,
    AgentResult,
    EvaluationInputs,
    OrchestratorSynthesis,
    TCMetadata,
)
from agents.llm_client import FakeLLMClient
from agents.pipeline import build_pipeline, run_evaluation


def _make_inputs(**overrides) -> EvaluationInputs:
    base = dict(
        product_name="Producto E2E",
        category="fisico",
        cost_purchase=Decimal("100.00"),
        cost_freight=Decimal("10.00"),
        cost_customs=Decimal("15.00"),
        cost_storage=Decimal("0.00"),
        cost_logistics_vehicle=Decimal("0.00"),
        cost_logistics_viaticos=Decimal("0.00"),
        cost_logistics_personnel=Decimal("0.00"),
        cost_shrinkage_pct=Decimal("0.00"),
        cost_commission_pct=Decimal("0.00"),
        cost_marketing=Decimal("0.00"),
        cost_overhead=Decimal("0.00"),
        target_price=Decimal("200.00"),
        estimated_units_month=100,
        exchange_rate_used=Decimal("19.8500"),
        exchange_rate_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return EvaluationInputs(**base)


def _make_tc() -> TCMetadata:
    return TCMetadata(
        rate=Decimal("19.8500"),
        source="banxico",
        fetched_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
    )


def _agent_result(score: int = 75) -> AgentResult:
    return AgentResult(
        score=score,
        veredicto_corto="veredicto valido para test",
        analisis_extenso="x" * 400,
        hallazgos_clave=["hallazgo"],
        recomendaciones=["recomendacion"],
    )


def _orchestrator_synthesis() -> OrchestratorSynthesis:
    return OrchestratorSynthesis(justificacion="S" * 150)


class TestPipelineE2EAllOK:
    async def test_all_four_agents_run_in_parallel(self):
        fake = FakeLLMClient()
        # 4 respuestas para agentes + 1 OrchestratorSynthesis para el orquestador
        fake.queue_responses(
            [
                _agent_result(score=10),  # financiero LLM (sobrescrito por calc)
                _agent_result(score=80),  # mercado
                _agent_result(score=75),  # riesgo
                _agent_result(score=70),  # estrategia
                _orchestrator_synthesis(),  # orquestador LLM call
            ]
        )

        final_state = await run_evaluation(_make_inputs(), _make_tc(), fake)

        results = final_state["agent_results"]
        assert len(results) == 4
        assert set(results.keys()) == {
            "financiero",
            "mercado",
            "riesgo",
            "estrategia",
        }
        # Todos son AgentResult, ninguno AgentError
        assert all(isinstance(v, AgentResult) for v in results.values())

    async def test_financiero_score_overridden_by_calc(self):
        fake = FakeLLMClient()
        # Caso "excelente" → score_from_calculations = 100
        fake.queue_responses(
            [_agent_result(score=10) for _ in range(4)]  # LLM scores irrelevantes
            + [_orchestrator_synthesis()]
        )

        final_state = await run_evaluation(_make_inputs(), _make_tc(), fake)
        financiero = final_state["agent_results"]["financiero"]
        assert isinstance(financiero, AgentResult)
        # LLM dijo 10, pero calc override puso ~100 (caso excelente)
        assert financiero.score >= 70

    async def test_other_agents_use_llm_score(self):
        fake = FakeLLMClient()
        fake.queue_responses(
            [
                _agent_result(score=10),  # financiero (sobrescrito)
                _agent_result(score=88),  # mercado
                _agent_result(score=66),  # riesgo
                _agent_result(score=44),  # estrategia
                _orchestrator_synthesis(),  # orquestador LLM call
            ]
        )

        final_state = await run_evaluation(_make_inputs(), _make_tc(), fake)
        results = final_state["agent_results"]
        # En orden NO determinístico — verificamos por nombre
        assert isinstance(results["mercado"], AgentResult)
        # FakeLLMClient FIFO → orden de queue == orden de llamada
        # Pero el orden de llamada paralela no está garantizado.
        # En cambio verificamos que los scores entregados son los del queue
        all_scores = {results[n].score for n in ("mercado", "riesgo", "estrategia")}
        assert all_scores == {88, 66, 44}

    async def test_final_verdict_emitted(self):
        fake = FakeLLMClient()
        fake.queue_responses(
            [_agent_result(score=80) for _ in range(4)]
            + [_orchestrator_synthesis()]
        )

        final_state = await run_evaluation(_make_inputs(), _make_tc(), fake)
        verdict = final_state["final_verdict"]
        assert verdict is not None
        assert verdict.veredicto in ("viable", "viable_con_ajustes", "no_viable")
        assert 0 <= verdict.score_final <= 100


class TestPipelineDegradation:
    async def test_one_agent_fails_pipeline_continues(self):
        from anthropic import RateLimitError
        from unittest.mock import MagicMock

        fake = FakeLLMClient()
        # 4 calls: 3 succeed, uno falla con excepción + 1 synthesis (3 OK triggers LLM)
        fake.queue_responses(
            [
                _agent_result(score=80),
                _agent_result(score=70),
                _agent_result(score=75),
            ]
        )
        fake.queue_exception(
            RateLimitError("simulated", response=MagicMock(), body=None)
        )
        fake.queue_responses([_orchestrator_synthesis()])

        final_state = await run_evaluation(_make_inputs(), _make_tc(), fake)

        results = final_state["agent_results"]
        assert len(results) == 4
        # 3 OK, 1 Error
        errors = [v for v in results.values() if isinstance(v, AgentError)]
        oks = [v for v in results.values() if isinstance(v, AgentResult)]
        assert len(errors) == 1
        assert len(oks) == 3

        # Verdict aún se emite
        assert final_state["final_verdict"] is not None

    async def test_all_agents_fail_no_viable(self):
        from anthropic import APIConnectionError
        from unittest.mock import MagicMock

        fake = FakeLLMClient()
        # Las 4 calls fallan
        for _ in range(4):
            fake.queue_exception(APIConnectionError(request=MagicMock()))

        final_state = await run_evaluation(_make_inputs(), _make_tc(), fake)

        results = final_state["agent_results"]
        # Todos son AgentError
        assert all(isinstance(v, AgentError) for v in results.values())

        verdict = final_state["final_verdict"]
        assert verdict.veredicto == "no_viable"
        assert verdict.requires_human_review is True


class TestPipelineBuildable:
    def test_build_returns_compiled_graph(self):
        fake = FakeLLMClient()
        graph = build_pipeline(fake)
        # LangGraph CompiledGraph tiene ainvoke
        assert hasattr(graph, "ainvoke")


class TestPipelineWebWarning:
    """Seam 3: sin resultados de Tavily el veredicto lleva warn_no_web (CLAUDE.md, Timeouts)."""

    async def _run(self, monkeypatch, web_result: str):
        async def fake_search(*a, **kw):
            return web_result

        monkeypatch.setattr("agents.market.search_web", fake_search)
        fake = FakeLLMClient()
        fake.queue_responses([_agent_result()] * 4 + [_orchestrator_synthesis()])
        state = await run_evaluation(_make_inputs(), _make_tc(), fake)
        return state["final_verdict"]

    async def test_no_web_results_flags_warn_no_web(self, monkeypatch):
        verdict = await self._run(monkeypatch, "")
        assert "warn_no_web" in verdict.warn_flags

    async def test_web_results_present_no_flag(self, monkeypatch):
        verdict = await self._run(monkeypatch, "## resultados de búsqueda")
        assert "warn_no_web" not in verdict.warn_flags
