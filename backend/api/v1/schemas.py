"""Pydantic request/response del API HTTP.

Separados de agents.contracts (EvaluationInputs) porque:
- HTTP shape puede divergir de internal shape (ej: campos opcionales,
  USD/MXN conversion, defaults distintos).
- Frontend genera tipos de estos schemas via openapi-typescript (ADR-004).
- Cambios HTTP no rompen el pipeline interno.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ===== Request =====


class CreateEvaluationRequest(BaseModel):
    """POST /api/v1/evaluations body."""

    model_config = ConfigDict(extra="forbid")  # rechaza campos no declarados

    # Metadata
    name: str = Field(min_length=1, max_length=255)
    product_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: Literal["fisico", "servicio"] = "fisico"
    sales_channel: str | None = Field(default=None, max_length=100)

    # 11 costos
    cost_purchase: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    cost_purchase_usd: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )
    cost_freight: Decimal = Field(default=Decimal("0"), ge=0)
    cost_customs: Decimal = Field(default=Decimal("0"), ge=0)
    cost_storage: Decimal = Field(default=Decimal("0"), ge=0)
    cost_logistics_vehicle: Decimal = Field(default=Decimal("0"), ge=0)
    cost_logistics_viaticos: Decimal = Field(default=Decimal("0"), ge=0)
    cost_logistics_personnel: Decimal = Field(default=Decimal("0"), ge=0)
    cost_shrinkage_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    cost_commission_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    cost_marketing: Decimal = Field(default=Decimal("0"), ge=0)
    cost_overhead: Decimal = Field(default=Decimal("0"), ge=0)

    # Ingresos
    target_price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    estimated_units_month: int = Field(gt=0)

    # TC: payload provee (Sprint 6 lo override con Banxico)
    exchange_rate_used: Decimal = Field(gt=0, max_digits=8, decimal_places=4)


# ===== Response =====


class EvaluationCreated(BaseModel):
    """POST /api/v1/evaluations response (202)."""

    evaluation_id: UUID
    status: Literal["pending"]


AgentStatus = Literal["pending", "running", "ok", "failed", "degraded"]
EvaluationStatus = Literal["pending", "queued", "running", "complete", "error"]
Verdict = Literal["viable", "viable_con_ajustes", "no_viable"]


class AgentResultDTO(BaseModel):
    """Resultado de un agente especialista (serializado para HTTP)."""

    agent_name: str
    status: AgentStatus
    score: int | None
    veredicto_corto: str | None
    analisis_extenso: str | None
    hallazgos_clave: list[str]
    recomendaciones: list[str]
    error_message: str | None = None


class EvaluationDetail(BaseModel):
    """GET /api/v1/evaluations/{id} response."""

    id: UUID
    name: str
    product_name: str
    status: EvaluationStatus
    final_verdict: Verdict | None
    final_score: int | None
    final_summary: str | None
    error_message: str | None
    warn_flags: list[str]
    requires_human_review: bool
    progress: dict[str, AgentStatus]
    agent_results: list[AgentResultDTO]
    created_at: datetime
    updated_at: datetime


class EvaluationSummary(BaseModel):
    """GET /api/v1/evaluations list item."""

    id: UUID
    name: str
    product_name: str
    status: EvaluationStatus
    final_verdict: Verdict | None
    final_score: int | None
    created_at: datetime
