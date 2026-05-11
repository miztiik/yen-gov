"""ECI Recon endpoints — discover, compare, and pin category_ids.

The admin GUI Recon panel uses this surface to manage
``config/eci-pins.json`` without touching code. Three responsibilities:

* **Sweep** — enumerate ECI's category_id space (1..N) by calling
  ``/eci-backend/public/api/election-result?category_id=<n>`` with the
  browser-style header recipe that bypasses the Akamai filter. Returns
  cat_name + index_url for every hit.

* **Pins** — read and write ``config/eci-pins.json`` (the single
  source of truth that ``backend/yen_gov/sources/eci/categories.py``
  loads at import). Writes go through jsonschema validation against
  ``datasets/schemas/eci_pins.schema.json`` and trigger a hot reload of
  the categories module so the next pipeline run picks them up.

* **Probe** — fetch one category_id live, used by the GUI's
  "confirm before pin" flow and by the compare-duplicates feature.

Network discipline (CLAUDE.md §6 / §1): all upstream calls are made
from the local FastAPI process — never from the browser. Single-flight
lock on sweep to keep us polite to ECI.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import jsonschema
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..sources.eci import categories as eci_categories
from ..sources.eci.events import EVENTS

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[3]
PINS_PATH = REPO_ROOT / "config" / "eci-pins.json"
PINS_SCHEMA_PATH = REPO_ROOT / "datasets" / "schemas" / "eci_pins.schema.json"
RECON_DIR = REPO_ROOT / "tools" / "eci_recon"
LAST_SWEEP_PATH = RECON_DIR / "categories.enumeration.json"

ECI_API = "https://www.eci.gov.in/eci-backend/public/api/election-result"

# Browser-style headers — see lessons.md (Akamai filter bypass recipe).
# `secret` is the public constant baked into the ECI JS bundle.
ECI_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "secret": "ECI@MAIN825",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.eci.gov.in/statistical-reports",
    "Origin": "https://www.eci.gov.in",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

# Single-flight: only one sweep at a time across the process.
_sweep_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _probe_one(client: httpx.Client, cid: int) -> dict[str, Any]:
    """One API call — returns a normalized hit/miss/error record."""
    try:
        r = client.get(ECI_API, params={"category_id": cid}, timeout=15.0)
    except httpx.RequestError as exc:
        return {"id": cid, "kind": "error", "error": exc.__class__.__name__}
    if r.status_code != 200:
        return {"id": cid, "kind": "error", "error": f"http {r.status_code}"}
    try:
        body = r.json()
    except ValueError:
        return {"id": cid, "kind": "error", "error": "non-json"}
    if not body.get("success") or not body.get("cat_name"):
        return {"id": cid, "kind": "miss"}
    return {
        "id": cid,
        "kind": "hit",
        "cat_name": body.get("cat_name"),
        "index_name": body.get("index_name") or "",
        "index_url": body.get("index_url") or "",
        "title_headline": body.get("title_headline") or "",
    }


def _load_schema() -> dict[str, Any]:
    return json.loads(PINS_SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_pins_payload() -> dict[str, Any]:
    if not PINS_PATH.is_file():
        return {
            "$schema": "https://yen-gov.github.io/schemas/eci_pins.schema.json",
            "$schema_version": "1.0",
            "sources": [],
            "pins": [],
        }
    return json.loads(PINS_PATH.read_text(encoding="utf-8"))


def _save_pins_payload(payload: dict[str, Any]) -> None:
    schema = _load_schema()
    try:
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as exc:
        raise HTTPException(400, f"schema validation failed: {exc.message}") from exc
    # Atomic-ish write.
    tmp = PINS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(PINS_PATH)
    eci_categories.reload()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/eci/recon/last-sweep")
def last_sweep() -> dict[str, Any]:
    """Return the most recent sweep result on disk (or ``null`` placeholder)."""
    if not LAST_SWEEP_PATH.is_file():
        return {"available": False}
    try:
        payload = json.loads(LAST_SWEEP_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(500, f"cannot read sweep file: {exc}") from exc
    return {"available": True, **payload}


class SweepBody(BaseModel):
    start: int = Field(1, ge=1, le=1000)
    end: int = Field(50, ge=1, le=1000)
    sleep_ms: int = Field(300, ge=0, le=5000,
                          description="Delay between requests; be polite.")


@router.post("/eci/recon/sweep")
def sweep(body: SweepBody) -> dict[str, Any]:
    """Sweep ``[start, end]`` against the ECI API and persist the result.

    Synchronous. Sweeps are small (default 50 ids × 0.3s = 15s) and the
    UI shows a spinner; running it as a background pipeline run would
    be overkill.
    """
    if body.end < body.start:
        raise HTTPException(400, "end < start")

    if not _sweep_lock.acquire(blocking=False):
        raise HTTPException(409, "another sweep is in flight")
    try:
        hits: list[dict[str, Any]] = []
        misses: list[int] = []
        errors: list[dict[str, Any]] = []
        with httpx.Client(headers=ECI_HEADERS) as client:
            for cid in range(body.start, body.end + 1):
                rec = _probe_one(client, cid)
                if rec["kind"] == "hit":
                    hits.append(rec)
                elif rec["kind"] == "miss":
                    misses.append(cid)
                else:
                    errors.append(rec)
                if body.sleep_ms:
                    time.sleep(body.sleep_ms / 1000.0)

        payload = {
            "ts": _now_iso(),
            "range": [body.start, body.end],
            "hits": hits,
            "misses": misses,
            "errors": errors,
        }
        RECON_DIR.mkdir(parents=True, exist_ok=True)
        LAST_SWEEP_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return payload
    finally:
        _sweep_lock.release()


@router.get("/eci/recon/probe/{category_id}")
def probe(category_id: int) -> dict[str, Any]:
    """Fetch one category_id live (used by the GUI's confirm-before-pin flow)."""
    if category_id < 1 or category_id > 100000:
        raise HTTPException(400, "category_id out of range")
    with httpx.Client(headers=ECI_HEADERS) as client:
        return _probe_one(client, category_id)


class CompareBody(BaseModel):
    a: int = Field(..., ge=1)
    b: int = Field(..., ge=1)


@router.post("/eci/recon/compare")
def compare(body: CompareBody) -> dict[str, Any]:
    """Probe two ids and return both records side-by-side.

    Use case: the May-2026 cohort appears twice in the catalogue (once
    as empty placeholders, once as real Statistical Reports); this lets
    the operator confirm which id is the canonical one before pinning.
    """
    with httpx.Client(headers=ECI_HEADERS) as client:
        ra = _probe_one(client, body.a)
        time.sleep(0.3)
        rb = _probe_one(client, body.b)
    return {"a": ra, "b": rb}


@router.get("/eci/pins")
def get_pins() -> dict[str, Any]:
    """Return the current pin set + a schema-id pointer for the UI."""
    payload = _load_pins_payload()
    return {
        "payload": payload,
        "path": "config/eci-pins.json",
        "schema_id": PINS_SCHEMA_PATH.name,
        "loaded_in_process": [
            {"state": s, "year": y, "category_id": cid}
            for (s, y), cid in sorted(eci_categories.STATISTICAL_REPORT_CATEGORY_ID.items())
        ],
        "events": [
            {
                "state": s,
                "year": y,
                "event_id": info.event_id,
                "has_partywise": info.has_partywise,
            }
            for (s, y), info in sorted(EVENTS.items())
        ],
    }


class PinEntry(BaseModel):
    state: str = Field(..., pattern=r"^[SU][0-9]{2}$")
    year: int = Field(..., ge=2024, le=2099)
    category_id: int = Field(..., ge=1)
    cat_name: str = Field(..., min_length=1)
    confirmed_at: str | None = Field(
        None,
        description="ISO timestamp; defaults to now if omitted.",
    )
    notes: str | None = None


class UpsertPinBody(PinEntry):
    confirm: bool = Field(False, description="Must be true; speed-bump.")


@router.post("/eci/pins", status_code=200)
def upsert_pin(body: UpsertPinBody) -> dict[str, Any]:
    """Add or replace a single pin keyed by (state, year)."""
    if not body.confirm:
        raise HTTPException(400, "confirm must be true")

    payload = _load_pins_payload()
    pins: list[dict[str, Any]] = list(payload.get("pins", []))

    new_entry: dict[str, Any] = {
        "state": body.state,
        "year": body.year,
        "category_id": body.category_id,
        "cat_name": body.cat_name,
        "confirmed_at": body.confirmed_at or _now_iso(),
    }
    if body.notes:
        new_entry["notes"] = body.notes

    replaced = False
    for i, existing in enumerate(pins):
        if existing.get("state") == body.state and existing.get("year") == body.year:
            pins[i] = new_entry
            replaced = True
            break
    if not replaced:
        pins.append(new_entry)

    payload["pins"] = pins
    _save_pins_payload(payload)
    return {"replaced": replaced, "entry": new_entry, "total_pins": len(pins)}


class DeletePinBody(BaseModel):
    state: str = Field(..., pattern=r"^[SU][0-9]{2}$")
    year: int = Field(..., ge=2024, le=2099)
    confirm: bool = Field(False)


@router.post("/eci/pins/delete")
def delete_pin(body: DeletePinBody) -> dict[str, Any]:
    """Remove the pin for (state, year). 404 if not present."""
    if not body.confirm:
        raise HTTPException(400, "confirm must be true")
    payload = _load_pins_payload()
    pins: list[dict[str, Any]] = list(payload.get("pins", []))
    keep = [p for p in pins
            if not (p.get("state") == body.state and p.get("year") == body.year)]
    if len(keep) == len(pins):
        raise HTTPException(404, f"no pin for ({body.state!r}, {body.year})")
    payload["pins"] = keep
    _save_pins_payload(payload)
    return {"removed": True, "total_pins": len(keep)}
