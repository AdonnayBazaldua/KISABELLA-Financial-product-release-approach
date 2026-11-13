"""Tipo de cambio USD/MXN desde API Banxico con cache diario en memoria.

Cache keyed por date.today(). Al reiniciar el proceso se pierde — re-fetch inmediato.
En fallo: usa último valor cacheado (fallback). Sin cache Y API caída → propaga excepción.
NUNCA loguear el token de Banxico.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import httpx

from core.config import get_settings

_cache: dict[date, Decimal] = {}


async def get_usd_mxn() -> tuple[Decimal, str]:
    """Retorna (rate, source) donde source = 'banxico' | 'fallback'."""
    today = date.today()
    if today in _cache:
        return _cache[today], "banxico"

    settings = get_settings()
    url = settings.banxico_url
    token = settings.banxico_token.get_secret_value()

    try:
        if not token:
            raise RuntimeError("BANXICO_TOKEN no configurado")
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers={"Bmx-Token": token})
            resp.raise_for_status()
            data = resp.json()
            rate_str = data["bmx"]["series"][0]["datos"][0]["dato"]
            rate = Decimal(rate_str)

        _cache[today] = rate
        # Limpiar entradas con más de 1 día (mantener hoy y ayer como fallback)
        stale = [d for d in list(_cache) if d < today - timedelta(days=1)]
        for d in stale:
            del _cache[d]

        return rate, "banxico"

    except Exception:
        if _cache:
            last_rate = _cache[max(_cache)]
            return last_rate, "fallback"
        raise
