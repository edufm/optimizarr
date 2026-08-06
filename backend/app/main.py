from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config as cfg
from .routers import dashboard, folders, jobs, sample, settings

app = FastAPI(title="optimizarr")

# Só relevante em dev (Vite em :5173 falando com uvicorn em :8000); em produção o
# frontend buildado é servido pelo próprio processo, mesma origem, sem CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(folders.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(sample.router, prefix="/api")

if cfg.FRONTEND_DIST.is_dir():
    assets_dir = cfg.FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        candidate = cfg.FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(cfg.FRONTEND_DIST / "index.html")
