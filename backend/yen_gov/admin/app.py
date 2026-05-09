"""FastAPI application factory and CORS setup for the local admin app.

The admin frontend served by Vite proxies ``/api/*`` here, so in
production-of-the-admin (i.e. when the operator runs both servers) all
requests share the origin and CORS is irrelevant. We still allow
``http://localhost:5174`` explicitly in case the operator hits the API
from a different port during exploration.

No authentication: uvicorn binds ``127.0.0.1`` (the user controls that
in the launch command) and the surface is single-user-developer.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from .inventory import router as inventory_router

app = FastAPI(
    title="yen-gov admin",
    version=__version__,
    description=(
        "Local-only operator console for yen-gov. Wraps the existing "
        "pipeline; reads datasets/ and (later) writes datasets/patches/. "
        "Never deployed to public hosting."
    ),
)

# The admin Svelte dev server runs on 5174 (5173 is the public app). When
# both run via the convenience script, vite proxies /api -> here and the
# request shares origin; this list covers the case where someone hits the
# API from a separately-launched dev server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe — used by the Vite proxy to confirm the API is up."""
    return {"status": "ok", "version": __version__}


app.include_router(inventory_router, prefix="/api", tags=["inventory"])
