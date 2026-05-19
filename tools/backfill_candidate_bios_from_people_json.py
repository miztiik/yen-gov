"""One-shot backfill: lift biographic fields from people JSON sidecars into
``datasets/elections/dim_candidates.parquet``.

Reads every ``datasets/people/<event>/<ac_eci_no>/<slug>.json`` artifact,
joins by ``(election_id == period_label, state + ac_eci_no -> ac_id,
slugify(name) == candidate_slug)`` against the existing dim_candidates
rows, and UPSERTs each matched row through the canonical writer's
``_upsert_dim`` path with the v1.2 bio columns populated (sex, age,
education, profession, constituency_type, party_type).

Idempotent: re-running with no JSON changes yields a byte-identical
parquet (the writer dedupes by PK and emits sorted output).

Run once after the schema v1.1 -> v1.2 commit lands; PR-S.2 will then
refactor ``backend/yen_gov/pipeline/people_ingest.py`` to write directly
into dim_candidates and delete the JSON sidecars. This tool stays in the
repo as the audit trail of the one-time lift.

Invocation (repo root):

    python tools/backfill_candidate_bios_from_people_json.py

Exits 0 on success, 2 on missing inputs (no-op recoverable), 1 on
validation failure of any matched row.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import duckdb

from yen_gov.canonical.envelope import CandidateDimRow
from yen_gov.canonical.writer import _DIM_SPECS, _regenerate_manifest, _upsert_dim


REPO_ROOT = Path(__file__).resolve().parent.parent
PEOPLE_DIR = REPO_ROOT / "datasets" / "people"
DATASETS_DIR = REPO_ROOT / "datasets"
DIM_PARQUET = DATASETS_DIR / "elections" / "dim_candidates.parquet"

# Mirror backend/yen_gov/sources/eci/people_panel.slugify(). Kept inline so
# this tool does not pull in any adapter wiring; the function is 4 lines.
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    folded = folded.lower()
    folded = _SLUG_RE.sub("-", folded)
    folded = folded.strip("-")
    return folded


# ac_id format: "IN-S22-AC-2008-167" -> state="S22", ac_eci_no=167
_AC_ID_RE = re.compile(r"^IN-([SU]\d{2})-AC-\d+-(\d+)$")


def _load_bio_lookup() -> dict[tuple[str, str, int, str], dict]:
    """(election_id, state, ac_eci_no, candidate_slug) -> {sex, age, ...}."""
    lookup: dict[tuple[str, str, int, str], dict] = {}
    n_files = 0
    for json_path in sorted(PEOPLE_DIR.rglob("*.json")):
        try:
            p = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 — diagnostic only
            print(f"WARN: skip {json_path.as_posix()} -- {exc}", file=sys.stderr)
            continue
        n_files += 1
        try:
            key = (
                p["election_id"],
                p["state"],
                int(p["ac_code"]),
                p["candidate_slug"],
            )
        except KeyError as exc:
            print(f"WARN: missing join key in {json_path.as_posix()} -- {exc}", file=sys.stderr)
            continue
        lookup[key] = {
            "sex": p.get("sex"),
            "age": p.get("age"),
            "education": p.get("education"),
            "profession": p.get("profession"),
            "constituency_type": p.get("constituency_type"),
            # party_type was NOT on the v1.0 people artifacts in the tree
            # we surveyed -- only the schema permitted it. Read defensively;
            # downstream dim_candidates.party_type stays NULL when absent.
            "party_type": p.get("party_type"),
        }
    print(f"Loaded {n_files} person sidecars; {len(lookup)} unique join keys.")
    return lookup


def main() -> int:
    if not DIM_PARQUET.is_file():
        print(
            f"ERROR: {DIM_PARQUET.relative_to(REPO_ROOT).as_posix()} missing -- "
            "re-run canonical ingest first.",
            file=sys.stderr,
        )
        return 2
    if not PEOPLE_DIR.is_dir():
        print(f"INFO: {PEOPLE_DIR.relative_to(REPO_ROOT).as_posix()} absent -- nothing to backfill.")
        return 0

    bio_lookup = _load_bio_lookup()
    if not bio_lookup:
        print("INFO: no bio sidecars found; nothing to do.")
        return 0

    # Load existing dim_candidates rows. The on-disk parquet may be v1.1
    # (no bio columns) or v1.2; we project explicitly so a v1.1 file is
    # treated as bio=NULL for every row.
    con = duckdb.connect(":memory:")
    dim_rel = con.execute(
        f"SELECT * FROM read_parquet('{DIM_PARQUET.as_posix()}') ORDER BY candidate_id"
    )
    cols = [d[0] for d in dim_rel.description]
    dim_rows = [dict(zip(cols, row)) for row in dim_rel.fetchall()]
    print(f"Loaded {len(dim_rows)} existing dim_candidates rows.")

    BIO_COLS = ("sex", "age", "education", "profession", "constituency_type", "party_type")
    matched_rows: list[dict] = []
    used_keys: set[tuple[str, str, int, str]] = set()
    skipped_no_ac_match = 0
    skipped_no_name = 0

    for r in dim_rows:
        m = _AC_ID_RE.match(r["ac_id"])
        if not m:
            skipped_no_ac_match += 1
            continue
        state, ac_eci_no = m.group(1), int(m.group(2))
        if not r["name"]:
            skipped_no_name += 1
            continue
        slug = slugify(r["name"])
        key = (r["period_label"], state, ac_eci_no, slug)
        bio = bio_lookup.get(key)
        if bio is None:
            continue
        used_keys.add(key)
        # Build the full v1.2 payload: carry existing v1.0 / v1.1 fields
        # forward, then layer the bio fields on top. Pydantic validates
        # enums + age bounds, surfacing any drift between the v1.0 people
        # schema and the v1.2 dim-candidates schema as a hard failure.
        row_payload = {
            "candidate_id": r["candidate_id"],
            "ac_id": r["ac_id"],
            "period_label": r["period_label"],
            "ballot_serial": r["ballot_serial"],
            "name": r["name"],
            "party_id": r["party_id"],
            "rank": r["rank"],
            "source_id": r["source_id"],
            "party_short_raw": r.get("party_short_raw"),
            **{c: bio.get(c) for c in BIO_COLS},
        }
        # Validate (raises if any enum/range constraint trips).
        CandidateDimRow(**row_payload)
        matched_rows.append(row_payload)

    unmatched_keys = sorted(set(bio_lookup.keys()) - used_keys)
    print(
        f"Matched {len(matched_rows)} dim rows to bio sidecars. "
        f"{len(unmatched_keys)} sidecar keys have no dim row "
        f"(NOTA / pre-canonical-ingest events / name mismatches)."
    )
    print(f"  diagnostics: skipped_no_ac_match={skipped_no_ac_match}, skipped_no_name={skipped_no_name}")
    for k in unmatched_keys[:10]:
        print(f"  sample unmatched key: {k}")

    if not matched_rows:
        print("Nothing to write.")
        return 0

    # UPSERT via the canonical writer path. INSERT BY NAME on the existing
    # v1.1 parquet loads pre-existing rows with bio=NULL into the v1.2
    # in-memory table; our matched rows then overwrite their PKs with the
    # full v1.2 payload. The COPY emit is sorted by candidate_id.
    spec = _DIM_SPECS["candidate"]
    n_emit = _upsert_dim(
        out_path=DIM_PARQUET,
        rows=matched_rows,
        spec=spec,
        table_id="elections.dim_candidates",
    )
    print(f"Wrote {n_emit} dim_candidates rows to {DIM_PARQUET.relative_to(REPO_ROOT).as_posix()}.")

    # Manifest carries per-table schema_version + size_bytes + row_count;
    # the bump from 1.1 -> 1.2 is derived from the schema file's x-version,
    # the byte / row counts re-read from the freshly written parquet.
    mf = _regenerate_manifest(DATASETS_DIR)
    print(f"Regenerated manifest at {mf.relative_to(REPO_ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
