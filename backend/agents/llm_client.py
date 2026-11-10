"""LLM client wrapper para Kisabella Financial Product Release.

ADR-007: langchain-anthropic + with_structured_output.
ADR-003: validación de outputs LLM con Pydantic acá, no en cada agente.

Tipos:
- LLMClient: Protocol (interface estructural).
- AnthropicLLMClient: implementación real (ChatAnthropic).
- FakeLLMClient: test double, cero red.
- get_llm_client(): singleton lazy cacheado.

Retries: tenacity 3x exponencial en RateLimitError/APITimeoutError/APIConnectionError.
NO retry en ValidationError (output malformado != problema transitorio).

Prompt caching: TODO Sprint 6 (cache_control en system block).
"""

from __future__ import annotations

import structlog
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol, TypeVar

from anthropic import APIConnectionError, APITimeoutError, RateLimitError
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)

# Default parameters
DEFAULT_TEMPERATURE = 0.2  # bajo para outputs estructurados deterministas
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT_S = 60
MAX_RETRIES = 3


class LLMClient(Protocol):
    """Interface estructural — Anthropic real o Fake en tests."""

    async def request_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        temperature: float | None = None,
    ) -> T:
        """Llama al LLM y retorna el output validado contra `schema`."""
        ...

    async def stream_text(
        self,
        messages: list,
        temperature: float = 0.4,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        """Emite tokens de texto. Sin structured output. ADR-017."""
        ...


class AnthropicLLMClient:
    """Implementación real usando ChatAnthropic + with_structured_output."""

    def __init__(
        self,
        settings: Settings,
        *,
        llm_factory=None,
    ) -> None:
        self._settings = settings
        if llm_factory is None:
            self._llm = ChatAnthropic(
                model=settings.anthropic_model,
                api_key=settings.anthropic_api_key.get_secret_value(),
                temperature=DEFAULT_TEMPERATURE,
                max_tokens=DEFAULT_MAX_TOKENS,
                timeout=DEFAULT_TIMEOUT_S,
                max_retries=0,  # tenacity maneja retries
            )
        else:
            self._llm = llm_factory()

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(MAX_RETRIES),
        retry=retry_if_exception_type(
            (RateLimitError, APITimeoutError, APIConnectionError)
        ),
        reraise=True,
    )
    async def request_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        temperature: float | None = None,
    ) -> T:
        llm = self._llm
        if temperature is not None:
            llm = llm.bind(temperature=temperature)

        structured = llm.with_structured_output(schema, method="function_calling")
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        return await structured.ainvoke(messages)  # type: ignore[return-value]

    async def stream_text(
        self,
        messages: list,
        temperature: float = 0.4,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        llm = ChatAnthropic(
            model=self._settings.anthropic_model,
            api_key=self._settings.anthropic_api_key.get_secret_value(),
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=DEFAULT_TIMEOUT_S,
            max_retries=0,
        )
        async for chunk in llm.astream(messages):
            if chunk.content and isinstance(chunk.content, str):
                yield chunk.content


@dataclass
class FakeCall:
    """Registro de una llamada a FakeLLMClient.request_structured."""

    system: str
    user: str
    schema: type[BaseModel]
    temperature: float | None


class FakeLLMClient:
    """Test double — cero red.

    Setup patterns:
        # 1. By schema:
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, AgentResult(score=72, ...))

        # 2. Queue FIFO (para múltiples agentes en pipeline):
        fake = FakeLLMClient()
        fake.queue_responses([result1, result2, result3, result4])

        # 3. Excepción simulada:
        fake.queue_exception(RateLimitError("..."))
    """

    def __init__(self) -> None:
        self.calls: list[FakeCall] = []
        self._queue: deque[BaseModel | Exception] = deque()
        self._by_schema: dict[type[BaseModel], BaseModel] = {}
        self._stream_tokens: list[str] = []
        self._stream_error: Exception | None = None

    def set_response_for(self, schema: type[BaseModel], response: BaseModel) -> None:
        self._by_schema[schema] = response

    def queue_responses(self, responses: list[BaseModel]) -> None:
        self._queue.extend(responses)

    def queue_exception(self, exc: Exception) -> None:
        self._queue.append(exc)

    async def request_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        temperature: float | None = None,
    ) -> T:
        self.calls.append(FakeCall(system, user, schema, temperature))

        if self._queue:
            item = self._queue.popleft()
            if isinstance(item, Exception):
                raise item
            return item  # type: ignore[return-value]

        if schema in self._by_schema:
            return self._by_schema[schema]  # type: ignore[return-value]

        raise LookupError(
            f"FakeLLMClient: no response configurada para {schema.__name__}. "
            f"Llamadas hechas: {len(self.calls)}"
        )

    def queue_stream(self, tokens: list[str]) -> None:
        self._stream_tokens = list(tokens)

    def queue_stream_error(self, error: Exception) -> None:
        self._stream_error = error

    async def stream_text(
        self,
        messages: list,
        temperature: float = 0.4,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        if self._stream_error is not None:
            err = self._stream_error
            self._stream_error = None
            raise err
        tokens = list(self._stream_tokens)
        self._stream_tokens = []
        for token in tokens:
            yield token


class BudgetExhaustedError(Exception):
    """Raised when a per-evaluation budget cap is exceeded."""

    def __init__(self, resource: str, used: int, limit: int) -> None:
        self.resource = resource
        self.used = used
        self.limit = limit
        super().__init__(
            f"Budget exhausted: {resource} — used {used}, limit {limit}"
        )


class BudgetedLLMClient:
    """Wrapper that enforces per-evaluation hard caps on LLM usage.

    Caps:
    - max_calls: 6 (4 agents + margin for retries)
    - max_input_tokens: 20,000
    """

    def __init__(
        self,
        inner: LLMClient,
        max_calls: int = 6,
        max_input_tokens: int = 20_000,
    ) -> None:
        self._inner = inner
        self._max_calls = max_calls
        self._max_input_tokens = max_input_tokens
        self._calls_used = 0
        self._tokens_used = 0

    def _estimate_tokens(self, system: str, user: str) -> int:
        return (len(system) + len(user)) // 4

    async def request_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        temperature: float | None = None,
    ) -> T:
        if self._calls_used >= self._max_calls:
            raise BudgetExhaustedError("calls", self._calls_used, self._max_calls)

        estimated = self._estimate_tokens(system, user)
        if self._tokens_used + estimated > self._max_input_tokens:
            raise BudgetExhaustedError(
                "tokens", self._tokens_used + estimated, self._max_input_tokens
            )

        self._calls_used += 1
        self._tokens_used += estimated
        result = await self._inner.request_structured(
            system=system, user=user, schema=schema, temperature=temperature
        )
        structlog.get_logger().info(
            "llm_call",
            schema=schema.__name__,
            tokens_estimated=estimated,
            calls_used=self._calls_used,
            calls_max=self._max_calls,
        )
        return result

    @property
    def budget_summary(self) -> dict:
        return {
            "calls_used": self._calls_used,
            "calls_max": self._max_calls,
            "tokens_estimated": self._tokens_used,
            "tokens_max": self._max_input_tokens,
        }


@lru_cache(maxsize=1)
def get_llm_client() -> AnthropicLLMClient:
    """Singleton lazy. Llama get_settings() y construye AnthropicLLMClient.

    En tests, instanciar FakeLLMClient o AnthropicLLMClient directo
    para evitar leer .env real.
    """
    return AnthropicLLMClient(get_settings())
