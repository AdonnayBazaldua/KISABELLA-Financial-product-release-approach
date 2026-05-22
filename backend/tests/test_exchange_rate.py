import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from main import app


@pytest.mark.asyncio
async def test_get_exchange_rate_returns_float():
    mock_response = {
        "bmx": {
            "series": [{
                "datos": [{"dato": "19.8234"}]
            }]
        }
    }
    with patch("api.exchange_rate.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_instance.get.return_value.json.return_value = mock_response
        mock_instance.get.return_value.raise_for_status = lambda: None

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/exchange-rate")

    assert response.status_code == 200
    data = response.json()
    assert "rate" in data
    assert isinstance(data["rate"], float)
    assert data["rate"] == 19.8234


@pytest.mark.asyncio
async def test_get_exchange_rate_fallback_on_error():
    with patch("api.exchange_rate.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_instance.get.side_effect = Exception("timeout")

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/exchange-rate")

    assert response.status_code == 200
    data = response.json()
    assert "rate" in data
    assert data["source"] == "fallback"
