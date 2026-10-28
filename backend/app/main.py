"""FastAPI entry point for MoodBoards."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import get_settings


class Health(BaseModel):
    """Response body for the health check."""

    status: str
    app: str


def create_app() -> FastAPI:
    """Build the FastAPI application with middleware and routers attached."""
    settings = get_settings()
    app = FastAPI(title="MoodBoards API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=Health)
    def health() -> Health:
        """Liveness check used by the Makefile and frontend."""
        return Health(status="ok", app="MoodBoards")

    return app


app = create_app()
