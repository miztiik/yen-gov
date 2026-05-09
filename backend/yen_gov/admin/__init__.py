"""yen-gov admin app — local-only FastAPI surface.

This package is a **dev-only** wrapper around the same pipeline code the
CLI uses. It is bound to localhost (127.0.0.1) and is never deployed:
the public app on GitHub Pages must function with no backend
(CLAUDE.md Holy Law #1; see docs/architecture/admin/overview.md).

Run locally:

    uvicorn yen_gov.admin:app --reload --port 8000

The companion Svelte app lives under ``admin/`` at the repo root and
proxies ``/api/*`` to this server.

Phase 4 — walking skeleton: only the inventory endpoint is implemented.
Schemas, pipeline, and patches panels follow once the topology is proven.
"""

from .app import app

__all__ = ["app"]
