"""Tests para agents/tools/banxico.py — cache diario + fetch + fallback."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest

from agents.tools.banxico import get_usd_mxn


MOCK_RESPONSE = {
    "bmx": {
        "series": [{"datos": [{"fecha": "01/06/2026", "dato": "17.1234"}]}]
    }
}


class _FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return MOCK_RESPONSE


class _FakeClient:
    def __init__(self, **_kw) -> None:
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        pass

    async def get(self, url: str, *, headers=None):
        self.calls += 1
        return _FakeResponse()


@pytest.fixture(autouse=True)
def clear_banxico_cache():
    import agents.tools.banxico as mod
    mod._cache.clear()
    yield
    mod._cache.clear()


@pytest.mark.asyncio
async def test_fetch_real_banxico(monkeypatch):
    """Fetch exitoso: parsea rate, source='banxico', guarda en cache."""
    fake = _FakeClient()
    monkeypatch.setattr("agents.tools.banxico.httpx.AsyncClient", lambda **kw: fake)

    rate, source = await get_usd_mxn()

    assert source == "banxico"
    assert rate == Decimal("17.1234")
    assert fake.calls == 1


@pytest.mark.asyncio
async def test_second_call_uses_cache(monkeypatch):
    """Segunda llamada el mismo día no hace HTTP."""
    fake = _FakeClient()
    monkeypatch.setattr("agents.tools.banxico.httpx.AsyncClient", lambda **kw: fake)

    await get_usd_mxn()  # first call populates cache
    rate2, source2 = await get_usd_mxn()  # second call

    assert fake.calls == 1  # solo una llamada HTTP
    assert source2 == "banxico"
    assert rate2 == Decimal("17.1234")


@pytest.mark.asyncio
async def test_fallback_when_api_fails_with_cache(monkeypatch):
    """Si API falla y hay cache viejo, retorna fallback sin propagar error."""
    import agents.tools.banxico as mod
    mod._cache[date(2026, 5, 30)] = Decimal("17.50")

    class _FailClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def get(self, *_a, **_kw): raise httpx.ConnectError("sin red")

    monkeypatch.setattr("agents.tools.banxico.httpx.AsyncClient", lambda **kw: _FailClient())

    rate, source = await get_usd_mxn()

    assert source == "fallback"
    assert rate == Decimal("17.50")


@pytest.mark.asyncio
async def test_raises_when_no_cache_and_api_fails(monkeypatch):
    """Sin cache + API caída → propaga la excepción."""
    class _FailClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def get(self, *_a, **_kw): raise httpx.ConnectError("sin red")

    monkeypatch.setattr("agents.tools.banxico.httpx.AsyncClient", lambda **kw: _FailClient())

    with pytest.raises(httpx.ConnectError):
        await get_usd_mxn()
