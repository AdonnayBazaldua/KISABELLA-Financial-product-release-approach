"""Evaluación con el modelo REAL sobre el golden set. Gasta tokens de tu cuenta (~25 llamadas).

No corre en CI: las pruebas usan FakeLLMClient. Esto mide lo que las pruebas no pueden:
si el modelo, con los prompts actuales, llega al veredicto esperado en casos conocidos.

Uso (desde backend/, con ANTHROPIC_API_KEY y DATABASE_URL en el entorno o en .env):
    python -m scripts.eval_real            # los 5 casos
    python -m scripts.eval_real gold-3     # solo los casos cuyo id contenga "gold-3"
Sale con código 1 si algún caso no da el veredicto o el rango de score esperado.
"""

import asyncio
import sys
from datetime import datetime, timezone

from langchain_core.callbacks import get_usage_metadata_callback

from agents.contracts import EvaluationInputs, TCMetadata
from agents.llm_client import get_llm_client
from agents.pipeline import run_evaluation
from tests.golden.fixtures import GOLDEN_FIXTURES


async def main(only: str) -> int:
    llm, now, failures = get_llm_client(), datetime.now(timezone.utc), 0
    for fx in (f for f in GOLDEN_FIXTURES if only in f["id"]):
        inputs = EvaluationInputs(**fx["inputs"], exchange_rate_at=now, tc_source="user_provided")
        tc = TCMetadata(rate=inputs.exchange_rate_used, source="user_provided", fetched_at=now)
        with get_usage_metadata_callback() as cb:
            state = await run_evaluation(inputs, tc, llm)
        verdict = state["final_verdict"]
        lo, hi = fx["expected_score_range"]
        ok = verdict.veredicto == fx["expected_verdict"] and lo <= verdict.score_final <= hi
        failures += not ok
        tokens = sum(u["total_tokens"] for u in cb.usage_metadata.values())
        print(
            f"{'OK  ' if ok else 'FAIL'} {fx['id']}: {verdict.veredicto} ({verdict.score_final}) "
            f"— esperado {fx['expected_verdict']} [{lo}-{hi}] — {tokens} tokens"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "")))
