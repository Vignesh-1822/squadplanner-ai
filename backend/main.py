"""FastAPI application entry point."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import admin, hitl, refinements, trips
from config import configure_langsmith, settings
from db.client import close_client, get_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SquadPlanner API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trips.router)
app.include_router(hitl.router)
app.include_router(refinements.router)
app.include_router(admin.router)

debug_ui_dir = Path(__file__).parent / "debug_ui"
if debug_ui_dir.exists():
    app.mount("/debug", StaticFiles(directory=debug_ui_dir, html=True), name="debug-ui")


@app.on_event("startup")
async def startup() -> None:
    get_database()
    logger.info("MongoDB connected (database=squadplanner).")

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
    return {"status": "ok", "db": "connected"}
