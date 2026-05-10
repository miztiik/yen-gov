"""ECI source reconnaissance.

Phase A of the ECI authority hierarchy (docs/architecture/backend/sources-eci.md#authority-hierarchy-for-past-elections):
probe ECI's reachable endpoints and produce a Markdown
inventory of what is available for a given (state, body, year) matrix.
Writes to notes/eci-recon-<date>.md (non-authoritative per CLAUDE.md §3).
Does NOT write to datasets/. No data ingestion happens here.

Usage:
    python tools/eci_recon/recon.py

The matrix and output path are module-level constants below; this is a
one-off recon script, not a configurable pipeline.

Endpoint map (verified 2026-05-09):
- 2024+ assembly elections: GET /eci-backend/public/api/election-result
  ?category_id=<small int per event>. Returns the file inventory (PDF + XLSX
  per section) with stable `https://www.eci.gov.in/eci-backend/public/all_files/
  election_report/...` URLs. The category_id is hardcoded per (state, year) in
  the React bundle's /statistical-reports hub table.
- <=2021 assembly elections: per-state landing page at
  https://old.eci.gov.in/files/file/<id>-<slug>/. The (state, year) -> URL map
  is also hardcoded in the same React table; the bundle IS the canonical
  inventory.
- ECI's `jl()` AES-ECB obfuscation (key "4WS8851W824R456Y") wraps category_ids
  on a small set of pre-2024 endpoints. Not needed for the canonical Phase A
  map because /statistical-reports already enumerates it cleartext; included
  here so future recon can probe deeper if needed.
"""

from __future__ import annotations

import base64
import datetime as _dt
import json
import re
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ECI's new-portal public API. The `secret` header value is embedded in the
# public JS bundle at https://www.eci.gov.in/static/js/main.<hash>.js as
# `bl="ECI@MAIN825"`. Refresh by re-greping the bundle if these probes start
# returning 401/403; not a credential, just a public constant.
NEW_PORTAL_API = "https://www.eci.gov.in/eci-backend/public"
NEW_PORTAL_SECRET = "ECI@MAIN825"
NEW_PORTAL_ROOT = "https://www.eci.gov.in/"

# AES-ECB key from the bundle (`rl="4WS8851W824R456Y"`). Used by `jl()` to
# obfuscate small id values on a handful of legacy endpoints. Public constant.
JL_KEY = b"4WS8851W824R456Y"

# Hosts where ECI's pre-2024 statistical reports live. Both have been observed
# unreachable from at least one dev environment (CONNECT timeout / actively
# refused). Recon records reachability per host so the inventory tells the
# truth about what we could and could not see.
LEGACY_HOSTS = [
    "https://old.eci.gov.in/",
    "https://eci.gov.in/",
]

# (ECI internal state code, year). 2026 is the in-scope active TN cycle.
# 2021/2016/2011 are the 3 prior cycles the authority hierarchy wants enriched
# (docs/architecture/backend/sources-eci.md).
MATRIX = [
    ("S22", 2026),
    ("S22", 2021), ("S22", 2016), ("S22", 2011),
    ("S11", 2021), ("S11", 2016), ("S11", 2011),
    ("S25", 2021), ("S25", 2016), ("S25", 2011),
]

# Display state names used in the React bundle's /statistical-reports table.
# Maps internal ECI code -> the exact label rendered in the hub table.
STATE_DISPLAY = {"S22": "Tamil Nadu", "S11": "Kerala", "S25": "West Bengal"}

# Verified category_ids from the React bundle for 2024+ AE events. Used to
# probe /api/election-result and confirm it returns the file inventory.
NEW_PORTAL_CATEGORIES = [("Tamil Nadu", 2026, 26)]

UA = "Mozilla/5.0 (compatible; yen-gov-recon/0.1; +https://github.com/miztiik/yen-gov)"


def jl(value: str | int) -> str:
    """ECI's `jl()` obfuscation: AES-ECB(PKCS7)-base64-urlencode of a string.
    Public constants from the bundle; not a credential."""
    enc = AES.new(JL_KEY, AES.MODE_ECB).encrypt(pad(str(value).encode(), 16))
    return urllib.parse.quote(base64.b64encode(enc).decode(), safe="")


@dataclass
class Probe:
    label: str
    url: str
    status: int | None = None
    bytes_seen: int = 0
    content_type: str = ""
    error: str = ""
    payload_summary: str = ""


@dataclass
class StateYearFinding:
    state: str
    year: int
    notification: dict | None = None
    hub_url: str = ""           # URL listed in /statistical-reports for this (state, year)
    hub_kind: str = ""          # "new-portal" | "old-portal" | "missing"
    inventory_files: int = 0    # # of (PDF, XLSX) entries the new-portal endpoint returned
    inventory_sample: str = ""


@dataclass
class Inventory:
    started_at: str
    state_code_map: dict = field(default_factory=dict)  # year -> {S22: "Tamil Nadu", ...}
    publications: list[dict] = field(default_factory=list)  # filtered hits
    hub_table: dict = field(default_factory=dict)       # state -> [(year, url), ...]
    legacy_host_probes: list[Probe] = field(default_factory=list)
    matrix: list[StateYearFinding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": UA, "secret": NEW_PORTAL_SECRET},
        timeout=20.0,
        follow_redirects=True,
    )


def fetch_state_code_map(client: httpx.Client) -> dict:
    r = client.get(f"{NEW_PORTAL_API}/api/get-ac-election-state")
    return r.json().get("message", {}) if r.status_code == 200 else {}


def fetch_notification(client: httpx.Client, state: str, year: int) -> dict | None:
    """The notification endpoint only carries the active cycle; older years
    consistently return an empty `message: []`. We probe anyway so the
    inventory states the truth per (state, year)."""
    r = client.get(
        f"{NEW_PORTAL_API}/api/get-ac-election-details"
        f"?iYear={year}&st_code={state}&election_id=3"
    )
    if r.status_code != 200:
        return None
    msg = r.json().get("message", [])
    return msg[0] if msg else None


def fetch_publications(client: httpx.Client) -> list[dict]:
    """Walk the new-portal publications catalogue and the narrative-reports
    pagination, return any document whose title/description mentions a state
    we care about, 'statistical', or 'assembly election'."""
    keep = re.compile(
        r"statistical|tamil\s*nadu|kerala|west\s*bengal|assembly\s*election|legislative",
        re.IGNORECASE,
    )
    out: list[dict] = []
    seen_ids: set = set()

    r = client.get(f"{NEW_PORTAL_API}/api/eci-publication")
    try:
        results = r.json().get("results", [])
    except (ValueError, json.JSONDecodeError):
        results = []
    for p in results:
        if p.get("id") in seen_ids:
            continue
        seen_ids.add(p.get("id"))
        haystack = (p.get("document_title") or "") + " " + (p.get("document_description") or "")
        if keep.search(haystack):
            out.append(p)

    page = 1
    while page < 25:  # hard cap; the catalogue is small
        r = client.get(
            f"{NEW_PORTAL_API}/api/general-election-narative-reports-publication"
            f"?page={page}"
        )
        if r.status_code != 200:
            break
        try:
            results = r.json().get("results", {})
        except (ValueError, json.JSONDecodeError):
            break
        data = results.get("data", []) if isinstance(results, dict) else []
        if not data:
            break
        for p in data:
            if p.get("id") in seen_ids:
                continue
            seen_ids.add(p.get("id"))
            haystack = (p.get("document_title") or "") + " " + (p.get("document_description") or "")
            if keep.search(haystack):
                out.append(p)
        last = results.get("last_page") if isinstance(results, dict) else None
        if not last or page >= last:
            break
        page += 1

    return out


def extract_hub_table(client: httpx.Client) -> dict[str, list[tuple[str, str]]]:
    """Pull the React bundle and extract the /statistical-reports hub table:
    the canonical (state, year) -> URL map. The new portal serves 2024+ via
    `/statistical-report/ae/<year>/<category_id>` (handled by /api/election-
    result internally); pre-2024 cycles link directly to old.eci.gov.in
    permalinks. The bundle IS the canonical inventory — there is no JSON API
    that returns this table.

    The HTML/JS routes refuse the API `secret` header (403); Akamai also
    blocks /static/* for unfamiliar User-Agents (the recon UA, full Chrome
    UAs at burst rate). Bare `Mozilla/5.0` consistently works. Public asset;
    no credentials involved."""
    plain = {"User-Agent": "Mozilla/5.0"}
    r = httpx.get(NEW_PORTAL_ROOT, headers=plain, timeout=20.0, follow_redirects=True)
    bundle_match = re.search(r'/static/js/main\.[a-f0-9]+\.js', r.text)
    if not bundle_match:
        return {}
    bundle_url = NEW_PORTAL_ROOT.rstrip("/") + bundle_match.group(0)
    src = httpx.get(bundle_url, headers=plain, timeout=60.0).text

    # Each row is `("td",{children:"<state>"}), ... <year-cells>`.
    state_pat = re.compile(r'\("td",\{children:"([A-Z][A-Za-z &\-]+)"\}\),(.{0,3000}?)\}\)\]\}')
    rows: dict[str, list[tuple[str, str]]] = {}
    for m in state_pat.finditer(src):
        state = m.group(1).strip()
        if len(state) < 3:
            continue
        years = re.findall(r'href:"([^"]+)",[^}]*?children:"(\d{4})"', m.group(2))
        if years:
            rows.setdefault(state, []).extend((yr, url) for url, yr in years)
    return rows


def fetch_election_result(client: httpx.Client, category_id: int) -> dict | None:
    """The 2024+ statistical-report endpoint. Returns a list of sections, each
    with `pdf_zip_url` and `xlsx_url` pointing to stable
    `https://www.eci.gov.in/eci-backend/public/all_files/election_report/...`
    paths (NOT signed `/api/download?url=<blob>` URLs)."""
    r = client.get(f"{NEW_PORTAL_API}/api/election-result?category_id={category_id}")
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except (ValueError, json.JSONDecodeError):
        return None


def probe_legacy(client: httpx.Client, urls: list[str]) -> list[Probe]:
    """HEAD-probe the per-state old.eci.gov.in landing pages so the inventory
    documents whether this run could see them at all, rather than silently
    omitting URLs we couldn't visit."""
    probes: list[Probe] = []
    for url in urls:
        label = url.replace("https://", "")
        try:
            r = client.head(url, timeout=8.0)
            probes.append(Probe(
                label=label, url=url, status=r.status_code,
                bytes_seen=int(r.headers.get("content-length", 0) or 0),
                content_type=r.headers.get("content-type", ""),
            ))
        except Exception as exc:  # noqa: BLE001 — recon needs to record any failure mode
            probes.append(Probe(label=label, url=url, error=type(exc).__name__ + ": " + str(exc)[:120]))
    return probes


def render_markdown(inv: Inventory, out: Path) -> None:
    lines: list[str] = []
    lines.append(f"# ECI Recon — {inv.started_at[:10]}")
    lines.append("")
    lines.append(
        "Output of `tools/eci_recon/recon.py`. Non-authoritative per CLAUDE.md §3 — "
        "this file is a scratch inventory written to `notes/`, intended for human review "
        "before any data is ingested into `datasets/`."
    )
    lines.append("")
    lines.append(f"Started at: `{inv.started_at}` UTC.")
    lines.append("")

    lines.append("## 1. State-code mapping (new-portal API, internal codes)")
    lines.append("")
    if inv.state_code_map:
        years = sorted(inv.state_code_map.keys(), reverse=True)
        all_codes: dict = {}
        for y in years:
            for code, name in inv.state_code_map[y].items():
                all_codes.setdefault(code, name)
        lines.append("| ECI code | Name | Years with active cycle |")
        lines.append("| -------- | ---- | ----------------------- |")
        for code in sorted(all_codes):
            present = [y for y in years if code in inv.state_code_map[y]]
            lines.append(f"| `{code}` | {all_codes[code]} | {', '.join(present) or '—'} |")
    else:
        lines.append("_No mapping returned — `/api/get-ac-election-state` was unreachable or empty._")
    lines.append("")

    lines.append("## 2. (State × Year) matrix — canonical hub URLs")
    lines.append("")
    lines.append(
        "The new portal's `/statistical-reports` hub is a hardcoded React table; the "
        "(state, year) -> URL map is extracted directly from the JS bundle, not from "
        "any JSON API. 2024+ cycles route to `/statistical-report/ae/<year>/<category_id>` "
        "(backed by `/api/election-result?category_id=<id>`); 2021 and earlier link "
        "directly to `old.eci.gov.in/files/file/<id>-<slug>/` permalinks. Both URL "
        "shapes are stable and safe to persist in `sources[]`."
    )
    lines.append("")
    lines.append("| State | Year | Hub URL | Kind | Notification API | Inventory files |")
    lines.append("| ----- | ---- | ------- | ---- | ---------------- | --------------- |")
    for f in inv.matrix:
        notif = "yes" if f.notification else "—"
        files = str(f.inventory_files) if f.inventory_files else "—"
        url_cell = f"`{f.hub_url}`" if f.hub_url else "_(not in hub table)_"
        lines.append(f"| {f.state} | {f.year} | {url_cell} | {f.hub_kind or '—'} | {notif} | {files} |")
    lines.append("")
    for f in inv.matrix:
        if f.inventory_sample:
            lines.append(f"### Sample inventory — {f.state} {f.year}")
            lines.append("")
            lines.append("```")
            lines.append(f.inventory_sample)
            lines.append("```")
            lines.append("")

    lines.append("## 3. Bundle-extracted hub table (full per-state history, in scope)")
    lines.append("")
    lines.append(
        "Every (state, year) -> URL row the React bundle exposes for the three "
        "in-scope states. Use this as the source of truth when picking what to "
        "ingest in Phase B; never re-derive these URLs by guessing patterns."
    )
    lines.append("")
    for code, name in STATE_DISPLAY.items():
        rows = inv.hub_table.get(name, [])
        lines.append(f"### {name} (`{code}`)")
        lines.append("")
        if rows:
            lines.append("| Year | URL |")
            lines.append("| ---- | --- |")
            for yr, url in rows:
                lines.append(f"| {yr} | `{url}` |")
        else:
            lines.append("_(state not present in hub table — may be under a different label)_")
        lines.append("")

    lines.append("## 4. New-portal publications catalogue (filtered)")
    lines.append("")
    lines.append(
        "Documents in `/api/eci-publication` and `/api/general-election-narative-reports-publication` "
        "whose title/description mentions a state in scope, 'statistical', 'assembly election', "
        "or 'legislative'. Permalinks (`document_url`) are stable and safe to persist in `sources[]`. "
        "The catalogue is heavily Lok-Sabha-skewed — most per-state AE reports do NOT appear here; "
        "they live in the hub table (§3) instead."
    )
    lines.append("")
    if inv.publications:
        lines.append("| ID | Title | Permalink |")
        lines.append("| -- | ----- | --------- |")
        for p in inv.publications:
            title = (p.get("document_title") or "").replace("|", "\\|")[:80]
            url = p.get("document_url") or ""
            lines.append(f"| {p.get('id')} | {title} | {url} |")
    else:
        lines.append("_No matching documents._")
    lines.append("")

    lines.append("## 5. Legacy-host reachability (`old.eci.gov.in`)")
    lines.append("")
    lines.append(
        "HEAD probes against the per-state landing pages from the hub table. Recon "
        "records reachability so the inventory reflects whether this run could see "
        "them at all, not just whether the URL existed in theory."
    )
    lines.append("")
    lines.append("| URL | Status | Content-Type | Size | Error |")
    lines.append("| --- | ------ | ------------ | ---- | ----- |")
    for p in inv.legacy_host_probes:
        lines.append(
            f"| `{p.label}` | {p.status if p.status is not None else '—'} | "
            f"{p.content_type or '—'} | {p.bytes_seen or '—'} | {p.error or '—'} |"
        )
    lines.append("")

    lines.append("## 6. Notes")
    lines.append("")
    for n in inv.notes:
        lines.append(f"- {n}")
    lines.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    inv = Inventory(started_at=_dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"))
    with _client() as client:
        inv.state_code_map = fetch_state_code_map(client)
        inv.hub_table = extract_hub_table(client)

        # Build per-(state, year) findings from hub table + notification API +
        # /api/election-result inventory for 2024+ events.
        cat_lookup = {(s, y): cid for s, y, cid in NEW_PORTAL_CATEGORIES}
        for state, year in MATRIX:
            display = STATE_DISPLAY.get(state, state)
            f = StateYearFinding(state=state, year=year)
            for yr, url in inv.hub_table.get(display, []):
                if yr == str(year):
                    f.hub_url = url
                    f.hub_kind = "new-portal" if url.startswith("/statistical-report/") else "old-portal"
                    break
            if not f.hub_url:
                f.hub_kind = "missing"
            f.notification = fetch_notification(client, state, year)
            cid = cat_lookup.get((display, year))
            if cid is not None:
                inv_payload = fetch_election_result(client, cid)
                if inv_payload:
                    items = inv_payload.get("results") or inv_payload.get("data") or []
                    if isinstance(items, dict):
                        items = items.get("data", [])
                    if isinstance(items, list):
                        f.inventory_files = len(items)
                        sample_lines = []
                        for it in items[:3]:
                            title = (it.get("document_title") or it.get("title") or "")[:60]
                            xlsx = it.get("xlsx_url") or it.get("xlsx") or ""
                            sample_lines.append(f"{title}\n  xlsx: {xlsx}")
                        f.inventory_sample = "\n".join(sample_lines)
            inv.matrix.append(f)

        inv.publications = fetch_publications(client)

        # Probe every old-portal hub URL we found for the 3 in-scope states, plus
        # the bare hosts to capture connect failures honestly.
        urls_to_probe: list[str] = []
        for code, name in STATE_DISPLAY.items():
            for _yr, url in inv.hub_table.get(name, []):
                if url.startswith("https://old.eci.gov.in/"):
                    urls_to_probe.append(url)
        urls_to_probe.extend(LEGACY_HOSTS)
        # de-dup, preserve order
        seen: set[str] = set()
        ordered: list[str] = []
        for u in urls_to_probe:
            if u not in seen:
                seen.add(u)
                ordered.append(u)
        inv.legacy_host_probes = probe_legacy(client, ordered)

    if all(p.status is None or p.status >= 500 for p in inv.legacy_host_probes):
        inv.notes.append(
            "Legacy ECI hosts (`old.eci.gov.in`, `eci.gov.in`) were UNREACHABLE from this run. "
            "Pre-2024 statistical reports for 2021/2016/2011 cannot be HEAD-validated until "
            "this run is repeated from a network that can reach those hosts (e.g. GitHub "
            "Actions, an India-region VM). The hub-table URLs in §3 are still authoritative — "
            "they were extracted from the React bundle directly."
        )
    inv.notes.append(
        "Endpoint split: `/api/election-result?category_id=<int>` serves 2024+ events with a "
        "stable file inventory; pre-2024 cycles are linked from the hub table directly to "
        "`old.eci.gov.in/files/file/<id>-<slug>/` permalinks. There is no single JSON API "
        "that returns the (state, year) -> URL map — the React bundle is the source of truth."
    )
    inv.notes.append(
        "docs/architecture/backend/sources-eci.md mandates persisting landing-page permalinks in `sources[]`, never the "
        "time-limited `/eci-backend/public/api/download?url=<blob>` signed URLs that the "
        "hub-page download buttons resolve to client-side. Recon never records the latter."
    )
    inv.notes.append(
        "ECI's `jl()` (AES-ECB, key `4WS8851W824R456Y`) is implemented but unused on the "
        "Phase A canonical path: the hub table gives every URL we need without it. Kept "
        "available in `recon.py` for future deeper probing of the few endpoints that still "
        "require it (`/api/get-statistical?categories=jl(<id>)`, `/api/get-sub-category`)."
    )

    out = Path(__file__).resolve().parents[2] / "notes" / f"eci-recon-{inv.started_at[:10]}.md"
    render_markdown(inv, out)
    print(f"wrote {out}")
    print(f"matrix: {len(inv.matrix)} probes; hub-table states: {len(inv.hub_table)}; "
          f"publications hits: {len(inv.publications)}; legacy probes: {len(inv.legacy_host_probes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
