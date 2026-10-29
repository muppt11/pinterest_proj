"""FastAPI entry point for MoodBoards."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import get_settings
from app.deps import get_embedder
from app.routers import assistant, board, boards, characters, color, look, me, search, trips


class Health(BaseModel):
    """Response body for the health check."""

    status: str
    app: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """On shutdown, stop the embedding worker process if one was started."""
    yield
    if get_embedder.cache_info().currsize:
        embedder = get_embedder()
        if hasattr(embedder, "close"):
            embedder.close()


def create_app() -> FastAPI:
    """Build the FastAPI application with middleware and routers attached."""
    settings = get_settings()
    app = FastAPI(title="MoodBoards API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(search.router)
    app.include_router(board.router)
    app.include_router(look.router)
    app.include_router(assistant.router)
    app.include_router(boards.router)
    app.include_router(color.router)
    app.include_router(characters.router)
    app.include_router(me.router)
    app.include_router(trips.router)
    # check_dir=False so the API still starts (and tests run) before the dataset is downloaded.
    app.mount("/images", StaticFiles(directory=settings.images_dir, check_dir=False), name="images")

    @app.get("/health", response_model=Health)
    def health() -> Health:
        """Liveness check used by the Makefile and frontend."""
        return Health(status="ok", app="MoodBoards")

    return app


app = create_app()
