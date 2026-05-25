"""Tests para agents.llm_client — AnthropicLLMClient y FakeLLMClient."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from anthropic import APIConnectionError, APITimeoutError, RateLimitError
from pydantic import BaseModel

from agents.contracts import AgentResult
from agents.llm_client import (
    DEFAULT_TEMPERATURE,
    AnthropicLLMClient,
    FakeCall,
    FakeLLMClient,
)
from core.config import Settings


# --- Fixtures ---


def _valid_settings_kwargs(**overrides):
    base = dict(
        anthropic_api_key="sk-ant-test",
        database_url="postgresql+psycopg://u:p@db:5432/test",
        secret_key="x" * 32,
    )
    base.update(overrides)
    return base


@pytest.fixture
def fake_settings():
    return Settings(_env_file=None, **_valid_settings_kwargs())


def _make_agent_result(score: int = 75) -> AgentResult:
    return AgentResult(
        score=score,
        veredicto_corto="veredicto de prueba para test unitario",
        analisis_extenso="x" * 400,
        hallazgos_clave=["hallazgo de prueba"],
        recomendaciones=["recomendación de prueba"],
    )


# --- FakeLLMClient tests ---


class TestFakeLLMClient:
    async def test_by_schema_response(self):
        fake = FakeLLMClient()
        expected = _make_agent_result(score=80)
        fake.set_response_for(AgentResult, expected)

        result = await fake.request_structured(
            system="sys", user="usr", schema=AgentResult
        )
        assert result.score == 80
        assert result is expected

    async def test_queue_fifo_order(self):
        fake = FakeLLMClient()
        r1 = _make_agent_result(score=60)
        r2 = _make_agent_result(score=70)
        r3 = _make_agent_result(score=80)
        fake.queue_responses([r1, r2, r3])

        a = await fake.request_structured(system="s", user="u", schema=AgentResult)
        b = await fake.request_structured(system="s", user="u", schema=AgentResult)
        c = await fake.request_structured(system="s", user="u", schema=AgentResult)

        assert (a.score, b.score, c.score) == (60, 70, 80)

    async def test_queue_takes_priority_over_by_schema(self):
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _make_agent_result(score=10))
        fake.queue_responses([_make_agent_result(score=99)])

        result = await fake.request_structured(
            system="s", user="u", schema=AgentResult
        )
        assert result.score == 99

    async def test_records_calls(self):
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _make_agent_result())

        await fake.request_structured(
            system="prompt sistema", user="input usuario", schema=AgentResult
        )
        await fake.request_structured(
            system="otro sys", user="otro usr", schema=AgentResult, temperature=0.7
        )

        assert len(fake.calls) == 2
        assert fake.calls[0].system == "prompt sistema"
        assert fake.calls[0].user == "input usuario"
        assert fake.calls[0].schema is AgentResult
        assert fake.calls[0].temperature is None
        assert fake.calls[1].temperature == 0.7

    async def test_queue_exception(self):
        fake = FakeLLMClient()
        fake.queue_exception(RateLimitError("simulado", response=MagicMock(), body=None))

        with pytest.raises(RateLimitError):
            await fake.request_structured(system="s", user="u", schema=AgentResult)

    async def test_raises_when_no_response_configured(self):
        fake = FakeLLMClient()
        with pytest.raises(LookupError, match="AgentResult"):
            await fake.request_structured(system="s", user="u", schema=AgentResult)


# --- AnthropicLLMClient tests ---


class _OkResponse(BaseModel):
    text: str


class TestAnthropicLLMClientInit:
    def test_uses_settings_for_model(self, fake_settings):
        captured = {}

        def factory():
            mock = MagicMock()
            captured["called"] = True
            return mock

        client = AnthropicLLMClient(fake_settings, llm_factory=factory)
        assert captured["called"]
        assert client._settings is fake_settings


class TestAnthropicLLMClientRequest:
    async def test_calls_with_structured_output(self, fake_settings):
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=_OkResponse(text="hello"))
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        client = AnthropicLLMClient(fake_settings, llm_factory=lambda: mock_llm)
        result = await client.request_structured(
            system="sys prompt", user="usr msg", schema=_OkResponse
        )

        assert result.text == "hello"
        mock_llm.with_structured_output.assert_called_once_with(
            _OkResponse, method="function_calling"
        )

    async def test_temperature_override_applies_bind(self, fake_settings):
        mock_llm = MagicMock()
        mock_bound = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=_OkResponse(text="ok"))
        mock_bound.with_structured_output = MagicMock(return_value=mock_structured)
        mock_llm.bind = MagicMock(return_value=mock_bound)

        client = AnthropicLLMClient(fake_settings, llm_factory=lambda: mock_llm)
        await client.request_structured(
            system="s", user="u", schema=_OkResponse, temperature=0.9
        )

        mock_llm.bind.assert_called_once_with(temperature=0.9)

    async def test_no_temperature_override_skips_bind(self, fake_settings):
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=_OkResponse(text="ok"))
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        client = AnthropicLLMClient(fake_settings, llm_factory=lambda: mock_llm)
        await client.request_structured(system="s", user="u", schema=_OkResponse)

        mock_llm.bind.assert_not_called()


class TestAnthropicLLMClientRetry:
    async def test_retries_on_rate_limit(self, fake_settings):
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        # Falla 2x, OK la 3ra
        mock_structured.ainvoke = AsyncMock(
            side_effect=[
                RateLimitError("first", response=MagicMock(), body=None),
                RateLimitError("second", response=MagicMock(), body=None),
                _OkResponse(text="finally ok"),
            ]
        )
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        client = AnthropicLLMClient(fake_settings, llm_factory=lambda: mock_llm)
        result = await client.request_structured(
            system="s", user="u", schema=_OkResponse
        )

        assert result.text == "finally ok"
        assert mock_structured.ainvoke.await_count == 3

    async def test_retries_on_timeout(self, fake_settings):
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(
            side_effect=[
                APITimeoutError(request=MagicMock()),
                _OkResponse(text="ok"),
            ]
        )
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        client = AnthropicLLMClient(fake_settings, llm_factory=lambda: mock_llm)
        result = await client.request_structured(
            system="s", user="u", schema=_OkResponse
        )

        assert result.text == "ok"
        assert mock_structured.ainvoke.await_count == 2

    async def test_gives_up_after_3_attempts(self, fake_settings):
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(
            side_effect=APIConnectionError(request=MagicMock())
        )
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        client = AnthropicLLMClient(fake_settings, llm_factory=lambda: mock_llm)
        with pytest.raises(APIConnectionError):
            await client.request_structured(
                system="s", user="u", schema=_OkResponse
            )

        assert mock_structured.ainvoke.await_count == 3

    async def test_no_retry_on_validation_error(self, fake_settings):
        """ValidationError no es transitorio — output malformado != worth retrying."""
        from pydantic import ValidationError

        mock_llm = MagicMock()
        mock_structured = MagicMock()

        # ValidationError requires error info, simulamos con genérica
        mock_structured.ainvoke = AsyncMock(
            side_effect=ValueError("simulando validation issue")
        )
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        client = AnthropicLLMClient(fake_settings, llm_factory=lambda: mock_llm)
        with pytest.raises(ValueError):
            await client.request_structured(
                system="s", user="u", schema=_OkResponse
            )

        # Solo 1 intento, no retries
        assert mock_structured.ainvoke.await_count == 1


class TestDefaults:
    def test_default_temperature_is_low(self):
        # Output estructurado requiere baja varianza
        assert DEFAULT_TEMPERATURE <= 0.3
