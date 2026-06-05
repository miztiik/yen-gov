"""F1.1 Path A backfill - mash legacy parquet + TCPD raw + LGD-spine extension.

One-shot tool. Bring per-(state, year) ``candidacies.csv`` + ``summary.csv``
back into byte-exact parity with
``backend/tests/fixtures/canonical_winners_2026_05_19.json`` after B2b.5.x
reingest dropped 271 ACs across 28 slices due to LGD-spine gaps in
``datasets/data/entities/electoral.csv``.

Strategy (per F1.1 sub-plan, user verdict Path A, 2026-06-06):

1. Read fixture; identify ``(state_slug, eci_no)`` tuples needed.
2. Read ``electoral.csv``; find ``(state, eci_no)`` missing.
3. Read ``dim_acs.parquet`` for the missing AC names.
4. Synthesise gap-fill ``electoral.csv`` rows (``IN-AC-2008-{slug}-eci{N}``).
5. Write the extended ``electoral.csv`` (sorted by ``entity_id``).
6. Re-run ``assembly_results.emit_state_assembly()`` for every state the
   fixture references. The existing emitter now picks up the previously
   unbindable ACs (because the FK lookup succeeds).
7. Diff each fixture slice against the new ``candidacies.csv``; emit a
   ``.reconcile.log`` per ``(state, year)``; surface fixture entries that
   are stale vs TCPD raw (per user's "prefer TCPD" rule) so the operator
   updates them in the SAME PR.
8. Print the final residue (Phase 3 STOP if any AC remains unbindable
   because no upstream source carries it).

Run from repo root:

    python -m tools.elections.backfill_from_legacy

Holy Law #7: no mocks. Uses the real on-disk parquet, the real on-disk
``All_States_AE.csv`` (TCPD raw, gitignored under ``datasets/ephemeral/``),
and the real ``electoral.csv``.

Provenance: gap-fill ``electoral.csv`` rows reuse the same LGD-snapshot
``source_id`` as the existing spine. Re-emitted candidacies + summary rows
carry the existing TCPD AE-compilation ``source_id`` (per ADR-0042).
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Repo root resolution (this file lives at tools/elections/backfill_from_legacy.py).
REPO_ROOT = Path(__file__).resolve().parents[2]

# Make the backend package importable so we can reuse emit_state_assembly().
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from yen_gov.canonical.csv_validator import validate_csv  # noqa: E402
from yen_gov.canonical.reingest import assembly_results  # noqa: E402
from yen_gov.canonical.reingest.elections import (  # noqa: E402
    ASSEMBLY_CANDIDACIES_FC,
    ASSEMBLY_SUMMARY_FC,
)

# Paths.
FIXTURE = REPO_ROOT / "backend" / "tests" / "fixtures" / "canonical_winners_2026_05_19.json"
ELECTORAL_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "electoral.csv"
SOURCE_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "source.csv"
TCPD_AE_CSV = REPO_ROOT / "datasets" / "ephemeral" / "All_States_AE.csv"
DIM_ACS_PARQUET = REPO_ROOT / "datasets" / "elections" / "dim_acs.parquet"
ELECTIONS_ASSEMBLY_ROOT = REPO_ROOT / "datasets" / "elections" / "assembly"

# Closed-set ECI legacy per-state code -> LGD state slug. Mirrors the map
# inlined in backend/tests/test_canonical_parity_oracle.py (which Phase 4 of
# this PR drops). Keys = every state_code present in the 41-slice fixture.
ECI_TO_SLUG: dict[str, str] = {
    "S01": "andhra-pradesh",
    "S03": "assam",
    "S04": "bihar",
    "S05": "goa",
    "S06": "gujarat",
    "S07": "haryana",
    "S08": "himachal-pradesh",
    "S10": "karnataka",
    "S11": "kerala",
    "S14": "manipur",
    "S15": "meghalaya",
    "S17": "nagaland",
    "S19": "punjab",
    "S20": "rajasthan",
    "S22": "tamil-nadu",
    "S23": "tripura",
    "S24": "uttar-pradesh",
    "S25": "west-bengal",
    "S27": "jharkhand",
    "S28": "uttarakhand",
    "U05": "delhi",
    "U07": "puducherry",
}
SLUG_TO_ECI: dict[str, str] = {v: k for k, v in ECI_TO_SLUG.items()}

# TCPD State_Name conventions differ for "Jammu_&_Kashmir" / "Goa_Daman_&_Diu"
# etc. The mechanical inverse of _run_assembly_fanout._slugify works for every
# state in the fixture (verified by code-inspecting the fanout WAVES list).
def slug_to_tcpd_name(slug: str) -> str:
    return slug.replace("-and-", "_&_").replace("-", " ").title().replace(" ", "_")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """Write CSV deterministically: LF line endings, no trailing newline on last row."""
    import io

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    path.write_text(buf.getvalue(), encoding="utf-8", newline="")


def _tcpd_ae_source_id(source_csv: Path) -> str:
    """Find the TCPD AE-compilation source_id in source.csv.

    The B2b.5.2/5.3 reingest stamps one source row per the TCPD AE compilation
    (one-citation-per-snapshot per ADR-0042). We resolve it by title prefix.
    """
    rows = _read_csv_rows(source_csv)
    matches = [
        r
        for r in rows
        if "Indian Assembly Elections" in (r.get("title") or "")
        and "TCPD" in (r.get("title") or "")
    ]
    if not matches:
        raise RuntimeError(
            "No TCPD AE-compilation row in source.csv. Run "
            "`python -m yen_gov.canonical.reingest._run_assembly_results` first."
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple TCPD AE-compilation rows in source.csv: {[r['source_id'] for r in matches]}"
        )
    return matches[0]["source_id"]


def _phase1_diagnose(
    fixture_slices: dict[str, dict[str, dict]],
    electoral_rows: list[dict[str, str]],
) -> tuple[set[tuple[str, int]], dict[tuple[str, str], list[int]]]:
    """Identify ``(state_slug, eci_no)`` tuples the fixture needs but
    electoral.csv lacks; also build per-slice missing-AC inventory.

    Returns:
        missing: set of ``(state_slug, eci_no)`` to gap-fill
        per_slice_missing: ``{(event_id, state_code): [missing_eci_nos]}``
    """
    needed: set[tuple[str, int]] = set()
    per_slice_needed: dict[tuple[str, str], set[int]] = defaultdict(set)
    for key, winners in fixture_slices.items():
        event_id, state_code = key.split("/", 1)
        slug = ECI_TO_SLUG.get(state_code)
        if slug is None:
            continue
        for ac_str in winners.keys():
            eci_no = int(ac_str)
            needed.add((slug, eci_no))
            per_slice_needed[(event_id, state_code)].add(eci_no)

    present: set[tuple[str, int]] = set()
    for r in electoral_rows:
        if r.get("entity_kind") != "ac":
            continue
        raw = (r.get("eci_no") or "").strip()
        if not raw:
            continue
        present.add((r["state"], int(raw)))

    missing = needed - present
    per_slice_missing = {
        slice_key: sorted(ecis - present_in_state(present, ECI_TO_SLUG[slice_key[1]]))
        for slice_key, ecis in per_slice_needed.items()
    }
    return missing, per_slice_missing


def present_in_state(present: set[tuple[str, int]], slug: str) -> set[int]:
    return {eci for s, eci in present if s == slug}


def _lookup_ac_names(missing: set[tuple[str, int]]) -> dict[tuple[str, int], str | None]:
    """Lift AC names for missing (state_slug, eci_no) from dim_acs.parquet."""
    import duckdb

    con = duckdb.connect()
    rows = con.execute(
        """
        SELECT state_code, eci_no, name
        FROM read_parquet(?)
        WHERE delim_year = 2008
        """,
        [str(DIM_ACS_PARQUET)],
    ).fetchall()
    by_key: dict[tuple[str, int], str] = {
        (state_code, eci_no): name for state_code, eci_no, name in rows
    }
    out: dict[tuple[str, int], str | None] = {}
    for slug, eci_no in missing:
        state_code = SLUG_TO_ECI[slug]
        out[(slug, eci_no)] = by_key.get((state_code, eci_no))
    return out


def _synthesise_gap_fills(
    missing: set[tuple[str, int]],
    ac_names: dict[tuple[str, int], str | None],
    existing_entity_ids: set[str],
) -> tuple[list[dict[str, str]], list[tuple[str, int]]]:
    """Build gap-fill electoral.csv rows for resolvable missing ACs.

    Returns:
        rows: gap-fill rows ready to merge into electoral.csv
        unresolvable: missing tuples for which no source has a name
            (Phase 3 residue)
    """
    rows: list[dict[str, str]] = []
    unresolvable: list[tuple[str, int]] = []
    for slug, eci_no in sorted(missing):
        name = ac_names.get((slug, eci_no))
        if name is None:
            unresolvable.append((slug, eci_no))
            continue
        entity_id = f"IN-AC-2008-{slug}-eci{eci_no}"
        # Defensive: if this synthetic id somehow collides with an existing
        # entity, skip (operator must rename).
        if entity_id in existing_entity_ids:
            unresolvable.append((slug, eci_no))
            continue
        rows.append(
            {
                "entity_id": entity_id,
                "name": name,
                "entity_kind": "ac",
                "delim_year": "2008",
                "state": slug,
                "parent": "",  # nullable; LGD spine has no parent PC for these
                "eci_no": str(eci_no),
                "aliases": "",
                "reservation": "",  # nullable; left empty for synthetic fills
            }
        )
    return rows, unresolvable


def _extend_electoral_csv(gap_fill_rows: list[dict[str, str]]) -> int:
    """Append gap-fill rows + write electoral.csv deterministically.

    Returns the count of new rows actually added (skipping duplicates).
    """
    existing = _read_csv_rows(ELECTORAL_CSV)
    fieldnames = list(existing[0].keys())
    existing_ids = {r["entity_id"] for r in existing}
    new_rows = [r for r in gap_fill_rows if r["entity_id"] not in existing_ids]
    merged = existing + new_rows
    # Sort by entity_id (the PK) per parent plan section 22.4 invariant 5
    # which the csv_validator enforces: every CSV is sorted ascending by PK
    # on first write so byte-identical re-emits land deterministically.
    merged.sort(key=lambda r: r["entity_id"])
    _write_csv_rows(ELECTORAL_CSV, fieldnames, merged)
    return len(new_rows)


def _reemit_state(
    state_slug: str, source_id: str
) -> dict[int, dict[str, Any]]:
    """Re-run the existing emit_state_assembly per state."""
    tcpd_name = slug_to_tcpd_name(state_slug)
    return assembly_results.emit_state_assembly(
        ae_csv=TCPD_AE_CSV,
        electoral_csv=ELECTORAL_CSV,
        out_root=REPO_ROOT,
        state_name_tcpd=tcpd_name,
        state_slug=state_slug,
        source_id=source_id,
    )


def _slice_winners_from_csv(
    state_slug: str, election_year: int
) -> dict[int, dict[str, Any]]:
    """Read the on-disk candidacies.csv for (state, year) + project per-AC winners.

    Returns: ``{eci_no: {"name": str, "votes": int, "party_id": str | None}}``
    """
    path = (
        ELECTIONS_ASSEMBLY_ROOT
        / f"state={state_slug}"
        / f"election={election_year}"
        / "candidacies.csv"
    )
    if not path.exists():
        return {}
    out: dict[int, dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                eci_no = int(row["constituency_no"])
                votes = int(row["votes"])
            except (KeyError, ValueError):
                continue
            existing = out.get(eci_no)
            # Tie-break: max votes, then name ASC (matches oracle's
            # ROW_NUMBER ORDER BY votes DESC, name ASC).
            if (
                existing is None
                or votes > existing["votes"]
                or (votes == existing["votes"] and row["candidate_name"] < existing["name"])
            ):
                out[eci_no] = {
                    "name": row["candidate_name"],
                    "votes": votes,
                    "party_id": row.get("party_id") or None,
                }
    return out


def _tcpd_winner_party_short_all() -> dict[tuple[str, int, int], str]:
    """Read TCPD raw ONCE and project per-(state_slug, year, eci_no) winning Party.

    Bulk query so Phase 4 doesn't pay the 113MB scan 35x. Returns
    ``{(state_slug, year, eci_no): party_short}`` for DelimID=4 across
    every fixture state slug.

    The fixture keeps ``party_short``; the test does NOT compare it (see
    oracle docstring) but we lift it so the fixture entry stays
    semantically aligned with TCPD source.
    """
    import duckdb

    # TCPD-name -> slug for the fixture states (one query gets them all).
    tcpd_to_slug = {
        slug.replace("-and-", "_&_").replace("-", " ").title().replace(" ", "_"): slug
        for slug in set(ECI_TO_SLUG.values())
    }
    tcpd_names = sorted(tcpd_to_slug.keys())

    con = duckdb.connect()
    rows = con.execute(
        f"""
        WITH ranked AS (
            SELECT
                State_Name,
                Year,
                Constituency_No AS eci_no,
                Party AS party_short,
                Votes,
                Candidate,
                ROW_NUMBER() OVER (
                    PARTITION BY State_Name, Year, Constituency_No
                    ORDER BY Votes DESC, Candidate ASC
                ) AS rn
            FROM read_csv(?, ignore_errors=false)
            WHERE State_Name IN ({", ".join(f"'{n}'" for n in tcpd_names)})
              AND DelimID = '4'
              AND (Party IS NULL OR Party != 'NOTA')
        )
        SELECT State_Name, Year, eci_no, party_short
        FROM ranked
        WHERE rn = 1
        """,
        [str(TCPD_AE_CSV)],
    ).fetchall()
    out: dict[tuple[str, int, int], str] = {}
    for state_name, year, eci, party in rows:
        slug = tcpd_to_slug.get(state_name)
        if slug is None or eci is None or year is None:
            continue
        out[(slug, int(year), int(eci))] = party or ""
    return out


def _tcpd_winner_party_short(
    state_slug: str, election_year: int
) -> dict[int, str]:
    """DEPRECATED single-slice fetch; superseded by the bulk-cache lift.

    Kept for the (unused) per-slice path. Phase 4 uses
    ``_tcpd_winner_party_short_all`` to avoid scanning the 113MB TCPD
    raw 35 times.
    """
    import duckdb

    tcpd_name = slug_to_tcpd_name(state_slug)
    con = duckdb.connect()
    rows = con.execute(
        """
        WITH ranked AS (
            SELECT
                Constituency_No AS eci_no,
                Party AS party_short,
                Votes AS votes,
                ROW_NUMBER() OVER (
                    PARTITION BY Constituency_No
                    ORDER BY Votes DESC, Candidate ASC
                ) AS rn
            FROM read_csv(?, ignore_errors=false)
            WHERE State_Name = ?
              AND Year = ?
              AND DelimID = '4'
              AND (Party IS NULL OR Party != 'NOTA')
        )
        SELECT eci_no, party_short
        FROM ranked
        WHERE rn = 1
        """,
        [str(TCPD_AE_CSV), tcpd_name, election_year],
    ).fetchall()
    return {int(eci): (party or "") for eci, party in rows if eci is not None}


def _rewrite_fixture(
    fixture: dict[str, Any],
    slice_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    """Re-anchor fixture entries on CSV-derived winners + re-key by slug.

    Behaviour:
      - For each slice with at least one CSV winner on disk, rebuild the
        slice's per-AC winner block from the CSV. Names + votes match
        TCPD-derived CSV byte-exact; party_short is lifted from TCPD raw
        (Party column) for the winning candidate.
      - The slice KEY shape changes from ``"<event_id>/<state_code>"`` to
        ``"<event_id>/<state_slug>"`` (per F1.1 Phase 4 of the sub-plan,
        eliminating the ECI st_code translation map dependency).
      - Slices for which the CSV is empty (the 6 Phase 3 residue slices:
        5 AcGenMay2026/* + 1 AcGenNov2023/S20) are re-keyed to slugs but
        their VALUE block is preserved verbatim (no CSV-derived winners
        to anchor on); the test continues to mark them KNOWN_ABSENT.

    Returns:
        A ``{"slices_updated": int, "values_changed": int, ...}`` receipt.
    """
    # Build a {(event_id, state_code, eci_no): csv_winner} index from
    # slice_reports for slices that ran successfully.
    csv_index: dict[tuple[str, str, int], dict[str, Any]] = {}
    print("  bulk-lifting winning party_short from TCPD raw (one scan)...")
    party_all = _tcpd_winner_party_short_all()
    print(f"  {len(party_all)} (slug, year, eci) -> party_short entries cached.")
    for r in slice_reports:
        slug = r["state_slug"]
        year = r["year"]
        state_code = SLUG_TO_ECI[slug]
        event_id = r["event_id"]
        csv_winners = _slice_winners_from_csv(slug, year)
        if not csv_winners:
            continue
        for eci, w in csv_winners.items():
            csv_index[(event_id, state_code, eci)] = {
                "name": w["name"],
                "votes": w["votes"],
                "party_short": party_all.get((slug, year, eci), ""),
            }

    new_slices: dict[str, dict[str, dict[str, Any]]] = {}
    n_slices_rewritten = 0
    n_values_changed = 0
    n_acs_added = 0
    n_acs_removed = 0
    n_slices_preserved_verbatim = 0
    for key, old_winners in fixture.get("slices", {}).items():
        event_id, state_code = key.split("/", 1)
        slug = ECI_TO_SLUG.get(state_code)
        if slug is None:
            # Unmapped state code; preserve as-is under its old key.
            new_slices[key] = old_winners
            continue
        new_key = f"{event_id}/{slug}"
        # Build the new winner block from the CSV index for this slice.
        slice_csv = {
            eci: w
            for (eid, sc, eci), w in csv_index.items()
            if eid == event_id and sc == state_code
        }
        if not slice_csv:
            # Phase 3 residue: keep the old values verbatim, only re-key.
            new_slices[new_key] = old_winners
            n_slices_preserved_verbatim += 1
            continue
        new_winners: dict[str, dict[str, Any]] = {}
        old_acs = set(int(k) for k in old_winners.keys())
        new_acs = set(slice_csv.keys())
        n_acs_added += len(new_acs - old_acs)
        n_acs_removed += len(old_acs - new_acs)
        for eci in sorted(new_acs):
            w = slice_csv[eci]
            new_entry = {
                "name": w["name"],
                "party_short": w["party_short"]
                or (old_winners.get(str(eci), {}).get("party_short", "")),
                "votes": int(w["votes"]),
            }
            old_entry = old_winners.get(str(eci))
            if (
                old_entry is None
                or old_entry.get("name") != new_entry["name"]
                or int(old_entry.get("votes", -1)) != new_entry["votes"]
                or old_entry.get("party_short") != new_entry["party_short"]
            ):
                n_values_changed += 1
            new_winners[str(eci)] = new_entry
        new_slices[new_key] = new_winners
        n_slices_rewritten += 1

    new_fixture = {
        "captured_at": fixture.get("captured_at"),
        "captured_from_commit": fixture.get("captured_from_commit"),
        "captured_from_n_sqlites": fixture.get("captured_from_n_sqlites"),
        "note": fixture.get("note"),
        # F1.1 Path A backfill: the fixture is re-anchored on TCPD raw
        # (datasets/ephemeral/All_States_AE.csv, vintage 2026-06-05) via
        # the existing assembly_results.emit_state_assembly emitter; the
        # slice keys are re-shaped from ECI legacy state_code ("S03") to
        # LGD state slug ("assam") so the test no longer needs the ECI
        # map. See TODO/20260605-f1-csv-loaders-and-oracle-rewrite-subplan.md
        # F1.1 Path A section for the receipt.
        "f1_1_path_a_rewrite": {
            "at": "2026-06-06",
            "tcpd_ae_vintage": "2026-06-05",
            "key_shape_before": "<event_id>/<eci_state_code>",
            "key_shape_after": "<event_id>/<lgd_state_slug>",
            "slices_rewritten_from_csv": n_slices_rewritten,
            "slices_preserved_verbatim_phase3_residue": n_slices_preserved_verbatim,
            "winner_entries_changed": n_values_changed,
            "winner_acs_added": n_acs_added,
            "winner_acs_removed": n_acs_removed,
        },
        "slices": dict(sorted(new_slices.items())),
    }
    FIXTURE.write_text(
        json.dumps(new_fixture, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"fixture: re-anchored {n_slices_rewritten} slices on CSV; "
        f"{n_slices_preserved_verbatim} slices preserved (Phase 3 residue); "
        f"{n_values_changed} winner entries changed; "
        f"{n_acs_added} winner ACs added, {n_acs_removed} removed"
    )
    return {
        "slices_rewritten": n_slices_rewritten,
        "slices_preserved": n_slices_preserved_verbatim,
        "values_changed": n_values_changed,
        "acs_added": n_acs_added,
        "acs_removed": n_acs_removed,
    }


def _diff_fixture_slice(
    state_slug: str,
    event_id: str,
    fixture_winners: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compare fixture slice to current candidacies.csv winners.

    Returns a per-slice report: missing ACs, present-but-diff ACs, matches.
    """
    import re

    m = re.search(r"(\d{4})$", event_id)
    if not m:
        return {"error": f"no year in event_id={event_id}"}
    year = int(m.group(1))

    csv_winners = _slice_winners_from_csv(state_slug, year)
    fx_acs = {int(k): v for k, v in fixture_winners.items()}

    missing_in_csv = sorted(set(fx_acs) - set(csv_winners))
    extra_in_csv = sorted(set(csv_winners) - set(fx_acs))
    both = set(fx_acs) & set(csv_winners)

    vote_diffs: list[dict[str, Any]] = []
    name_diffs: list[dict[str, Any]] = []
    for eci in sorted(both):
        fx_v = int(fx_acs[eci]["votes"])
        csv_v = int(csv_winners[eci]["votes"])
        if fx_v != csv_v:
            vote_diffs.append(
                {
                    "eci": eci,
                    "fixture_votes": fx_v,
                    "csv_votes": csv_v,
                    "fixture_name": fx_acs[eci]["name"],
                    "csv_name": csv_winners[eci]["name"],
                }
            )
        else:
            fx_n = fx_acs[eci]["name"].strip()
            csv_n = csv_winners[eci]["name"].strip()
            if fx_n != csv_n:
                name_diffs.append(
                    {
                        "eci": eci,
                        "fixture_name": fx_n,
                        "csv_name": csv_n,
                        "votes": csv_v,
                    }
                )

    return {
        "event_id": event_id,
        "state_slug": state_slug,
        "year": year,
        "csv_path": str(
            (
                ELECTIONS_ASSEMBLY_ROOT
                / f"state={state_slug}"
                / f"election={year}"
                / "candidacies.csv"
            ).relative_to(REPO_ROOT)
        ).replace("\\", "/"),
        "n_fixture_acs": len(fx_acs),
        "n_csv_acs": len(csv_winners),
        "missing_in_csv": missing_in_csv,
        "extra_in_csv": extra_in_csv,
        "vote_diffs": vote_diffs,
        "name_diffs": name_diffs,
    }


def _write_reconcile_log(slice_report: dict[str, Any]) -> Path:
    """Emit per-(state, year) .reconcile.log next to candidacies.csv."""
    year = slice_report["year"]
    slug = slice_report["state_slug"]
    log_path = (
        ELECTIONS_ASSEMBLY_ROOT
        / f"state={slug}"
        / f"election={year}"
        / "backfill.reconcile.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# F1.1 Path A backfill reconciliation log (2026-06-06)",
        f"#",
        f"# slice:     {slice_report['event_id']}/{SLUG_TO_ECI[slug]}",
        f"# csv_path:  {slice_report['csv_path']}",
        f"# fixture_acs: {slice_report['n_fixture_acs']}",
        f"# csv_acs:     {slice_report['n_csv_acs']}",
        f"#",
    ]
    if slice_report["missing_in_csv"]:
        lines.append(f"# {len(slice_report['missing_in_csv'])} ACs MISSING in CSV (unbindable; Phase 3 residue):")
        for eci in slice_report["missing_in_csv"]:
            lines.append(f"#   eci_no={eci}")
    else:
        lines.append(f"# 0 ACs missing in CSV; all fixture ACs bound.")
    lines.append("#")
    if slice_report["vote_diffs"]:
        lines.append(f"# {len(slice_report['vote_diffs'])} winner vote-count diffs (TCPD wins per user verdict; fixture would update):")
        for d in slice_report["vote_diffs"]:
            lines.append(
                f"#   eci_no={d['eci']}: fixture={d['fixture_name']} v={d['fixture_votes']} "
                f"!= csv={d['csv_name']} v={d['csv_votes']}"
            )
    else:
        lines.append(f"# 0 winner vote-count diffs vs fixture.")
    lines.append("#")
    if slice_report["name_diffs"]:
        lines.append(f"# {len(slice_report['name_diffs'])} winner-name diffs (votes match; name whitespace/spelling):")
        for d in slice_report["name_diffs"]:
            lines.append(
                f"#   eci_no={d['eci']}: fixture={d['fixture_name']!r} vs csv={d['csv_name']!r} (votes={d['votes']})"
            )
    if slice_report["extra_in_csv"]:
        lines.append(
            f"# {len(slice_report['extra_in_csv'])} ACs PRESENT in CSV but NOT in fixture (informational): {slice_report['extra_in_csv']}"
        )
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return log_path


def main() -> int:
    skip_reemit = "--skip-reemit" in sys.argv
    print(f"F1.1 Path A backfill - mash from parquet+TCPD+LGD-spine")
    print(f"repo:     {REPO_ROOT}")
    print(f"fixture:  {FIXTURE.relative_to(REPO_ROOT)}")
    print(f"electoral.csv: {ELECTORAL_CSV.relative_to(REPO_ROOT)}")
    print(f"TCPD AE:  {TCPD_AE_CSV.relative_to(REPO_ROOT)} ({'OK' if TCPD_AE_CSV.exists() else 'MISSING'})")
    if skip_reemit:
        print(f"--skip-reemit: Phase 2.3 (per-state emit) WILL BE SKIPPED (re-runs only).")
    print()

    if not TCPD_AE_CSV.exists():
        print(
            f"ERROR: TCPD raw {TCPD_AE_CSV.relative_to(REPO_ROOT)} is absent. "
            "This tool reads the upstream TCPD compilation; download it first."
        )
        return 2

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture_slices = fixture.get("slices", {})
    electoral_rows = _read_csv_rows(ELECTORAL_CSV)
    print(f"electoral.csv: {len(electoral_rows)} rows on disk")
    print(f"fixture:       {len(fixture_slices)} slices on disk")

    # === Phase 1: diagnose ===
    missing, per_slice_missing = _phase1_diagnose(fixture_slices, electoral_rows)
    print()
    print(f"=== Phase 1 diagnosis ===")
    print(f"missing (state_slug, eci_no) tuples: {len(missing)}")
    by_state = defaultdict(list)
    for slug, eci_no in missing:
        by_state[slug].append(eci_no)
    for slug in sorted(by_state):
        ecis = sorted(by_state[slug])
        print(
            f"  {slug:20s}: {len(ecis):4d} missing ACs "
            f"(eci_no range {ecis[0]}..{ecis[-1]})"
        )
    print()
    print(f"per-slice missing-AC breakdown (28 expected with non-empty residue pre-mash):")
    n_nonempty = 0
    for slice_key in sorted(per_slice_missing):
        ecis = per_slice_missing[slice_key]
        if not ecis:
            continue
        n_nonempty += 1
        event_id, state_code = slice_key
        slug = ECI_TO_SLUG[state_code]
        print(
            f"  {event_id}/{state_code} ({slug}): {len(ecis)} missing"
        )
    print(f"  total slices with missing ACs: {n_nonempty}")
    print()

    # === Phase 2.1: lookup AC names from dim_acs.parquet ===
    print(f"=== Phase 2.1: lifting AC names from dim_acs.parquet ===")
    ac_names = _lookup_ac_names(missing)
    n_resolved = sum(1 for v in ac_names.values() if v is not None)
    print(f"resolved {n_resolved} of {len(missing)} missing names via dim_acs.parquet")
    print()

    # === Phase 2.2: synthesise + extend electoral.csv ===
    print(f"=== Phase 2.2: extending electoral.csv with gap-fill rows ===")
    existing_entity_ids = {r["entity_id"] for r in electoral_rows}
    gap_fill_rows, unresolvable = _synthesise_gap_fills(
        missing, ac_names, existing_entity_ids
    )
    print(f"synthesised {len(gap_fill_rows)} gap-fill rows")
    if unresolvable:
        print(f"WARNING: {len(unresolvable)} (state_slug, eci_no) tuples are UNRESOLVABLE:")
        for slug, eci in unresolvable[:30]:
            print(f"  ({slug}, eci_no={eci})")
        if len(unresolvable) > 30:
            print(f"  ... and {len(unresolvable) - 30} more")
    added = _extend_electoral_csv(gap_fill_rows)
    print(f"electoral.csv: appended {added} new rows ({len(gap_fill_rows) - added} were duplicates)")
    print()

    # === Phase 2.3: re-emit per state ===
    src_id = _tcpd_ae_source_id(SOURCE_CSV)
    print(f"=== Phase 2.3: re-emit candidacies + summary per state ===")
    print(f"TCPD AE source_id: {src_id}")
    fixture_state_slugs = sorted({ECI_TO_SLUG[sc] for sc in {k.split("/")[1] for k in fixture_slices}})
    print(f"states to re-emit ({len(fixture_state_slugs)}): {fixture_state_slugs}")
    per_state_emit: dict[str, dict[int, dict[str, Any]]] = {}
    if skip_reemit:
        print("  SKIPPED per --skip-reemit (assuming a prior run already produced the CSVs).")
    else:
        for slug in fixture_state_slugs:
            try:
                result = _reemit_state(slug, src_id)
            except FileNotFoundError as e:
                print(f"  {slug}: ERROR - {e}")
                continue
            per_state_emit[slug] = result
            n_years = len(result)
            n_cand = sum(r["n_candidacies"] for r in result.values())
            n_summ = sum(r["n_summary"] for r in result.values())
            unbound_years = [
                (y, r["unbound_eci_nos"]) for y, r in result.items() if r["unbound_eci_nos"]
            ]
            unbound_summary = (
                f" (unbound: {unbound_years[:3]}{'...' if len(unbound_years) > 3 else ''})"
                if unbound_years
                else ""
            )
            print(
                f"  {slug:20s}: {n_years} years, {n_cand} candidacies, {n_summ} summary rows{unbound_summary}"
            )

    # Validate the emitted CSVs (skipped if re-emit skipped).
    if not skip_reemit:
        print()
        print(f"=== validating emitted candidacies + summary CSVs ===")
        n_validated = 0
        for slug, emitted in per_state_emit.items():
            for year, info in emitted.items():
                try:
                    validate_csv(
                        path=info["candidacies"],
                        file_class=ASSEMBLY_CANDIDACIES_FC,
                        repo_root=REPO_ROOT,
                    )
                    validate_csv(
                        path=info["summary"],
                        file_class=ASSEMBLY_SUMMARY_FC,
                        repo_root=REPO_ROOT,
                    )
                    n_validated += 2
                except Exception as e:
                    print(f"  VALIDATE FAIL {slug}/{year}: {e}")
                    return 3
        print(f"validated {n_validated} CSV files")
    print()

    # === Phase 3: diff per fixture slice ===
    print(f"=== Phase 3: per-slice fixture parity diff (post-mash) ===")
    slice_reports: list[dict[str, Any]] = []
    log_paths: list[Path] = []
    n_perfect = 0
    n_missing_acs = 0
    n_vote_diffs = 0
    n_name_diffs = 0
    for key, winners in sorted(fixture_slices.items()):
        event_id, state_code = key.split("/", 1)
        slug = ECI_TO_SLUG.get(state_code)
        if slug is None:
            print(f"  {key}: SKIPPED (unmapped state_code)")
            continue
        report = _diff_fixture_slice(slug, event_id, winners)
        slice_reports.append(report)
        log_path = _write_reconcile_log(report)
        log_paths.append(log_path)
        n_perfect_this = (
            not report["missing_in_csv"]
            and not report["vote_diffs"]
            and not report["name_diffs"]
        )
        n_perfect += 1 if n_perfect_this else 0
        n_missing_acs += len(report["missing_in_csv"])
        n_vote_diffs += len(report["vote_diffs"])
        n_name_diffs += len(report["name_diffs"])
        status = "OK" if n_perfect_this else "DIFF"
        print(
            f"  [{status}] {key} -> {report['csv_path']}: "
            f"missing={len(report['missing_in_csv'])}, "
            f"votes_diff={len(report['vote_diffs'])}, "
            f"name_diff={len(report['name_diffs'])}, "
            f"extra={len(report['extra_in_csv'])}"
        )

    print()
    print(f"=== summary ===")
    print(f"reconcile logs:      {len(log_paths)}")
    print(f"perfectly-aligned slices:  {n_perfect} of {len(slice_reports)}")
    print(f"residual missing ACs:      {n_missing_acs}")
    print(f"residual vote diffs:       {n_vote_diffs} (TCPD wins per user verdict; fixture updates surfaced)")
    print(f"residual name diffs:       {n_name_diffs} (votes match; whitespace/spelling)")

    # === Phase 4: rewrite fixture with TCPD-derived winners + re-key by slug ===
    print()
    print(f"=== Phase 4: rewrite fixture (re-anchor on TCPD-derived CSV + re-key by slug) ===")
    fixture_updates = _rewrite_fixture(fixture, slice_reports)

    # Emit a top-level summary so the PR body can cite the receipts.
    summary = {
        "fixture_total_slices": len(fixture_slices),
        "mappable_slices": len(slice_reports),
        "perfectly_aligned": n_perfect,
        "residual_missing_acs": n_missing_acs,
        "residual_vote_diffs": n_vote_diffs,
        "residual_name_diffs": n_name_diffs,
        "gap_fill_electoral_rows_added": added,
        "tcpd_ae_source_id": src_id,
        "phase4_fixture_rewrite": fixture_updates,
        "per_slice_reports": [
            {
                "event_id": r["event_id"],
                "state_code": SLUG_TO_ECI[r["state_slug"]],
                "state_slug": r["state_slug"],
                "year": r["year"],
                "n_fixture_acs": r["n_fixture_acs"],
                "n_csv_acs": r["n_csv_acs"],
                "n_missing_in_csv": len(r["missing_in_csv"]),
                "missing_in_csv": r["missing_in_csv"],
                "n_vote_diffs": len(r["vote_diffs"]),
                "vote_diffs_preview": r["vote_diffs"][:3],
                "n_name_diffs": len(r["name_diffs"]),
                "name_diffs_preview": r["name_diffs"][:3],
                "csv_path": r["csv_path"],
            }
            for r in slice_reports
        ],
    }
    summary_path = REPO_ROOT / "datasets" / "_ops" / "f1.1-backfill-summary-2026-06-06.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"summary receipt:    {summary_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
