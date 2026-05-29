# backend/tests/agents/test_chat_agent.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from agents.chat import process_chat_turn
from agents.chat_processing import get_stream_queue
from db.models import ChatMessage, Evaluation, EvaluationInput


def _make_evaluation() -> tuple[Evaluation, EvaluationInput]:
    ev = Evaluation()
    ev.id = uuid.uuid4()
    ev.name = "Test Prod"
    ev.final_verdict = "viable"
    ev.final_score = 75
    ev.final_summary = "OK resumen"
    ev.status = "complete"
    ev.created_by = uuid.UUID("00000000-0000-0000-0000-000000000001")
    ev.warn_flags = []
    ev.requires_human_review = False
    ev.created_at = datetime.now(timezone.utc)
    ev.updated_at = datetime.now(timezone.utc)
    inp = EvaluationInput()
    inp.id = uuid.uuid4()
    inp.evaluation_id = ev.id
    inp.product_name = "Test Prod"
    inp.target_price = 400
    inp.estimated_units_month = 50
    inp.cost_purchase = 100
    inp.cost_freight = 10
    inp.cost_customs = 5
    inp.cost_storage = 2
    inp.cost_logistics_vehicle = 2
    inp.cost_logistics_viaticos = 0
    inp.cost_logistics_personnel = 0
    inp.cost_shrinkage_pct = 1
    inp.cost_commission_pct = 3
    inp.cost_marketing = 5
    inp.cost_overhead = 5
    ev.inputs = inp
    ev.agent_results = []
    ev.chat_messages = []
    return ev, inp


def _make_messages(ev: Evaluation) -> tuple[ChatMessage, ChatMessage]:
    user_msg = ChatMessage()
    user_msg.id = uuid.uuid4()
    user_msg.evaluation_id = ev.id
    user_msg.role = "user"
    user_msg.content = "¿Cuál es el margen neto?"
    user_msg.status = "complete"
    user_msg.created_at = datetime.now(timezone.utc)
    user_msg.updated_at = datetime.now(timezone.utc)

    asst_msg = ChatMessage()
    asst_msg.id = uuid.uuid4()
    asst_msg.evaluation_id = ev.id
    asst_msg.role = "assistant"
    asst_msg.content = ""
    asst_msg.status = "streaming"
    asst_msg.created_at = datetime.now(timezone.utc)
    asst_msg.updated_at = datetime.now(timezone.utc)
    return user_msg, asst_msg


@pytest.mark.asyncio
async def test_process_chat_turn_completes_message(fake_session, fake_llm):
    ev, _ = _make_evaluation()
    fake_session.add(ev)
    await fake_session.flush()

    user_msg, asst_msg = _make_messages(ev)
    fake_session.add(user_msg)
    fake_session.add(asst_msg)
    await fake_session.flush()

    fake_llm.queue_stream(["El margen ", "neto es 40%."])

    await process_chat_turn(
        evaluation_id=ev.id,
        user_msg_id=user_msg.id,
        assistant_msg_id=asst_msg.id,
        session=fake_session,
        llm=fake_llm,
    )

    await fake_session.refresh(asst_msg)
    assert asst_msg.status == "complete"
    assert "margen" in asst_msg.content.lower()
    # Queue should be cleaned up
    assert get_stream_queue(str(asst_msg.id)) is None


@pytest.mark.asyncio
async def test_process_chat_turn_sets_error_on_llm_failure(fake_session, fake_llm):
    ev, _ = _make_evaluation()
    fake_session.add(ev)
    await fake_session.flush()

    user_msg, asst_msg = _make_messages(ev)
    fake_session.add(user_msg)
    fake_session.add(asst_msg)
    # Use commit so data survives the session.rollback() called inside
    # process_chat_turn on the error path (join_transaction_mode='create_savepoint'
    # means commit here becomes RELEASE SAVEPOINT, anchoring rows below next sp).
    await fake_session.commit()

    fake_llm.queue_stream_error(RuntimeError("LLM timeout simulated"))

    await process_chat_turn(
        evaluation_id=ev.id,
        user_msg_id=user_msg.id,
        assistant_msg_id=asst_msg.id,
        session=fake_session,
        llm=fake_llm,
    )

    # After rollback inside process_chat_turn, asst_msg is detached from the
    # session identity map. Re-query by ID to get the persisted state.
    from sqlalchemy import select as _select
    result = await fake_session.execute(
        _select(ChatMessage).where(ChatMessage.id == asst_msg.id)
    )
    asst_msg_db = result.scalar_one()
    assert asst_msg_db.status == "error"
    assert asst_msg_db.error_msg is not None
    assert get_stream_queue(str(asst_msg.id)) is None
