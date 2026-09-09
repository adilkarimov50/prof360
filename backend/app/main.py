"""Точка входа API «Профилактика 360»."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    ai,
    analytics_api,
    audit,
    auth,
    commission,
    commission_sessions,
    dashboard,
    ingest,
    legal,
    localities,
    persons,
    reports,
)
from app.bootstrap import ensure_default_admin
from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.security_middleware import SecurityMiddleware
from app.ai import llm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("prof360")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s", settings.app_name)
    init_db()
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Профилактика 360 — Прокуратура Алматинской области",
    description="Информационно-аналитическая система профилактики правонарушений.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Export-Id"],
)

for r in (auth, dashboard, persons, legal, localities, analytics_api, ai, reports, audit, admin, ingest, commission, commission_sessions):
    app.include_router(r.router, prefix=settings.api_prefix)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/health/ready")
def health_ready():
    """Readiness: DB + optional LLM."""
    db_ok = False
    db = SessionLocal()
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    finally:
        db.close()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "llm": llm.info(),
    }
