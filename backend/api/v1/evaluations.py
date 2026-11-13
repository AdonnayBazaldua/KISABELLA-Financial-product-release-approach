"""Endpoints HTTP de evaluaciones (POST 202 + GET polling + LIST).

ADR-006: POST devuelve 202 + evaluation_id. Pipeline corre en BackgroundTask.
Frontend hace polling sobre GET /api/v1/evaluations/{id} hasta status=complete.

Todas las deps (LLMClient, user_id, session_factory) son FastAPI dependencies
para que los tests las puedan overridear via app.dependency_overrides.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncContextManager, Callable
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from agents.llm_client import LLMClient, get_llm_client
from api.v1.schemas import (
    CreateEvaluationRequest,
    EvaluationCreated,
    EvaluationDetail,
    EvaluationSummary,
)
from core.config import Settings, get_settings
from db.session import _ensure_engine, get_db
from services.evaluation_service import DuplicateEvaluationError, EvaluationService

router = APIRouter(prefix="/api/v1", tags=["evaluations"])


# ===== Dependencies (overrideables en tests) =====


def get_user_id(settings: Settings = Depends(get_settings)) -> UUID:
    """Usuario único implícito: viene de settings (no hay cuentas)."""
    return UUID(settings.app_user_id)


def get_background_session_factory() -> Callable[[], AsyncContextManager[AsyncSession]]:
    """Factory de sesiones para trabajo fuera del request (BackgroundTasks, SSE).

    La sesión del request ya está cerrada cuando ese trabajo corre; cada uso abre la suya.
    El contexto RLS lo pone db.session en cada transacción.
    """

    @asynccontextmanager
    async def _factory():
        async with _ensure_engine()() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    return _factory


def get_eval_service(
    llm: LLMClient = Depends(get_llm_client),
    user_id: UUID = Depends(get_user_id),
    session_factory: Callable = Depends(get_background_session_factory),
) -> EvaluationService:
    return EvaluationService(
        session_factory=session_factory,
        llm=llm,
        user_id=user_id,
    )


# ===== Endpoints =====


@router.post(
    "/evaluations",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EvaluationCreated,
)
async def create_evaluation(
    req: CreateEvaluationRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    service: EvaluationService = Depends(get_eval_service),
) -> EvaluationCreated:
    """Crea evaluación + dispara pipeline async. Retorna 202 inmediato."""
    try:
        created = await service.create(req, db)
    except DuplicateEvaluationError:
        raise HTTPException(
            status_code=409,
            detail={"detail": "Evaluación duplicada — esperá 30s antes de re-enviar", "code": "DUPLICATE"},
        )
    background.add_task(service.run_pipeline, created.evaluation_id, req)
    return created


@router.get(
    "/evaluations/compare",
    response_model=list[EvaluationDetail],
)
async def compare_evaluations(
    ids: str,
    db: AsyncSession = Depends(get_db),
    service: EvaluationService = Depends(get_eval_service),
) -> list[EvaluationDetail]:
    """Retorna 2-3 evaluaciones completas para comparacion lado a lado."""
    try:
        id_list = [UUID(i.strip()) for i in ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="IDs invalidos")

    try:
        return await service.compare(id_list, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/evaluations/{eval_id}",
    response_model=EvaluationDetail,
)
async def get_evaluation(
    eval_id: UUID,
    db: AsyncSession = Depends(get_db),
    service: EvaluationService = Depends(get_eval_service),
) -> EvaluationDetail:
    detail = await service.get_detail(eval_id, db)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Evaluación no encontrada", "code": "NOT_FOUND"},
        )
    return detail


@router.get(
    "/evaluations",
    response_model=list[EvaluationSummary],
)
async def list_evaluations(
    db: AsyncSession = Depends(get_db),
    service: EvaluationService = Depends(get_eval_service),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[EvaluationSummary]:
    return await service.list_evaluations(db, limit=limit, offset=offset)
