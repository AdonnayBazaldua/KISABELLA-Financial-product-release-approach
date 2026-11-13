"""Seam: EvaluationService persiste el error de los agentes fallidos y el consumo real de tokens."""

from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agents.contracts import AgentError
from api.v1.schemas import CreateEvaluationRequest
from db.models import Evaluation
from services import evaluation_service as svc
from tests.integration.test_evaluation_e2e import (
    AGENT_RESULT,
    ORCHESTRATOR_SYNTHESIS,
    VALID_PAYLOAD,
)

USER = UUID("11111111-1111-1111-1111-111111111111")


def _session_with(ev):
    session = MagicMock()
    found = MagicMock()
    found.scalar_one_or_none = MagicMock(return_value=ev)
    session.execute = AsyncMock(return_value=found)
    session.commit = AsyncMock()
    return session


async def test_failed_agent_error_is_persisted_and_shown_in_detail():
    ev = Evaluation(id=uuid4(), created_by=USER, name="x", status="running")
    session = _session_with(ev)
    service = svc.EvaluationService(None, None, USER)
    state = {
        "agent_results": {
            "financiero": AGENT_RESULT,
            "mercado": AgentError(
                agent_name="mercado", error_type="timeout", error_message="Agente mercado excedió 90s"
            ),
        }
    }

    await service._persist_results(session, ev.id, state)

    rows = [c.args[0] for c in session.add.call_args_list]
    ev.agent_results, ev.inputs = rows, None
    ev.created_at = ev.updated_at = datetime.now()
    detail = await service.get_detail(ev.id, _session_with(ev))
    by_name = {a.agent_name: a for a in detail.agent_results}
    assert by_name["mercado"].status == "failed"
    assert by_name["mercado"].error_message == "Agente mercado excedió 90s"
    assert by_name["financiero"].status == "ok"
    assert detail.progress["mercado"] == "failed"


class _LLMWithUsage:
    """Cliente que pasa por un chat model de LangChain, como el real, y reporta consumo."""

    def __init__(self, responses):
        self._responses = list(responses)

    async def request_structured(self, *, system, user, schema, temperature=None):
        usage = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
        model = GenericFakeChatModel(messages=iter([AIMessage(content="x", usage_metadata=usage, response_metadata={"model_name": "fake"})]))
        await model.ainvoke("hola")
        return self._responses.pop(0)


async def test_real_token_usage_is_summed_across_the_five_calls(monkeypatch):
    captured = {}

    async def spy_persist(self, session, eval_id, final_state, usage=None):
        captured["usage"] = usage

    monkeypatch.setattr(svc.EvaluationService, "_persist_results", spy_persist)

    async def no_banxico():
        raise RuntimeError("sin red")

    monkeypatch.setattr(svc, "get_usd_mxn", no_banxico)

    @asynccontextmanager
    async def factory():
        yield _session_with(None)

    llm = _LLMWithUsage([AGENT_RESULT] * 4 + [ORCHESTRATOR_SYNTHESIS])
    service = svc.EvaluationService(factory, llm, USER)
    await service.run_pipeline(uuid4(), CreateEvaluationRequest(**VALID_PAYLOAD))

    assert captured["usage"] == {"tokens_input": 500, "tokens_output": 100}


async def test_usage_is_stored_on_the_evaluation_and_exposed():
    ev = Evaluation(id=uuid4(), created_by=USER, name="x", status="running")
    service = svc.EvaluationService(None, None, USER)
    await service._persist_results(
        _session_with(ev), ev.id, {"agent_results": {}}, {"tokens_input": 500, "tokens_output": 100}
    )
    ev.agent_results, ev.inputs = [], None
    ev.created_at = ev.updated_at = datetime.now()
    detail = await service.get_detail(ev.id, _session_with(ev))
    assert (detail.tokens_input, detail.tokens_output) == (500, 100)
