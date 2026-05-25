"""Factory para agentes especialistas (ADR-001).

Patrón funcional: AgentFn = async (EvaluationInputs, LLMClient) → AgentResult.
NO clases. NO herencia. La factory build_agent() compone los pedazos:
- prompt template (system + user con placeholders)
- calc_fn opcional (cálculos previos al LLM — Financiero la usa)
- score_fn opcional (override del score del LLM con cálculo determinístico)

Para sumar un agente nuevo: 1 archivo .py con `name_agent = build_agent(...)`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from agents.contracts import AgentResult, EvaluationInputs
from agents.llm_client import LLMClient

PROMPTS_DIR = Path(__file__).parent / "prompts"

AgentFn = Callable[[EvaluationInputs, LLMClient], Awaitable[AgentResult]]
CalcFn = Callable[[EvaluationInputs], Any]
ScoreFn = Callable[[AgentResult, Any], int]


class PromptTemplates(BaseModel):
    model_config = ConfigDict(frozen=True)
    system: str
    user_template: str


def load_prompt(name: str) -> PromptTemplates:
    """Lee prompts/{name}.md y separa secciones ## System / ## User Template."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt no encontrado: {path}")

    content = path.read_text(encoding="utf-8")
    sections: dict[str, list[str]] = {}
    current_key: str | None = None
    for line in content.splitlines():
        if line.startswith("## "):
            current_key = line[3:].strip().lower().replace(" ", "_")
            sections[current_key] = []
        elif current_key is not None:
            sections[current_key].append(line)

    if "system" not in sections or "user_template" not in sections:
        raise ValueError(
            f"Prompt {name}.md debe tener secciones '## System' y '## User Template'"
        )

    return PromptTemplates(
        system="\n".join(sections["system"]).strip(),
        user_template="\n".join(sections["user_template"]).strip(),
    )


def _render_user(template: str, inputs: EvaluationInputs, calc: Any) -> str:
    """Rinde user_template con valores de inputs (+ calc si existe).

    Decimal y datetime se serializan a string via model_dump(mode="json").
    Valores None se renderizan como 'N/D' para legibilidad.
    """
    ctx: dict[str, Any] = inputs.model_dump(mode="json")
    if calc is not None and isinstance(calc, BaseModel):
        ctx.update(calc.model_dump(mode="json"))

    # Reemplaza None por "N/D" para que el LLM no vea "None"
    safe_ctx = {k: ("N/D" if v is None else v) for k, v in ctx.items()}

    return template.format(**safe_ctx)


def build_agent(
    name: str,
    prompt_name: str,
    calc_fn: CalcFn | None = None,
    score_fn: ScoreFn | None = None,
) -> AgentFn:
    """Construye un AgentFn componiendo prompt + calc + score override.

    - calc_fn(inputs) → cualquier Pydantic model con los pre-cálculos.
      Sus campos se inyectan en el user_template junto con los inputs.
    - score_fn(raw_result, calc) → score 0-100 que reemplaza el del LLM.
      Si None, se usa el score que el LLM devolvió.
    """
    prompts = load_prompt(prompt_name)

    async def _agent(inputs: EvaluationInputs, llm: LLMClient) -> AgentResult:
        calc = calc_fn(inputs) if calc_fn else None
        user_msg = _render_user(prompts.user_template, inputs, calc)

        raw = await llm.request_structured(
            system=prompts.system,
            user=user_msg,
            schema=AgentResult,
        )

        if score_fn is not None:
            return raw.model_copy(update={"score": score_fn(raw, calc)})
        return raw

    _agent.__name__ = f"{name}_agent"
    _agent.__qualname__ = f"{name}_agent"
    return _agent
