"""Tests para agents.calculations.scoring."""

import pytest

from agents.calculations.scoring import (
    AGENT_WEIGHTS,
    count_ok,
    degraded_verdict,
    verdict_from_score,
    weighted_final_score,
)
from agents.contracts import AgentError, AgentResult


def _ar(score: int) -> AgentResult:
    return AgentResult(
        score=score,
        veredicto_corto="veredicto valido para test",
        analisis_extenso="x" * 350,
        hallazgos_clave=["uno"],
        recomendaciones=["uno"],
    )


def _err(name) -> AgentError:
    return AgentError(
        agent_name=name, error_type="timeout", error_message="test fail"
    )


class TestWeights:
    def test_sum_to_one(self):
        assert sum(AGENT_WEIGHTS.values()) == 1

    def test_financiero_is_dominant(self):
        assert AGENT_WEIGHTS["financiero"] > AGENT_WEIGHTS["mercado"]
        assert AGENT_WEIGHTS["mercado"] > AGENT_WEIGHTS["riesgo"]


class TestCountOk:
    def test_all_ok(self):
        results = {
            "financiero": _ar(70),
            "mercado": _ar(80),
            "riesgo": _ar(60),
            "estrategia": _ar(75),
        }
        assert count_ok(results) == 4

    def test_partial_failures(self):
        results = {
            "financiero": _ar(70),
            "mercado": _err("mercado"),
            "riesgo": _ar(60),
            "estrategia": _err("estrategia"),
        }
        assert count_ok(results) == 2

    def test_all_failed(self):
        results = {
            "financiero": _err("financiero"),
            "mercado": _err("mercado"),
        }
        assert count_ok(results) == 0


class TestWeightedScore:
    def test_all_ok_uses_full_weights(self):
        # Todos 80 → 80
        results = {
            "financiero": _ar(80),
            "mercado": _ar(80),
            "riesgo": _ar(80),
            "estrategia": _ar(80),
        }
        assert weighted_final_score(results) == 80

    def test_renormalizes_on_partial(self):
        # Solo Mercado OK con 100 → score = 100 (renormalizado sobre peso 0.25)
        results = {
            "mercado": _ar(100),
            "financiero": _err("financiero"),
            "riesgo": _err("riesgo"),
            "estrategia": _err("estrategia"),
        }
        assert weighted_final_score(results) == 100

    def test_weighted_correctly(self):
        # Financiero 100 (0.35), resto 50 (0.65) → 100*0.35 + 50*0.65 = 35+32.5 = 67.5 → 68
        results = {
            "financiero": _ar(100),
            "mercado": _ar(50),
            "riesgo": _ar(50),
            "estrategia": _ar(50),
        }
        assert weighted_final_score(results) == 68

    def test_zero_when_all_failed(self):
        results = {
            "financiero": _err("financiero"),
            "mercado": _err("mercado"),
        }
        assert weighted_final_score(results) == 0


class TestDegradedVerdict:
    def test_one_ok_is_no_viable(self):
        results = {
            "financiero": _ar(90),
            "mercado": _err("mercado"),
            "riesgo": _err("riesgo"),
            "estrategia": _err("estrategia"),
        }
        v, rhr, conf = degraded_verdict(results, 90)
        assert v == "no_viable"
        assert rhr is True
        assert conf == "low"

    def test_zero_ok_is_no_viable(self):
        results = {
            "financiero": _err("financiero"),
            "mercado": _err("mercado"),
            "riesgo": _err("riesgo"),
            "estrategia": _err("estrategia"),
        }
        v, rhr, _ = degraded_verdict(results, 0)
        assert v == "no_viable"
        assert rhr is True

    def test_two_ok_is_con_ajustes(self):
        results = {
            "financiero": _ar(80),
            "mercado": _ar(80),
            "riesgo": _err("riesgo"),
            "estrategia": _err("estrategia"),
        }
        v, rhr, _ = degraded_verdict(results, 80)
        assert v == "viable_con_ajustes"
        assert rhr is True

    def test_three_ok_raises(self):
        """≥3 OK no debe llamar degraded_verdict — el LLM decide."""
        results = {
            "financiero": _ar(80),
            "mercado": _ar(80),
            "riesgo": _ar(80),
            "estrategia": _err("estrategia"),
        }
        with pytest.raises(ValueError, match="3 agentes"):
            degraded_verdict(results, 80)


class TestVerdictFromScore:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (100, "viable"),
            (80, "viable"),
            (75, "viable"),
            (74, "viable_con_ajustes"),
            (60, "viable_con_ajustes"),
            (50, "viable_con_ajustes"),
            (49, "no_viable"),
            (30, "no_viable"),
            (0, "no_viable"),
        ],
    )
    def test_thresholds(self, score, expected):
        assert verdict_from_score(score) == expected
