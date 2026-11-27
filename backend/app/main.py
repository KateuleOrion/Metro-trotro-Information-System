"""Metro Trotro Information System - backend API (FastAPI + PostgreSQL).

Start it with:  uvicorn app.main:app --reload
Interactive documentation: http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config, db
from .errors import ApiError
from .routers import (activity, auth, catalog, driver_requests, passenger, queue, staff_accounts, sync, tracking,
                      trips, vehicles)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.open_pool()
    yield
    db.close_pool()


app = FastAPI(
    title="Metro Trotro Information System API",
    version="1.0.0",
    description="Queue, vehicle, trip and passenger information for a trotro station.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Turn validation problems into one readable sentence, e.g. 'capacity: Input should be at least 1'."""
    parts = []
    for e in exc.errors():
        field = ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path"))
        parts.append(f"{field}: {e['msg']}" if field else e["msg"])
    return JSONResponse(status_code=422, content={"detail": "; ".join(parts)})


@app.get("/health", tags=["Health"])
def health(conn=Depends(db.get_conn, scope="function")):
    conn.execute("SELECT 1")
    return {"status": "ok", "database": "ok"}


for module in (auth, staff_accounts, catalog, driver_requests, vehicles, queue, trips, passenger, sync, tracking, activity):
    app.include_router(module.router)
