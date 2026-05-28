"""Tests para agents.orchestrator — synthesize_verdict async con LLM."""

import pytest

from agents.contracts import (
    AgentError,
    AgentResult,
    OrchestratorSynthesis,
    PipelineState,
)
from agents.llm_client import FakeLLMClient
from agents.orchestrator import synthesize_verdict


def _ar(score: int) -> AgentResult:
    return AgentResult(
        score=score,
        veredicto_corto="veredicto valido para test orquestador",
        analisis_extenso="x" * 400,
        hallazgos_clave=["hallazgo"],
        recomendaciones=["recomendacion"],
    )


def _err(name: str) -> AgentError:
    return AgentError(agent_name=name, error_type="timeout", error_message="test fail")


def _synth(text: str = "") -> OrchestratorSynthesis:
    body = text if len(text) >= 100 else "S" * 150
    return OrchestratorSynthesis(justificacion=body)


def _state(results: dict, flags: list | None = None) -> PipelineState:
    return {"agent_results": results, "warn_flags": flags or []}


class TestSynthesizeAllOKWithLLM:
    async def test_high_scores_viable_with_llm_justification(self):
        fake = FakeLLMClient()
        fake.set_response_for(OrchestratorSynthesis, _synth())
        state = _state({
            "financiero": _ar(85),
            "mercado": _ar(80),
            "riesgo": _ar(80),
            "estrategia": _ar(80),
        })
        v = await synthesize_verdict(state, fake)
        assert v.veredicto == "viable"
        assert v.score_final >= 75
        assert v.confidence == "high"
        assert v.requires_human_review is False
        assert len(v.justificacion) >= 100

    async def test_mid_scores_con_ajustes(self):
        fake = FakeLLMClient()
        fake.set_response_for(OrchestratorSynthesis, _synth())
        state = _state({
            "financiero": _ar(60),
            "mercado": _ar(60),
            "riesgo": _ar(55),
            "estrategia": _ar(50),
        })
        v = await synthesize_verdict(state, fake)
        assert v.veredicto == "viable_con_ajustes"
        assert v.confidence == "high"

    async def test_llm_called_when_3_or_more_ok(self):
        fake = FakeLLMClient()
        fake.set_response_for(OrchestratorSynthesis, _synth())
        state = _state({
            "financiero": _ar(85),
            "mercado": _ar(80),
            "riesgo": _ar(75),
            "estrategia": _ar(70),
        })
        await synthesize_verdict(state, fake)
        assert len(fake.calls) == 1
        assert fake.calls[0].schema == OrchestratorSynthesis


class TestSynthesizeLLMFallback:
    async def test_llm_failure_uses_mechanical_justification(self):
        fake = FakeLLMClient()
        fake.queue_exception(RuntimeError("LLM down"))
        state = _state({
            "financiero": _ar(85),
            "mercado": _ar(80),
            "riesgo": _ar(80),
            "estrategia": _ar(80),
        })
        v = await synthesize_verdict(state, fake)
        assert v.veredicto == "viable"
        assert len(v.justificacion) >= 100
        assert "Veredicto integrado" in v.justificacion


class TestSynthesizeDegraded:
    async def test_two_ok_no_llm_call(self):
        fake = FakeLLMClient()
        state = _state({
            "financiero": _ar(90),
            "mercado": _ar(85),
            "riesgo": _err("riesgo"),
            "estrategia": _err("estrategia"),
        })
        v = await synthesize_verdict(state, fake)
        assert v.veredicto == "viable_con_ajustes"
        assert v.requires_human_review is True
        assert v.confidence == "low"
        assert len(fake.calls) == 0

    async def test_one_ok_no_viable(self):
        fake = FakeLLMClient()
        state = _state({
            "financiero": _ar(95),
            "mercado": _err("mercado"),
            "riesgo": _err("riesgo"),
            "estrategia": _err("estrategia"),
        })
        v = await synthesize_verdict(state, fake)
        assert v.veredicto == "no_viable"
        assert v.requires_human_review is True
        assert len(fake.calls) == 0

    async def test_all_failed_no_viable(self):
        fake = FakeLLMClient()
        state = _state({
            "financiero": _err("financiero"),
            "mercado": _err("mercado"),
            "riesgo": _err("riesgo"),
            "estrategia": _err("estrategia"),
        })
        v = await synthesize_verdict(state, fake)
        assert v.veredicto == "no_viable"
        assert v.requires_human_review is True

    async def test_three_ok_confidence_medium(self):
        fake = FakeLLMClient()
        fake.set_response_for(OrchestratorSynthesis, _synth())
        state = _state({
            "financiero": _ar(85),
            "mercado": _ar(80),
            "riesgo": _ar(75),
            "estrategia": _err("estrategia"),
        })
        v = await synthesize_verdict(state, fake)
        assert v.confidence == "medium"
        assert v.requires_human_review is False
        assert v.veredicto == "viable"


class TestWarnFlagsPropagation:
    async def test_propagates_from_state(self):
        fake = FakeLLMClient()
        fake.set_response_for(OrchestratorSynthesis, _synth())
        state: PipelineState = {
            "agent_results": {
                "financiero": _ar(85),
                "mercado": _ar(80),
                "riesgo": _ar(80),
                "estrategia": _ar(80),
            },
            "warn_flags": ["warn_fx", "warn_no_web"],
        }
        v = await synthesize_verdict(state, fake)
        assert "warn_fx" in v.warn_flags
        assert "warn_no_web" in v.warn_flags
