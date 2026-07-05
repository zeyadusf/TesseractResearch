"""
app/api/main.py
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langsmith import Client as LangSmithClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.agent.checkpoint_memory import create_checkpointer
from app.agent.graph import build_graph
from app.api.routers.research_router import router as research_router
from app.core.config import get_setting
from app.core.dependencies import close_dispatchers
from app.core.logging import get_logger

settings = get_setting()
logger = get_logger("Main")

limiter = Limiter(key_func=get_remote_address)
langsmith_client = LangSmithClient()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting TesseractResearch API", extra={"version": settings.APP_VERSION})

    checkpointer, ctx = await create_checkpointer()

    try:
        await checkpointer.setup()
        logger.info("Checkpointer ready — checkpoint tables verified")

        app.state.graph = await build_graph(checkpointer)
        logger.info("Graph compiled and attached to app.state")

        yield

    finally:
        logger.info("Shutting down — flushing LangSmith traces")
        langsmith_client.flush()

        logger.info("Shutting down — closing checkpointer")
        await ctx.__aexit__(None, None, None)

        logger.info("Closing dispatchers")
        await close_dispatchers()

        logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Autonomous AI research agent with Human-in-the-Loop approval.",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else ["http://localhost:5500",
        "http://127.0.0.1:5500",
        "tesseractresearch.ziayd-usf.workers.dev",], 
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(research_router)

    @app.get("/health", tags=["meta"], summary="Liveness probe")
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "version": settings.APP_VERSION})

    return app


app = create_app()