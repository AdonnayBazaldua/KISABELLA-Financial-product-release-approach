import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import get_session
from db.models import Evaluation, EvaluationInput, AgentResult
from agents.pipeline import run_pipeline
from core.config import settings

router = APIRouter()


class CreateEvaluationRequest(BaseModel):
    name: str
    product_name: str
    description: str = ""
    category: str = "fisico"
    cost_purchase: float = 0
    cost_purchase_usd: float = 0
    cost_freight: float = 0
    cost_customs: float = 0
    cost_storage: float = 0
    cost_logistics_vehicle: float = 0
    cost_logistics_viaticos: float = 0
    cost_logistics_personnel: float = 0
    cost_shrinkage_pct: float = 0
    cost_commission_pct: float = 0
    cost_marketing: float = 0
    cost_overhead: float = 0
    target_price: float
    estimated_units_month: int = 1
    sales_channel: str = ""
    exchange_rate_used: float = 19.50


@router.post("/evaluations", status_code=201)
async def create_evaluation(
    payload: CreateEvaluationRequest,
    db: AsyncSession = Depends(get_session),
):
    eval_id = str(uuid.uuid4())

    evaluation = Evaluation(
        id=uuid.UUID(eval_id),
        created_by=uuid.UUID(settings.app_user_id),
        name=payload.name,
        status="running",
    )
    db.add(evaluation)

    eval_input = EvaluationInput(
        evaluation_id=uuid.UUID(eval_id),
        product_name=payload.product_name,
        description=payload.description,
        category=payload.category,
        cost_purchase=payload.cost_purchase,
        cost_purchase_usd=payload.cost_purchase_usd,
        cost_freight=payload.cost_freight,
        cost_customs=payload.cost_customs,
        cost_storage=payload.cost_storage,
        cost_logistics_vehicle=payload.cost_logistics_vehicle,
        cost_logistics_viaticos=payload.cost_logistics_viaticos,
        cost_logistics_personnel=payload.cost_logistics_personnel,
        cost_shrinkage_pct=payload.cost_shrinkage_pct,
        cost_commission_pct=payload.cost_commission_pct,
        cost_marketing=payload.cost_marketing,
        cost_overhead=payload.cost_overhead,
        target_price=payload.target_price,
        estimated_units_month=payload.estimated_units_month,
        sales_channel=payload.sales_channel,
        exchange_rate_used=payload.exchange_rate_used,
        exchange_rate_at=datetime.now(timezone.utc),
    )
    db.add(eval_input)
    await db.commit()

    inputs_dict = {
        **payload.model_dump(),
        "exchange_rate": payload.exchange_rate_used,
    }
    try:
        result = await run_pipeline(eval_id, inputs_dict)

        if result.get("financial_result"):
            fr = result["financial_result"]
            agent_result = AgentResult(
                evaluation_id=uuid.UUID(eval_id),
                agent_name="financiero",
                score=fr["score"],
                veredicto_corto=fr["veredicto_corto"],
                analisis_extenso=fr["analisis_extenso"],
                hallazgos_clave=fr["hallazgos_clave"],
                recomendaciones=fr["recomendaciones"],
                raw_calculations=fr.get("raw_calculations"),
            )
            db.add(agent_result)

        evaluation.status = "complete"
        evaluation.final_verdict = result.get("final_verdict")
        evaluation.final_score = result.get("final_score")
        evaluation.final_summary = result.get("final_summary")
        await db.commit()

    except Exception as e:
        evaluation.status = "error"
        evaluation.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

    return {"evaluation_id": eval_id, "status": "complete", **result}


@router.get("/evaluations")
async def list_evaluations(db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Evaluation).order_by(Evaluation.created_at.desc())
    )
    evaluations = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "status": e.status,
            "final_verdict": e.final_verdict,
            "final_score": e.final_score,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in evaluations
    ]


@router.get("/evaluations/{evaluation_id}")
async def get_evaluation(
    evaluation_id: str,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(Evaluation).where(Evaluation.id == uuid.UUID(evaluation_id))
    )
    evaluation = result.scalar_one_or_none()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    inputs_result = await db.execute(
        select(EvaluationInput).where(EvaluationInput.evaluation_id == uuid.UUID(evaluation_id))
    )
    inputs = inputs_result.scalar_one_or_none()

    agents_result = await db.execute(
        select(AgentResult).where(AgentResult.evaluation_id == uuid.UUID(evaluation_id))
    )
    agent_results = agents_result.scalars().all()

    return {
        "id": str(evaluation.id),
        "name": evaluation.name,
        "status": evaluation.status,
        "final_verdict": evaluation.final_verdict,
        "final_score": evaluation.final_score,
        "final_summary": evaluation.final_summary,
        "created_at": evaluation.created_at.isoformat() if evaluation.created_at else None,
        "inputs": {
            "product_name": inputs.product_name if inputs else None,
            "target_price": float(inputs.target_price) if inputs else None,
            "exchange_rate_used": float(inputs.exchange_rate_used) if inputs and inputs.exchange_rate_used else None,
        } if inputs else None,
        "agent_results": [
            {
                "agent_name": ar.agent_name,
                "score": ar.score,
                "veredicto_corto": ar.veredicto_corto,
                "analisis_extenso": ar.analisis_extenso,
                "hallazgos_clave": ar.hallazgos_clave,
                "recomendaciones": ar.recomendaciones,
                "raw_calculations": ar.raw_calculations,
            }
            for ar in agent_results
        ],
    }
