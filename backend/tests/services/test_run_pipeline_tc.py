"""Seam 2: run_pipeline etiqueta la procedencia del TC y persiste warn_fx (ADR-005)."""

from contextlib import asynccontextmanager
from decimal import Decimal as D
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from agents.contracts import AgentResult, OrchestratorSynthesis
from agents.llm_client import FakeLLMClient
from api.v1.schemas import CreateEvaluationRequest
from services import evaluation_service as svc
from tests.integration.test_evaluation_e2e import (
    AGENT_RESULT,
    ORCHESTRATOR_SYNTHESIS,
    VALID_PAYLOAD,
)

USER = UUID("11111111-1111-1111-1111-111111111111")


async def _run(monkeypatch, banxico, payload_rate):
    """Corre run_pipeline y devuelve el state que se persistiría (sin DB: sqlite no soporta UUID PG)."""

    async def fake_get_usd_mxn():
        if banxico is None:
            raise RuntimeError("banxico caído")
        return banxico

    monkeypatch.setattr(svc, "get_usd_mxn", fake_get_usd_mxn, raising=False)
    captured = {}

    async def spy_persist(self, session, eval_id, final_state):
        captured["state"] = final_state

    monkeypatch.setattr(svc.EvaluationService, "_persist_results", spy_persist)

    @asynccontextmanager
    async def factory():
        sess = MagicMock()
        sess.execute = AsyncMock(return_value=MagicMock())
        sess.commit = AsyncMock()
        yield sess

    llm = FakeLLMClient()
    llm.queue_responses([AGENT_RESULT] * 4 + [ORCHESTRATOR_SYNTHESIS])
    service = svc.EvaluationService(factory, llm, USER)
    req = CreateEvaluationRequest(**{**VALID_PAYLOAD, "exchange_rate_used": payload_rate})
    await service.run_pipeline(uuid4(), req)
    return captured["state"]


async def test_tc_matching_banxico_adds_no_fx_flag(monkeypatch):
    state = await _run(monkeypatch, (D("17.50"), "banxico"), 17.5)
    assert state["final_verdict"] is not None
    assert "warn_fx" not in state["final_verdict"].warn_flags


async def test_tc_edited_by_user_flags_warn_fx(monkeypatch):
    state = await _run(monkeypatch, (D("19.50"), "banxico"), 17.5)
    assert "warn_fx" in state["final_verdict"].warn_flags


async def test_banxico_down_does_not_break_pipeline_and_flags_warn_fx(monkeypatch):
    state = await _run(monkeypatch, None, 17.5)
    assert state["final_verdict"] is not None
    assert "warn_fx" in state["final_verdict"].warn_flags
