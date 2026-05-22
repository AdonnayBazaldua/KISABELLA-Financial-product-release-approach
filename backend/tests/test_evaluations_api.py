import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from main import app


SAMPLE_PAYLOAD = {
    "name": "Test Producto",
    "product_name": "Silla de Madera",
    "description": "Silla artesanal importada",
    "category": "fisico",
    "cost_purchase": 500.0,
    "cost_purchase_usd": 25.0,
    "cost_freight": 80.0,
    "cost_customs": 50.0,
    "cost_storage": 600.0,
    "cost_logistics_vehicle": 100.0,
    "cost_logistics_viaticos": 50.0,
    "cost_logistics_personnel": 150.0,
    "cost_shrinkage_pct": 2.0,
    "cost_commission_pct": 10.0,
    "cost_marketing": 1000.0,
    "cost_overhead": 500.0,
    "target_price": 1200.0,
    "estimated_units_month": 50,
    "sales_channel": "marketplace",
    "exchange_rate_used": 19.50,
}


@pytest.mark.asyncio
async def test_list_evaluations_returns_200():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/evaluations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
