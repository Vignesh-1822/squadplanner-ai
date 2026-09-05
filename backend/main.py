"""FastAPI application entry point."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api import admin, hitl, refinements, squad, trips
from api.middleware.rate_limit import limiter
from api.routes import auth
from config import configure_langsmith, settings
from db.client import close_client, get_database
from db.indexes import ensure_indexes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SquadPlanner API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(trips.router, prefix="/api")
app.include_router(squad.router, prefix="/api")
app.include_router(hitl.router, prefix="/api")
app.include_router(refinements.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

debug_ui_dir = Path(__file__).resolve().parent / "debug_ui"
app.mount("/debug", StaticFiles(directory=debug_ui_dir, html=True), name="debug")


@app.on_event("startup")
async def startup() -> None:
    db = get_database()
    try:
        await db.command("ping")
        logger.info("MongoDB connected (database=squadplanner).")
    except Exception as exc:
        logger.error("MongoDB connection failed: %s", exc)

    try:
        await ensure_indexes()
    except Exception as exc:
        logger.error("Failed to ensure MongoDB indexes: %s", exc)

    configure_langsmith()
    if settings.langchain_tracing_v2.lower() == "true":
        logger.info("LangSmith tracing enabled (project=%s).", settings.langchain_project)

    from agent.graph import initialize_graph

    await initialize_graph()
    logger.info("LangGraph orchestrator initialized.")


@app.on_event("shutdown")
async def shutdown() -> None:
    close_client()


@app.get("/health")
async def health():
    db = get_database()
    try:
        await db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "unreachable"
    return {"status": "ok", "db": db_status}
