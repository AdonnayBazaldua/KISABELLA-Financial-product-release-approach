from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import secure

from api.evaluations import router as evaluations_router
from api.exchange_rate import router as exchange_rate_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="CAPI kisabella API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

secure_headers = secure.Secure()


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in secure_headers.headers().items():
        response.headers[header] = value
    return response


app.include_router(evaluations_router, prefix="/api")
app.include_router(exchange_rate_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
