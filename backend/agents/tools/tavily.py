"""Búsqueda web vía Tavily con cache 24h en memoria.

ADR-011: llamada directa antes del LLM call, no via bind_tools.
En fallo (timeout, API error, key vacía) retorna string vacío — pipeline continúa.
Cache keyed por sha256(query). Se pierde al reiniciar el proceso.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

from core.config import get_settings

_CACHE_TTL = timedelta(hours=24)
_cache: dict[str, tuple[datetime, str]] = {}


async def search_web(query: str, max_results: int = 5) -> str:
    """Busca en web y retorna resultados como Markdown. String vacío en fallo."""
    key = hashlib.sha256(query.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    if key in _cache:
        cached_at, result = _cache[key]
        if now - cached_at < _CACHE_TTL:
            return result

    settings = get_settings()
    api_key = settings.tavily_api_key.get_secret_value()
    if not api_key:
        return ""

    try:
        from tavily import AsyncTavilyClient  # type: ignore[import]

        client = AsyncTavilyClient(api_key=api_key)
        response = await asyncio.wait_for(
            client.search(query, max_results=max_results),
            timeout=15.0,
        )
        results = response.get("results", [])
        text = "\n\n".join(
            f"**{r.get('title', '')}**\n{r.get('content') or r.get('snippet', '')}"
            for r in results
        )
        # Evict expired entries
        expired = [k for k, (ts, _) in list(_cache.items()) if now - ts >= _CACHE_TTL]
        for k in expired:
            del _cache[k]
        _cache[key] = (now, text)
        return text

    except Exception:
        return ""
