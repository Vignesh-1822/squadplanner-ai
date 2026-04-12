"""FastAPI application entry point."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
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

# TODO: include routers when implemented:
# from api import trips, hitl, admin
# app.include_router(trips.router, prefix="/api")
# app.include_router(hitl.router, prefix="/api")
# app.include_router(admin.router, prefix="/api")


@app.on_event("startup")
async def startup() -> None:
    get_database()
    logger.info("MongoDB connected (database=squadplanner).")

    if settings.langchain_tracing_v2.lower() == "true":
        os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        if settings.langchain_api_key:
            os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        logger.info("LangSmith tracing enabled (project=%s).", settings.langchain_project)


@app.on_event("shutdown")
async def shutdown() -> None:
    close_client()


@app.get("/health")
async def health():
    return {"status": "ok", "db": "connected"}
