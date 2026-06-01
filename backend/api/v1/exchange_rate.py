"""Endpoint GET /api/v1/tc — tipo de cambio USD/MXN desde Banxico."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.tools.banxico import get_usd_mxn

router = APIRouter(prefix="/api/v1", tags=["tc"])


class TCResponse(BaseModel):
    rate: float
    date: str
    source: str


@router.get("/tc", response_model=TCResponse)
async def get_tc() -> TCResponse:
    """Retorna el tipo de cambio USD/MXN. Source = 'banxico' | 'fallback'."""
    try:
        rate, source = await get_usd_mxn()
        return TCResponse(
            rate=float(rate),
            date=date.today().isoformat(),
            source=source,
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Tipo de cambio no disponible. Intente nuevamente.",
        )
