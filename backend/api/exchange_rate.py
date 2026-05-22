from datetime import datetime, timezone
import httpx
from fastapi import APIRouter

router = APIRouter()

BANXICO_URL = (
    "https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF60653/datos/oportuno"
)
FALLBACK_RATE = 19.50


@router.get("/exchange-rate")
async def get_exchange_rate():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(BANXICO_URL)
            response.raise_for_status()
            data = response.json()
            rate_str = data["bmx"]["series"][0]["datos"][0]["dato"]
            rate = float(rate_str)
            return {
                "rate": rate,
                "source": "banxico",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception:
        return {
            "rate": FALLBACK_RATE,
            "source": "fallback",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
