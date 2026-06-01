"""Tests para agents/tools/tavily.py."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.tools.tavily import search_web


@pytest.fixture(autouse=True)
def clear_tavily_cache():
    import agents.tools.tavily as mod
    mod._cache.clear()
    yield
    mod._cache.clear()


@pytest.mark.asyncio
async def test_returns_empty_when_api_key_not_set(monkeypatch):
    """Sin API key configurada retorna string vacío (no aborta pipeline)."""
    import agents.tools.tavily as mod
    with patch.object(mod, "get_settings") as mock_gs:
        mock_gs.return_value.tavily_api_key.get_secret_value.return_value = ""
        result = await search_web("producto México precio")
    assert result == ""


@pytest.mark.asyncio
async def test_returns_formatted_results(monkeypatch):
    """Fetch exitoso retorna texto Markdown con título y contenido."""
    import agents.tools.tavily as mod

    mock_response = {
        "results": [
            {"title": "Producto en México", "content": "Precio promedio $500 MXN"},
            {"title": "Competencia directa", "content": "Similar a $480 MXN"},
        ]
    }

    fake_client = MagicMock()
    fake_client.search = AsyncMock(return_value=mock_response)

    with patch("tavily.AsyncTavilyClient", return_value=fake_client):
        with patch.object(mod, "get_settings") as mock_gs:
            mock_gs.return_value.tavily_api_key.get_secret_value.return_value = "fake-key"
            result = await search_web("Producto en México precio")

    assert "Producto en México" in result
    assert "Precio promedio $500 MXN" in result
    assert "Competencia directa" in result


@pytest.mark.asyncio
async def test_caches_result():
    """Segunda llamada con la misma query usa cache, no hace HTTP."""
    import agents.tools.tavily as mod

    call_count = 0
    mock_response = {"results": [{"title": "T", "content": "C"}]}

    async def fake_search(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_response

    fake_client = MagicMock()
    fake_client.search = fake_search

    with patch("tavily.AsyncTavilyClient", return_value=fake_client):
        with patch.object(mod, "get_settings") as mock_gs:
            mock_gs.return_value.tavily_api_key.get_secret_value.return_value = "fake-key"
            await search_web("misma query")
            await search_web("misma query")

    assert call_count == 1


@pytest.mark.asyncio
async def test_returns_empty_on_timeout():
    """Timeout retorna string vacío sin propagar excepción."""
    import asyncio
    import agents.tools.tavily as mod

    fake_client = MagicMock()
    fake_client.search = AsyncMock(side_effect=asyncio.TimeoutError())

    with patch("tavily.AsyncTavilyClient", return_value=fake_client):
        with patch.object(mod, "get_settings") as mock_gs:
            mock_gs.return_value.tavily_api_key.get_secret_value.return_value = "fake-key"
            result = await search_web("query que da timeout")

    assert result == ""
