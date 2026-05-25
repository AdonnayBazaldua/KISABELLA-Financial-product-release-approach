"""Tests para agents.orchestrator — synthesize_verdict."""

import pytest

from agents.contracts import AgentError, AgentResult, PipelineState
from agents.orchestrator import synthesize_verdict


def _ar(score: int) -> AgentResult:
    return AgentResult(
        score=score,
        veredicto_corto="veredicto valido para test",
        analisis_extenso="x" * 400,
        hallazgos_clave=["h"],
        recomendaciones=["r"],
    )


def _err(name) -> AgentError:
    return AgentError(
        agent_name=name, error_type="timeout", error_message="test fail"
    )


def _state(results: dict) -> PipelineState:
    return {"agent_results": results, "warn_flags": []}


class TestSynthesizeAllOK:
    def test_high_scores_viable(self):
        state = _state(
            {
                "financiero": _ar(85),
                "mercado": _ar(80),
                "riesgo": _ar(80),
                "estrategia": _ar(80),
            }
        )
        v = synthesize_verdict(state)
        assert v.veredicto == "viable"
        assert v.score_final >= 75
        assert v.confidence == "high"
        assert v.requires_human_review is False

    def test_mid_scores_con_ajustes(self):
        state = _state(
            {
                "financiero": _ar(60),
                "mercado": _ar(60),
                "riesgo": _ar(55),
                "estrategia": _ar(50),
            }
        )
        v = synthesize_verdict(state)
        # weighted ≈ 60*0.35+60*0.25+55*0.20+50*0.20 = 21+15+11+10 = 57 → con_ajustes
        assert v.veredicto == "viable_con_ajustes"
        assert v.confidence == "high"  # 4 OK


class TestDegradedThree:
    def test_three_ok_confidence_medium(self):
        state = _state(
            {
                "financiero": _ar(85),
                "mercado": _ar(80),
                "riesgo": _ar(75),
                "estrategia": _err("estrategia"),
            }
        )
        v = synthesize_verdict(state)
        # 3 OK → no es degraded, va por verdict_from_score
        assert v.confidence == "medium"
        assert v.requires_human_review is False
        assert v.veredicto == "viable"


class TestDegradedTwoOrLess:
    def test_two_ok_con_ajustes_review(self):
        state = _state(
            {
                "financiero": _ar(90),
                "mercado": _ar(85),
                "riesgo": _err("riesgo"),
                "estrategia": _err("estrategia"),
            }
        )
        v = synthesize_verdict(state)
        assert v.veredicto == "viable_con_ajustes"
        assert v.requires_human_review is True
        assert v.confidence == "low"

    def test_one_ok_no_viable(self):
        state = _state(
            {
                "financiero": _ar(95),
                "mercado": _err("mercado"),
                "riesgo": _err("riesgo"),
                "estrategia": _err("estrategia"),
            }
        )
        v = synthesize_verdict(state)
        assert v.veredicto == "no_viable"
        assert v.requires_human_review is True

    def test_all_failed_no_viable(self):
        state = _state(
            {
                "financiero": _err("financiero"),
                "mercado": _err("mercado"),
                "riesgo": _err("riesgo"),
                "estrategia": _err("estrategia"),
            }
        )
        v = synthesize_verdict(state)
        assert v.veredicto == "no_viable"
        assert v.score_final == 0


class TestJustificacionContent:
    def test_includes_summary_per_agent(self):
        state = _state(
            {
                "financiero": _ar(85),
                "mercado": _ar(80),
                "riesgo": _ar(75),
                "estrategia": _ar(70),
            }
        )
        v = synthesize_verdict(state)
        assert "financiero" in v.justificacion
        assert "mercado" in v.justificacion
        assert "riesgo" in v.justificacion
        assert "estrategia" in v.justificacion

    def test_mentions_failed_agents(self):
        state = _state(
            {
                "financiero": _ar(85),
                "mercado": _err("mercado"),
                "riesgo": _ar(75),
                "estrategia": _ar(70),
            }
        )
        v = synthesize_verdict(state)
        assert "falló" in v.justificacion or "fall" in v.justificacion


class TestWarnFlagsPropagation:
    def test_propagates_from_state(self):
        state: PipelineState = {
            "agent_results": {
                "financiero": _ar(85),
                "mercado": _ar(80),
                "riesgo": _ar(80),
                "estrategia": _ar(80),
            },
            "warn_flags": ["warn_fx", "warn_no_web"],
        }
        v = synthesize_verdict(state)
        assert "warn_fx" in v.warn_flags
        assert "warn_no_web" in v.warn_flags
