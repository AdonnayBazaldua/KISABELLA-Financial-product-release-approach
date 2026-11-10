"""Contratos Pydantic del dominio Kisabella Financial Product Release.

Estos modelos son la fuente de verdad sobre las shapes que viajan por el pipeline.

- EvaluationInputs: shape de los inputs al pipeline (post-validación HTTP).
- AgentResult: lo que cada agente especialista retorna (validado por with_structured_output).
- AgentError: cuando un agente falla parcialmente — el pipeline NO se aborta.
- FinalVerdict: salida del orquestador (sin score propio; el score se deriva).
- TCMetadata: TC usado en la evaluación + procedencia (ADR-005).
- PipelineState: TypedDict mutable del grafo LangGraph (ADR-002).

ADR-001: agentes son AgentFn pure functions.
ADR-002: PipelineState.agent_results es dict[name, AgentResult | AgentError].
ADR-003: outputs LLM se validan con Pydantic en el LLMClient, no en cada agente.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --- Literales del dominio ---
Verdict = Literal["viable", "viable_con_ajustes", "no_viable"]
SpecialistName = Literal["financiero", "mercado", "riesgo", "estrategia"]
TCSource = Literal["banxico", "fallback_db", "user_provided"]
Confidence = Literal["high", "medium", "low"]
AgentErrorType = Literal[
    "parsing", "timeout", "rate_limit", "tool_failure", "validation", "budget", "unknown"
]


class EvaluationInputs(BaseModel):
    """Inputs del formulario, post-validación HTTP. Frozen una vez creados."""

    model_config = ConfigDict(frozen=True)

    # --- Producto ---
    product_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: Literal["fisico", "servicio"] = "fisico"
    sales_channel: str | None = Field(default=None, max_length=100)

    # --- Costos en MXN (11 componentes, todos >= 0) ---
    cost_purchase: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    cost_purchase_usd: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )
    cost_freight: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    cost_customs: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    cost_storage: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    cost_logistics_vehicle: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    cost_logistics_viaticos: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    cost_logistics_personnel: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    cost_shrinkage_pct: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    cost_commission_pct: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    cost_marketing: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    cost_overhead: Decimal = Field(ge=0, max_digits=14, decimal_places=2)

    # --- Ingresos ---
    target_price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    estimated_units_month: int = Field(gt=0)

    # --- Tipo de cambio (ADR-005) ---
    exchange_rate_used: Decimal = Field(gt=0, max_digits=8, decimal_places=4)
    exchange_rate_at: datetime
    tc_source: TCSource = "banxico"


class AgentResult(BaseModel):
    """Output estructurado de un agente especialista.

    Validado por ChatAnthropic.with_structured_output(AgentResult).
    Constraints reflejan las convenciones de CLAUDE.md:
    - score entero 0-100
    - veredicto_corto: 1 línea descriptiva
    - analisis_extenso: ~300-500 palabras (chequeado por longitud de string)
    - hallazgos_clave y recomendaciones: al menos 1 ítem, máximo 10
    """

    model_config = ConfigDict(frozen=True)

    score: int = Field(ge=0, le=100, description="Puntuación 0-100")
    veredicto_corto: str = Field(min_length=10, max_length=255)
    analisis_extenso: str = Field(
        min_length=300,
        max_length=5000,
        description="Análisis en español, 300-500 palabras",
    )
    hallazgos_clave: list[str] = Field(min_length=1, max_length=10)
    recomendaciones: list[str] = Field(min_length=1, max_length=10)


class AgentError(BaseModel):
    """Falla parcial de un agente.

    El pipeline NO se aborta cuando aparece — el orquestador maneja
    la degradación graceful (≥3 OK → normal; 2 OK → con ajustes; ≤1 → no_viable).
    """

    model_config = ConfigDict(frozen=True)

    agent_name: SpecialistName
    error_type: AgentErrorType
    error_message: str = Field(min_length=1, max_length=1000)
    retry_count: int = Field(ge=0, le=3, default=0)


class FinalVerdict(BaseModel):
    """Output del agente Orquestador.

    El score_final lo calcula el orquestador como weighted average
    de los AgentResult válidos (pesos en calculations/scoring.py):
        Financiero 0.35, Mercado 0.25, Riesgo 0.20, Estrategia 0.20
    """

    model_config = ConfigDict(frozen=True)

    veredicto: Verdict
    score_final: int = Field(ge=0, le=100)
    justificacion: str = Field(min_length=100, max_length=5000)
    requires_human_review: bool = False
    confidence: Confidence = "high"
    warn_flags: list[str] = Field(default_factory=list)


class OrchestratorSynthesis(BaseModel):
    """Output del LLM call del orquestador. Solo justificacion rica."""

    model_config = ConfigDict(frozen=True)

    justificacion: str = Field(
        min_length=100,
        max_length=8000,
        description="Sintesis ejecutiva en espanol, 100-800 palabras",
    )


class TCMetadata(BaseModel):
    """Metadata del TC usado en la evaluación (ADR-005)."""

    model_config = ConfigDict(frozen=True)

    rate: Decimal = Field(gt=0, max_digits=8, decimal_places=4)
    source: TCSource
    fetched_at: datetime
    is_stale: bool = False


# --- LangGraph reducers ---
# Los reducers determinan cómo merge-ar valores cuando múltiples nodos paralelos
# escriben al mismo campo del state. Sin reducer, default es "last write wins".


def _merge_agent_results(
    left: dict | None, right: dict | None
) -> dict[SpecialistName, AgentResult | AgentError]:
    """Merge dict-of-dicts: cada nodo escribe su key, no se pisan."""
    return {**(left or {}), **(right or {})}


def _merge_warn_flags(left: list | None, right: list | None) -> list[str]:
    """Concat + deduplica preservando orden."""
    return list(dict.fromkeys((left or []) + (right or [])))


class PipelineState(TypedDict, total=False):
    """Estado mutable del grafo LangGraph (ADR-002).

    `agent_results` es la única manera de identificar qué agente corrió.
    NUNCA agregar campos por agente nombrados (financiero_result, etc.).
    Sumar un agente nuevo = entrada en la dict, no cambio del shape.

    Los campos Annotated tienen reducer para merge paralelo correcto.
    """

    eval_id: UUID
    user_id: UUID
    inputs: EvaluationInputs
    tc_meta: TCMetadata
    agent_results: Annotated[
        dict[SpecialistName, AgentResult | AgentError], _merge_agent_results
    ]
    final_verdict: FinalVerdict | None
    warn_flags: Annotated[list[str], _merge_warn_flags]
