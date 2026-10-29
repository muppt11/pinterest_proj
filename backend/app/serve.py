"""Production entry point (Hugging Face Spaces / Docker): the API under /api and the built React app
at /, with client-side routes (e.g. /item/<id>, /trips/3) falling back to index.html.

Local development doesn't use this: Vite serves the frontend and proxies /api to app.main.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import REPO_ROOT
from app.main import create_app, lifespan

DIST = REPO_ROOT / "frontend" / "dist"

app = FastAPI(title="MoodBoards", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/api", create_app())
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> FileResponse:
    """Serve a built file if it exists (logo, favicon), else the app shell for client-side routing."""
    candidate = (DIST / path).resolve()
    if path and candidate.is_file() and DIST.resolve() in candidate.parents:
        return FileResponse(candidate)
    index = DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="Frontend not built. Run `npm run build` in frontend/.")
    return FileResponse(index)

