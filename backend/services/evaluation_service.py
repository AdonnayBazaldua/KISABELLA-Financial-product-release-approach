"""EvaluationService — orquesta DB + pipeline + serialización a DTOs.

ADR-006: el endpoint POST devuelve 202 inmediato; el pipeline corre en
BackgroundTask. El service expone create() (sync con DB) y run_pipeline()
(async, llamado desde BackgroundTask con su propia session).

Sprint 1 / Fase 0: el flujo es funcional pero algunos detalles son stub:
- TC viene del payload (Banxico real en Sprint 6).
- Watchdog de huérfanos: TODO (Sprint 6).
- Idempotency key: TODO (Sprint 2).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agents.contracts import (
    AgentError,
    AgentResult,
    EvaluationInputs,
    TCMetadata,
)
from agents.llm_client import LLMClient
from agents.pipeline import AGENTS, run_evaluation
from api.v1.schemas import (
    AgentResultDTO,
    AgentStatus,
    CreateEvaluationRequest,
    EvaluationCreated,
    EvaluationDetail,
    EvaluationSummary,
)
from db.models import AgentResult as AgentResultRow
from db.models import Evaluation, EvaluationInput

if TYPE_CHECKING:
    SessionFactory = Callable[[], AsyncSession]


def _inputs_from_request(req: CreateEvaluationRequest) -> EvaluationInputs:
    """Mapea HTTP request → EvaluationInputs interno del pipeline."""
    return EvaluationInputs(
        product_name=req.product_name,
        description=req.description,
        category=req.category,
        sales_channel=req.sales_channel,
        cost_purchase=req.cost_purchase,
        cost_purchase_usd=req.cost_purchase_usd,
        cost_freight=req.cost_freight,
        cost_customs=req.cost_customs,
        cost_storage=req.cost_storage,
        cost_logistics_vehicle=req.cost_logistics_vehicle,
        cost_logistics_viaticos=req.cost_logistics_viaticos,
        cost_logistics_personnel=req.cost_logistics_personnel,
        cost_shrinkage_pct=req.cost_shrinkage_pct,
        cost_commission_pct=req.cost_commission_pct,
        cost_marketing=req.cost_marketing,
        cost_overhead=req.cost_overhead,
        target_price=req.target_price,
        estimated_units_month=req.estimated_units_month,
        exchange_rate_used=req.exchange_rate_used,
        exchange_rate_at=datetime.now(timezone.utc),
        tc_source="user_provided",
    )


def _eval_row_from_request(
    req: CreateEvaluationRequest, user_id: UUID, eval_id: UUID
) -> tuple[Evaluation, EvaluationInput]:
    """Construye las dos rows (Evaluation + EvaluationInput) desde el payload."""
    eval_row = Evaluation(
        id=eval_id,
        created_by=user_id,
        name=req.name,
        status="pending",
    )
    inputs_row = EvaluationInput(
        evaluation_id=eval_id,
        product_name=req.product_name,
        description=req.description,
        category=req.category,
        cost_purchase=req.cost_purchase,
        cost_purchase_usd=req.cost_purchase_usd,
        cost_freight=req.cost_freight,
        cost_customs=req.cost_customs,
        cost_storage=req.cost_storage,
        cost_logistics_vehicle=req.cost_logistics_vehicle,
        cost_logistics_viaticos=req.cost_logistics_viaticos,
        cost_logistics_personnel=req.cost_logistics_personnel,
        cost_shrinkage_pct=req.cost_shrinkage_pct,
        cost_commission_pct=req.cost_commission_pct,
        cost_marketing=req.cost_marketing,
        cost_overhead=req.cost_overhead,
        target_price=req.target_price,
        estimated_units_month=req.estimated_units_month,
        sales_channel=req.sales_channel,
        exchange_rate_used=req.exchange_rate_used,
        exchange_rate_at=datetime.now(timezone.utc),
    )
    return eval_row, inputs_row


def _agent_result_to_dto(name: str, item: AgentResult | AgentError | None) -> AgentResultDTO:
    """Serializa AgentResult/AgentError/None → DTO HTTP."""
    if item is None:
        return AgentResultDTO(
            agent_name=name,
            status="pending",
            score=None,
            veredicto_corto=None,
            analisis_extenso=None,
            hallazgos_clave=[],
            recomendaciones=[],
        )
    if isinstance(item, AgentError):
        return AgentResultDTO(
            agent_name=name,
            status="failed",
            score=None,
            veredicto_corto=None,
            analisis_extenso=None,
            hallazgos_clave=[],
            recomendaciones=[],
            error_message=item.error_message,
        )
    # AgentResult
    return AgentResultDTO(
        agent_name=name,
        status="ok",
        score=item.score,
        veredicto_corto=item.veredicto_corto,
        analisis_extenso=item.analisis_extenso,
        hallazgos_clave=list(item.hallazgos_clave),
        recomendaciones=list(item.recomendaciones),
    )


def compute_idempotency_hash(user_id: UUID, payload: dict) -> str:
    """SHA-256 de user_id + payload serializado. Determinístico."""
    canonical = json.dumps(
        {"user_id": str(user_id), **payload},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class DuplicateEvaluationError(Exception):
    def __init__(self, hash_value: str):
        self.hash_value = hash_value
        super().__init__(f"Evaluación duplicada (hash={hash_value[:12]}…)")


class EvaluationService:
    """Orquesta el ciclo de vida de una evaluación.

    - create(): inserta rows + retorna 202 payload (sync DB).
    - run_pipeline(): corre el pipeline LangGraph en background + persiste.
    - get_detail(): lee detail con todos los agent_results.
    - list(): paginación de evaluaciones del user.
    """

    def __init__(
        self,
        session_factory: Callable[[], Awaitable[AsyncSession]],
        llm: LLMClient,
        user_id: UUID,
    ) -> None:
        self._session_factory = session_factory
        self._llm = llm
        self._user_id = user_id

    async def create(
        self, req: CreateEvaluationRequest, db: AsyncSession
    ) -> EvaluationCreated:
        """Inserta Evaluation + EvaluationInput. Retorna 202 payload."""
        idem_hash = compute_idempotency_hash(
            self._user_id, req.model_dump(mode="json")
        )

        # Check duplicado en ventana 30s
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
        existing = await db.execute(
            select(Evaluation).where(
                Evaluation.idempotency_hash == idem_hash,
                Evaluation.created_at >= cutoff,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DuplicateEvaluationError(idem_hash)

        eval_id = uuid4()
        eval_row, inputs_row = _eval_row_from_request(req, self._user_id, eval_id)
        eval_row.idempotency_hash = idem_hash
        db.add(eval_row)
        db.add(inputs_row)
        await db.flush()
        return EvaluationCreated(evaluation_id=eval_id, status="pending")

    async def run_pipeline(
        self, eval_id: UUID, req: CreateEvaluationRequest
    ) -> None:
        """Ejecuta el pipeline + persiste resultados. Llamado por BackgroundTask.

        Abre su propia session (independiente de la del request, que ya cerró).
        Captura cualquier excepción y la persiste como error_message.
        """
        inputs = _inputs_from_request(req)
        tc_meta = TCMetadata(
            rate=req.exchange_rate_used,
            source="user_provided",
            fetched_at=datetime.now(timezone.utc),
        )

        try:
            async with self._session_factory() as session:
                await self._mark_status(session, eval_id, "running")

            final_state = await run_evaluation(
                inputs, tc_meta, self._llm, eval_id=eval_id, user_id=self._user_id
            )

            async with self._session_factory() as session:
                await self._persist_results(session, eval_id, final_state)
        except Exception as exc:  # noqa: BLE001
            async with self._session_factory() as session:
                await self._mark_error(session, eval_id, str(exc)[:1000])

    async def _mark_status(
        self, session: AsyncSession, eval_id: UUID, status: str
    ) -> None:
        result = await session.execute(
            select(Evaluation).where(Evaluation.id == eval_id)
        )
        ev = result.scalar_one_or_none()
        if ev is not None:
            ev.status = status
            ev.updated_at = datetime.now(timezone.utc)
            await session.commit()

    async def _mark_error(
        self, session: AsyncSession, eval_id: UUID, msg: str
    ) -> None:
        result = await session.execute(
            select(Evaluation).where(Evaluation.id == eval_id)
        )
        ev = result.scalar_one_or_none()
        if ev is not None:
            ev.status = "error"
            ev.error_message = msg
            ev.updated_at = datetime.now(timezone.utc)
            await session.commit()

    async def _persist_results(
        self, session: AsyncSession, eval_id: UUID, final_state: dict
    ) -> None:
        result = await session.execute(
            select(Evaluation).where(Evaluation.id == eval_id)
        )
        ev = result.scalar_one_or_none()
        if ev is None:
            return

        verdict = final_state.get("final_verdict")
        agent_results = final_state.get("agent_results", {})

        # Persistir cada AgentResult válido como row
        for name, item in agent_results.items():
            if isinstance(item, AgentResult):
                session.add(
                    AgentResultRow(
                        evaluation_id=eval_id,
                        agent_name=name,
                        score=item.score,
                        veredicto_corto=item.veredicto_corto,
                        analisis_extenso=item.analisis_extenso,
                        hallazgos_clave=list(item.hallazgos_clave),
                        recomendaciones=list(item.recomendaciones),
                    )
                )

        ev.status = "complete"
        if verdict is not None:
            ev.final_verdict = verdict.veredicto
            ev.final_score = verdict.score_final
            ev.final_summary = verdict.justificacion
            ev.warn_flags = list(verdict.warn_flags)
            ev.requires_human_review = verdict.requires_human_review
        ev.updated_at = datetime.now(timezone.utc)
        await session.commit()

    async def get_detail(
        self, eval_id: UUID, db: AsyncSession
    ) -> EvaluationDetail | None:
        result = await db.execute(
            select(Evaluation)
            .where(Evaluation.id == eval_id)
            .options(
                selectinload(Evaluation.agent_results),
                selectinload(Evaluation.inputs),
            )
        )
        ev = result.scalar_one_or_none()
        if ev is None:
            return None

        # Build progress dict + agent_results DTOs
        agents_by_name = {ar.agent_name: ar for ar in ev.agent_results}
        progress: dict[str, AgentStatus] = {}
        dtos: list[AgentResultDTO] = []
        for name in AGENTS.keys():
            ar = agents_by_name.get(name)
            if ar is None:
                progress[name] = "pending" if ev.status != "complete" else "failed"
                dtos.append(
                    AgentResultDTO(
                        agent_name=name,
                        status=progress[name],
                        score=None,
                        veredicto_corto=None,
                        analisis_extenso=None,
                        hallazgos_clave=[],
                        recomendaciones=[],
                    )
                )
            else:
                progress[name] = "ok"
                dtos.append(
                    AgentResultDTO(
                        agent_name=name,
                        status="ok",
                        score=ar.score,
                        veredicto_corto=ar.veredicto_corto,
                        analisis_extenso=ar.analisis_extenso,
                        hallazgos_clave=list(ar.hallazgos_clave or []),
                        recomendaciones=list(ar.recomendaciones or []),
                    )
                )

        inputs_row = ev.inputs

        return EvaluationDetail(
            id=ev.id,
            name=ev.name,
            product_name=inputs_row.product_name if inputs_row else "",
            status=ev.status,  # type: ignore[arg-type]
            final_verdict=ev.final_verdict,  # type: ignore[arg-type]
            final_score=ev.final_score,
            final_summary=ev.final_summary,
            error_message=ev.error_message,
            warn_flags=ev.warn_flags or [],
            requires_human_review=ev.requires_human_review or False,
            progress=progress,
            agent_results=dtos,
            created_at=ev.created_at,
            updated_at=ev.updated_at,
        )

    async def list_evaluations(
        self, db: AsyncSession, *, limit: int = 20, offset: int = 0
    ) -> list[EvaluationSummary]:
        result = await db.execute(
            select(Evaluation)
            .where(Evaluation.created_by == self._user_id)
            .options(selectinload(Evaluation.inputs))
            .order_by(Evaluation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        evs = result.scalars().all()
        return [
            EvaluationSummary(
                id=ev.id,
                name=ev.name,
                product_name=ev.inputs.product_name if ev.inputs else "",
                status=ev.status,
                final_verdict=ev.final_verdict,
                final_score=ev.final_score,
                created_at=ev.created_at,
            )
            for ev in evs
        ]
