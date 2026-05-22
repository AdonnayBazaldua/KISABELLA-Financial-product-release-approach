import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_response_mock(json_payload, raises=None):
    """Build a fake httpx response whose .json() is sync and .raise_for_status() is sync."""
    response = MagicMock()
    response.json.return_value = json_payload
    if raises is None:
        response.raise_for_status = MagicMock(return_value=None)
    else:
        response.raise_for_status = MagicMock(side_effect=raises)
    return response


@pytest.mark.asyncio
async def test_get_exchange_rate_returns_float(client):
    mock_payload = {
        "bmx": {
            "series": [{
                "datos": [{"dato": "19.8234"}]
            }]
        }
    }
    with patch("api.exchange_rate.httpx.AsyncClient") as mock_client_cls:
        async_client = AsyncMock()
        async_client.get.return_value = _make_response_mock(mock_payload)
        mock_client_cls.return_value.__aenter__.return_value = async_client

        response = await client.get("/api/exchange-rate")

    assert response.status_code == 200
    data = response.json()
    assert "rate" in data
    assert isinstance(data["rate"], float)
    assert data["rate"] == 19.8234
    assert data["source"] == "banxico"


@pytest.mark.asyncio
async def test_get_exchange_rate_fallback_on_error(client):
    with patch("api.exchange_rate.httpx.AsyncClient") as mock_client_cls:
        async_client = AsyncMock()
        async_client.get.side_effect = Exception("timeout")
        mock_client_cls.return_value.__aenter__.return_value = async_client

        response = await client.get("/api/exchange-rate")

    assert response.status_code == 200
    data = response.json()
    assert "rate" in data
    assert data["source"] == "fallback"
    assert data["rate"] == 19.50
