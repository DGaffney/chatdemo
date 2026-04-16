"""FastAPI application entrypoint.

Wires the HTTP surface, CORS, the three API routers (parent chat, operator
dashboard, onboarding), and the lifespan hook that boots persistence and the
knowledge base. On startup the lifespan:

1. Initializes SQLite (``init_db``).
2. Loads the markdown handbook into the in-memory chunk pool.
3. Scans ``settings.documents_path`` for PDFs and runs any that aren't
   already stored through the document ingestion pipeline.
4. Hydrates the chunk pool with active document chunks so the retriever
   sees both markdown and PDF content.

Also mounts the built frontend at ``/`` when a ``static/`` directory is
present (production Docker build).
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.db.database import init_db, close_db
from backend.knowledge.loader import load_handbook
from backend.knowledge.documents.bootstrap import (
    hydrate_chunk_pool,
    scan_and_ingest,
)
from backend.settings import settings
from backend.api.parent import router as parent_router
from backend.api.operator import router as operator_router
from backend.api.onboarding import router as onboarding_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    load_handbook()
    await scan_and_ingest(settings.documents_path)
    await hydrate_chunk_pool()
    yield
    await close_db()


app = FastAPI(title="AI Front Desk", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parent_router, prefix="/api")
app.include_router(operator_router, prefix="/api")
app.include_router(onboarding_router, prefix="/api")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir) and os.listdir(static_dir):
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    index_path = os.path.join(static_dir, "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)

        candidate = os.path.join(static_dir, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)

        return FileResponse(index_path)
