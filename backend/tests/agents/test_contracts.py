"""Tests para agents.contracts — shape y validators del dominio."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agents.contracts import (
    AgentError,
    AgentResult,
    EvaluationInputs,
    FinalVerdict,
    PipelineState,
    TCMetadata,
)


def _valid_eval_kwargs(**overrides):
    base = dict(
        product_name="Smartwatch X1",
        category="fisico",
        cost_purchase=Decimal("250.00"),
        cost_freight=Decimal("30.00"),
        cost_customs=Decimal("50.00"),
        cost_storage=Decimal("10.00"),
        cost_logistics_vehicle=Decimal("5.00"),
        cost_logistics_viaticos=Decimal("3.00"),
        cost_logistics_personnel=Decimal("15.00"),
        cost_shrinkage_pct=Decimal("2.00"),
        cost_commission_pct=Decimal("10.00"),
        cost_marketing=Decimal("20.00"),
        cost_overhead=Decimal("25.00"),
        target_price=Decimal("599.00"),
        estimated_units_month=100,
        exchange_rate_used=Decimal("19.8500"),
        exchange_rate_at=datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return base


def _valid_agent_result_kwargs(**overrides):
    base = dict(
        score=75,
        veredicto_corto="Margen bruto saludable con sensibilidad TC controlada",
        analisis_extenso="x" * 500,  # 500 chars válidos
        hallazgos_clave=["margen bruto 47%", "punto equilibrio 32 unidades/mes"],
        recomendaciones=[
            "Negociar volumen con proveedor para reducir costo unitario",
            "Cubrir TC con forward 6 meses",
        ],
    )
    base.update(overrides)
    return base


def _valid_final_verdict_kwargs(**overrides):
    base = dict(
        veredicto="viable",
        score_final=78,
        justificacion="x" * 200,
    )
    base.update(overrides)
    return base


class TestEvaluationInputsValid:
    def test_loads_with_valid_inputs(self):
        e = EvaluationInputs(**_valid_eval_kwargs())
        assert e.product_name == "Smartwatch X1"
        assert e.target_price == Decimal("599.00")
        assert e.tc_source == "banxico"  # default

    def test_is_frozen(self):
        e = EvaluationInputs(**_valid_eval_kwargs())
        with pytest.raises(ValidationError):
            e.target_price = Decimal("700.00")  # type: ignore[misc]

    def test_optional_fields_use_defaults(self):
        e = EvaluationInputs(**_valid_eval_kwargs())
        assert e.description is None
        assert e.sales_channel is None
        assert e.cost_purchase_usd is None


class TestEvaluationInputsValidators:
    def test_negative_cost_fails(self):
        with pytest.raises(ValidationError, match="greater than or equal"):
            EvaluationInputs(**_valid_eval_kwargs(cost_purchase=Decimal("-1.00")))

    def test_shrinkage_pct_over_100_fails(self):
        with pytest.raises(ValidationError, match="less than or equal"):
            EvaluationInputs(
                **_valid_eval_kwargs(cost_shrinkage_pct=Decimal("101.00"))
            )

    def test_commission_pct_over_100_fails(self):
        with pytest.raises(ValidationError):
            EvaluationInputs(
                **_valid_eval_kwargs(cost_commission_pct=Decimal("150.00"))
            )

    def test_target_price_zero_fails(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            EvaluationInputs(**_valid_eval_kwargs(target_price=Decimal("0.00")))

    def test_estimated_units_zero_fails(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            EvaluationInputs(**_valid_eval_kwargs(estimated_units_month=0))

    def test_estimated_units_negative_fails(self):
        with pytest.raises(ValidationError):
            EvaluationInputs(**_valid_eval_kwargs(estimated_units_month=-5))

    def test_exchange_rate_zero_fails(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            EvaluationInputs(**_valid_eval_kwargs(exchange_rate_used=Decimal("0.0000")))

    def test_product_name_empty_fails(self):
        with pytest.raises(ValidationError):
            EvaluationInputs(**_valid_eval_kwargs(product_name=""))

    def test_invalid_category_fails(self):
        with pytest.raises(ValidationError):
            EvaluationInputs(**_valid_eval_kwargs(category="digital"))

    def test_invalid_tc_source_fails(self):
        with pytest.raises(ValidationError):
            EvaluationInputs(**_valid_eval_kwargs(tc_source="manual"))


class TestAgentResultValid:
    def test_loads_with_valid_inputs(self):
        r = AgentResult(**_valid_agent_result_kwargs())
        assert r.score == 75
        assert len(r.hallazgos_clave) == 2

    def test_is_frozen(self):
        r = AgentResult(**_valid_agent_result_kwargs())
        with pytest.raises(ValidationError):
            r.score = 80  # type: ignore[misc]


class TestAgentResultValidators:
    def test_score_over_100_fails(self):
        with pytest.raises(ValidationError, match="less than or equal to 100"):
            AgentResult(**_valid_agent_result_kwargs(score=101))

    def test_score_negative_fails(self):
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            AgentResult(**_valid_agent_result_kwargs(score=-5))

    def test_score_must_be_int_not_float(self):
        # Pydantic v2 coerce float to int silently if "75.0"; vamos a verificar
        # que números no enteros fallan
        with pytest.raises(ValidationError):
            AgentResult(**_valid_agent_result_kwargs(score=75.5))

    def test_analisis_too_short_fails(self):
        with pytest.raises(ValidationError, match="at least 300"):
            AgentResult(**_valid_agent_result_kwargs(analisis_extenso="muy corto"))

    def test_hallazgos_empty_fails(self):
        with pytest.raises(ValidationError):
            AgentResult(**_valid_agent_result_kwargs(hallazgos_clave=[]))

    def test_recomendaciones_empty_fails(self):
        with pytest.raises(ValidationError):
            AgentResult(**_valid_agent_result_kwargs(recomendaciones=[]))

    def test_veredicto_corto_too_short_fails(self):
        with pytest.raises(ValidationError):
            AgentResult(**_valid_agent_result_kwargs(veredicto_corto="x"))


class TestAgentError:
    def test_creates_with_required(self):
        err = AgentError(
            agent_name="financiero",
            error_type="parsing",
            error_message="LLM devolvió JSON inválido",
        )
        assert err.retry_count == 0

    def test_invalid_agent_name_fails(self):
        with pytest.raises(ValidationError):
            AgentError(
                agent_name="orquestador",  # orquestador no es SpecialistName
                error_type="parsing",
                error_message="test",
            )

    def test_invalid_error_type_fails(self):
        with pytest.raises(ValidationError):
            AgentError(
                agent_name="mercado",
                error_type="cosmic_ray",  # type: ignore[arg-type]
                error_message="test",
            )

    def test_retry_count_over_3_fails(self):
        with pytest.raises(ValidationError):
            AgentError(
                agent_name="riesgo",
                error_type="timeout",
                error_message="test",
                retry_count=4,
            )


class TestFinalVerdict:
    def test_creates_with_required(self):
        v = FinalVerdict(**_valid_final_verdict_kwargs())
        assert v.veredicto == "viable"
        assert v.requires_human_review is False
        assert v.confidence == "high"
        assert v.warn_flags == []

    def test_invalid_veredicto_fails(self):
        with pytest.raises(ValidationError):
            FinalVerdict(**_valid_final_verdict_kwargs(veredicto="VIABLE"))

    def test_veredicto_must_use_underscore(self):
        with pytest.raises(ValidationError):
            FinalVerdict(
                **_valid_final_verdict_kwargs(veredicto="viable con ajustes")
            )

    def test_all_three_veredictos_accepted(self):
        for v in ("viable", "viable_con_ajustes", "no_viable"):
            verdict = FinalVerdict(**_valid_final_verdict_kwargs(veredicto=v))
            assert verdict.veredicto == v

    def test_justificacion_too_short_fails(self):
        with pytest.raises(ValidationError, match="at least 100"):
            FinalVerdict(**_valid_final_verdict_kwargs(justificacion="corta"))

    def test_invalid_confidence_fails(self):
        with pytest.raises(ValidationError):
            FinalVerdict(**_valid_final_verdict_kwargs(confidence="unknown"))


class TestTCMetadata:
    def test_creates_with_required(self):
        tc = TCMetadata(
            rate=Decimal("19.85"),
            source="banxico",
            fetched_at=datetime.now(timezone.utc),
        )
        assert tc.is_stale is False

    def test_negative_rate_fails(self):
        with pytest.raises(ValidationError):
            TCMetadata(
                rate=Decimal("-1.00"),
                source="banxico",
                fetched_at=datetime.now(timezone.utc),
            )

    def test_invalid_source_fails(self):
        with pytest.raises(ValidationError):
            TCMetadata(
                rate=Decimal("19.85"),
                source="random_api",  # type: ignore[arg-type]
                fetched_at=datetime.now(timezone.utc),
            )


class TestPipelineState:
    """PipelineState es TypedDict — Python no valida en runtime, pero usemos
    como dict normal y assertear sobre la estructura."""

    def test_instantiates_as_dict(self):
        state: PipelineState = {
            "eval_id": uuid4(),
            "user_id": uuid4(),
            "agent_results": {},
            "warn_flags": [],
        }
        assert state["agent_results"] == {}
        assert isinstance(state["warn_flags"], list)

    def test_total_false_allows_partial(self):
        state: PipelineState = {"warn_flags": ["warn_fx"]}
        assert state.get("eval_id") is None

    def test_can_store_mixed_result_and_error(self):
        state: PipelineState = {
            "agent_results": {
                "financiero": AgentResult(**_valid_agent_result_kwargs()),
                "mercado": AgentError(
                    agent_name="mercado",
                    error_type="timeout",
                    error_message="Tavily timeout",
                ),
            }
        }
        assert isinstance(state["agent_results"]["financiero"], AgentResult)
        assert isinstance(state["agent_results"]["mercado"], AgentError)
