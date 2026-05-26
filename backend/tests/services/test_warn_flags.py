"""Tests: warn_flags y requires_human_review se persisten desde FinalVerdict."""

import pytest

from agents.contracts import AgentResult, FinalVerdict, PipelineState


def _make_agent_result(score: int = 70) -> AgentResult:
    return AgentResult(
        score=score,
        veredicto_corto="Veredicto de prueba para validación del pipeline completo",
        analisis_extenso="A" * 350,
        hallazgos_clave=["hallazgo 1", "hallazgo 2", "hallazgo 3"],
        recomendaciones=["rec 1", "rec 2", "rec 3"],
    )


def test_persist_results_stores_warn_flags():
    """_persist_results debe guardar warn_flags del FinalVerdict en la row."""
    verdict = FinalVerdict(
        veredicto="viable_con_ajustes",
        score_final=65,
        justificacion="J" * 120,
        requires_human_review=True,
        confidence="medium",
        warn_flags=["warn_fx", "warn_no_web"],
    )
    assert verdict.warn_flags == ["warn_fx", "warn_no_web"]
    assert verdict.requires_human_review is True


def test_final_verdict_defaults():
    """FinalVerdict sin flags explícitos usa defaults limpios."""
    verdict = FinalVerdict(
        veredicto="viable",
        score_final=85,
        justificacion="J" * 120,
    )
    assert verdict.warn_flags == []
    assert verdict.requires_human_review is False
    assert verdict.confidence == "high"
