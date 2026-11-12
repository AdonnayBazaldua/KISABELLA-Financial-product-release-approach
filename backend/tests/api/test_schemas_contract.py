"""Contrato HTTP: los enums del OpenAPI (que alimentan los tipos del frontend, ADR-0004)."""
from api.v1.schemas import EvaluationSummary


def _enum(schema: dict, field: str) -> list[str]:
    prop = schema[field]
    opts = prop.get("anyOf", [prop])
    return next(o["enum"] for o in opts if "enum" in o)


def test_summary_expone_status_y_veredicto_como_enum():
    s = EvaluationSummary.model_json_schema()["properties"]
    assert _enum(s, "final_verdict") == ["viable", "viable_con_ajustes", "no_viable"]
    assert "complete" in _enum(s, "status")
