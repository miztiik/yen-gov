"""Curator script: apply PR-W-2 ECI parity verdict.csv to parties.csv.

Reads ``datasets/ephemeral/party-parity/eci-registered/2024/<sha>/verdict.csv``
and applies the operator-curatable Q1-owned enrichments to
``datasets/data/entities/parties.csv``:

  - ``verdict == VERIFIED`` + ``action == enrich``:
      * Fill ``eci_codes`` if empty (ECI publication code).
      * Fill ``recognition_scope`` if empty (ECI enum).
      * Fill ``home_state_codes`` if empty (ECI pipe-list of IN-XX).
      * Append ECI short to ``aliases`` if not already present.
  - ``verdict == VERIFIED`` + ``action == match``: no-op (already aligned).
  - ``verdict == VERIFIED`` + ``action == alias-add``: add the ECI short
    to aliases (collision-skip if claimed by another canonical party).
  - ``verdict == VERIFIED`` + ``action == conflict``: NO mutation. Adds a
    ``curator_note`` to the verdict.csv naming the collision and a
    ``curator_source_id`` pointing at ECI's source.csv row.
  - ``verdict == UNVERIFIED`` + ``action == mint-new``: NO mutation. The
    deferred-mint list is dumped to stdout for hand-curation via
    ``hans_mints.py``.

Per CLAUDE.md section 10 (auto-correct BANNED on publisher disagreement)
+ Wave 0 / Hans verdict ("hand-curation is the only path"), this script
NEVER overwrites authored canonical cells. Real disagreements (e.g. ECI
says national, canonical says state — the 6 known 2024 flips) are
hand-applied via ``hans_mints.py`` with explicit per-row justification.

Per Q1 fact-class authority (plan section 0.3): ECI wins on
``eci_codes``, ``recognition_scope``, ``home_state_codes`` — but ONLY
via the fill-empty-only enrich leg here. Overwriting an authored
canonical cell with an ECI value happens in ``hans_mints.py`` for the
specific 2024 flips and Q7 mints.

Run from the repo root (dry-run by default; pass --apply to write):

    python -m tools.recon_curate_eci_registered \\
        --verdict datasets/ephemeral/party-parity/eci-registered/2024/<sha>/verdict.csv \\
        --apply

The verdict.csv path is written-back-in-place with curator_note +
curator_source_id columns populated for conflict rows; parties.csv is
read-modify-rewritten preserving original column order + LF line
terminators (matching the writer at writers under canonical/).
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter
from pathlib import Path

# Allow ``python -m tools.recon_curate_eci_registered`` from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.canonical.citation import derive_source_id  # noqa: E402
from yen_gov.canonical.recon.adapters.eci_registered import (  # noqa: E402
    DEFAULT_ECI_CSV,
    _read_eci_snapshot,
)

PARTIES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
SOURCE_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "source.csv"

#: PR-W-2's ECI registered-parties catalogue citation triple (per ADR-0032).
#: Carries vintage="2024" matching the operator snapshot window
#: (ADR-0042 publisher edition anchor).
ECI_REGISTERED_PRODUCER = "Election Commission of India"
ECI_REGISTERED_TITLE = (
    "List of Political Parties & Symbol main Notification "
    "(National, State, Unrecognised-Registered)"
)
ECI_REGISTERED_VINTAGE = "2024"
ECI_REGISTERED_URL = "https://www.eci.gov.in/political-parties/"


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """Write CSV with deterministic LF + matches canonical writer chain."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        full = {k: (row.get(k) or "") for k in fieldnames}
        writer.writerow(full)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _ensure_eci_source(*, apply: bool) -> str:
    """Find-or-add the ECI-registered-parties source.csv row; return source_id.

    Idempotent: if a row with the same (producer, title, vintage) triple
    already exists in source.csv, returns its source_id without
    modification. Otherwise appends a new row (only when --apply is
    passed; dry-run computes the id and returns it without writing).
    """
    source_id = derive_source_id(
        ECI_REGISTERED_PRODUCER, ECI_REGISTERED_TITLE, ECI_REGISTERED_VINTAGE
    )
    fieldnames, rows = _read_csv(SOURCE_CSV)
    existing = next((r for r in rows if r.get("source_id") == source_id), None)
    if existing is not None:
        return source_id
    if not apply:
        return source_id
    rows.append(
        {
            "source_id": source_id,
            "owner": ECI_REGISTERED_PRODUCER,
            "title": ECI_REGISTERED_TITLE,
            "vintage": ECI_REGISTERED_VINTAGE,
            "url": ECI_REGISTERED_URL,
        }
    )
    rows.sort(key=lambda r: r.get("source_id", ""))
    _write_csv(SOURCE_CSV, fieldnames, rows)
    return source_id


def _index_eci_by_short() -> dict[str, dict[str, str]]:
    """Re-read ECI snapshot and project to {short: {eci_code, scope, states, year}}.

    Lifted from the adapter's read so the curator can resolve verdict
    rows back to the original ECI snapshot row for enrichment payload.
    """
    eci_csv = REPO_ROOT / DEFAULT_ECI_CSV
    if not eci_csv.exists():
        raise FileNotFoundError(
            f"ECI snapshot CSV not found at {eci_csv.as_posix()!r}; "
            f"required by recon-curate (cited in adapter docstring)."
        )
    records = _read_eci_snapshot(eci_csv)
    out: dict[str, dict[str, str]] = {}
    for rec in records:
        if not rec.short:
            continue
        # Keyed by short (verdict.csv external_key carries the same).
        out[rec.short] = {
            "eci_code": rec.eci_code,
            "recognition_scope": rec.recognition_scope,
            "home_state_codes": rec.home_state_codes,
            "gained_year": rec.gained_year,
            "full": rec.full,
        }
    return out


def _apply_enrich(
    canonical_row: dict[str, str],
    eci_record: dict[str, str],
    claimed_aliases: dict[str, str],
    short_to_add: str,
) -> tuple[bool, list[str], list[str]]:
    """Apply VERIFIED+enrich payload to a canonical parties.csv row.

    Q1-owned fill-empty-only operation on:
      - eci_codes
      - recognition_scope
      - home_state_codes
    Plus alias-add of the ECI short (skip on alias collision).

    Returns ``(changed, change_log, skipped_collisions)``.

    Mutates ``canonical_row`` AND ``claimed_aliases`` in place.

    Fill-empty-only rule per CLAUDE.md section 10: never overwrites
    authored values. The 6 known 2024 flips (where ECI disagrees with
    a previously-authored canonical recognition_scope) go through
    ``hans_mints.py`` with explicit per-row justification.
    """
    log: list[str] = []
    skipped: list[str] = []
    pid = (canonical_row.get("party_id") or "").strip()
    # eci_codes
    if eci_record["eci_code"] and not (canonical_row.get("eci_codes") or "").strip():
        canonical_row["eci_codes"] = eci_record["eci_code"]
        log.append(f"eci_codes={eci_record['eci_code']}")
    # recognition_scope
    rec_scope = eci_record["recognition_scope"]
    if rec_scope and not (canonical_row.get("recognition_scope") or "").strip():
        canonical_row["recognition_scope"] = rec_scope
        log.append(f"recognition_scope={rec_scope}")
    # home_state_codes
    home = eci_record["home_state_codes"]
    if home and not (canonical_row.get("home_state_codes") or "").strip():
        canonical_row["home_state_codes"] = home
        log.append(f"home_state_codes={home}")
    # alias-add: ECI short.
    canonical_short = (canonical_row.get("short") or "").upper().strip()
    short_upper = (short_to_add or "").upper().strip()
    if short_upper and short_upper != canonical_short:
        aliases_raw = (canonical_row.get("aliases") or "").strip()
        current_aliases: set[str] = set()
        if aliases_raw:
            for a in aliases_raw.split("|"):
                v = a.strip().upper()
                if v:
                    current_aliases.add(v)
        if short_upper not in current_aliases:
            claimed_by = claimed_aliases.get(short_upper)
            if claimed_by is not None and claimed_by != pid:
                skipped.append(f"{short_upper}->{claimed_by}")
            else:
                existing_ordered = [a.strip() for a in aliases_raw.split("|") if a.strip()]
                canonical_row["aliases"] = "|".join(existing_ordered + [short_upper])
                claimed_aliases[short_upper] = pid
                log.append(f"aliases+=[{short_upper}]")
    return bool(log), log, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--verdict",
        type=Path,
        required=True,
        help="Path to the verdict.csv produced by `python -m yen_gov parity --source eci-registered`.",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to parties.csv + source.csv + verdict.csv. Default is dry-run.",
    )
    args = ap.parse_args()

    if not args.verdict.exists():
        print(f"verdict.csv not found: {args.verdict.as_posix()}", file=sys.stderr)
        return 2

    # Read verdict.csv + parties.csv + project ECI source-of-truth.
    verdict_fields, verdict_rows = _read_csv(args.verdict)
    parties_fields, parties_rows = _read_csv(PARTIES_CSV)
    parties_by_pid: dict[str, dict[str, str]] = {
        (r.get("party_id") or "").strip(): r for r in parties_rows if r.get("party_id")
    }
    eci_by_short = _index_eci_by_short()

    # Build the claimed-alias index across ALL canonical parties so
    # _apply_enrich can skip ECI shorts that would collide with another
    # party's short or aliases (the party_resolver loader fails-loud on
    # duplicate keys; this skip-policy keeps the parity idempotent
    # rather than crashing post-apply).
    claimed_aliases: dict[str, str] = {}
    for r in parties_rows:
        pid = (r.get("party_id") or "").strip()
        if not pid:
            continue
        short = (r.get("short") or "").upper().strip()
        if short:
            claimed_aliases[short] = pid
        for a in (r.get("aliases") or "").split("|"):
            v = a.strip().upper()
            if v:
                claimed_aliases[v] = pid

    # Idempotent: ensure source.csv carries the ECI-registered citation.
    eci_source_id = _ensure_eci_source(apply=args.apply)

    enriched = 0
    enrich_changes: Counter[str] = Counter()
    alias_collisions: list[tuple[str, str]] = []
    conflicts_marked = 0
    alias_added = 0
    skipped_no_canonical = 0
    skipped_no_eci = 0
    mint_new_deferred: list[str] = []

    for vrow in verdict_rows:
        verdict = (vrow.get("verdict") or "").strip()
        action = (vrow.get("action") or "").strip()
        proposed_pid = (vrow.get("proposed_party_id") or "").strip()
        external_key = (vrow.get("external_key") or "").strip()
        external_short = (vrow.get("external_short") or "").strip()

        if verdict == "VERIFIED" and action == "enrich":
            canonical_row = parties_by_pid.get(proposed_pid)
            eci_record = eci_by_short.get(external_key)
            if canonical_row is None:
                skipped_no_canonical += 1
                continue
            if eci_record is None:
                skipped_no_eci += 1
                continue
            changed, log, skipped = _apply_enrich(
                canonical_row, eci_record, claimed_aliases, external_short
            )
            if changed:
                enriched += 1
                for entry in log:
                    field = entry.split("=", 1)[0].split("+=", 1)[0]
                    enrich_changes[field] += 1
            for sk in skipped:
                alias_collisions.append((proposed_pid, sk))
        elif verdict == "VERIFIED" and action == "alias-add":
            canonical_row = parties_by_pid.get(proposed_pid)
            if canonical_row is None:
                skipped_no_canonical += 1
                continue
            # Same alias-add as the enrich leg; just no Q1-owned-field
            # writes since the adapter already determined those are equal.
            empty_eci = {"eci_code": "", "recognition_scope": "", "home_state_codes": ""}
            changed, log, skipped = _apply_enrich(
                canonical_row, empty_eci, claimed_aliases, external_short
            )
            if changed:
                alias_added += 1
                for sk in skipped:
                    alias_collisions.append((proposed_pid, sk))
        elif verdict == "VERIFIED" and action == "conflict":
            # Mark the verdict row with a curator note + ECI source_id.
            if not (vrow.get("curator_note") or "").strip():
                vrow["curator_note"] = (
                    "abbreviation/slug collision: ECI party shares a short "
                    "with a different canonical party. Curator: mint ECI as "
                    "a new id (e.g. parties.IN.<UPPER_FULL_PREFIX>) and add "
                    "the upstream short to canonical's aliases only if both "
                    "parties genuinely share the publisher's preferred short."
                )
            if not (vrow.get("curator_source_id") or "").strip():
                vrow["curator_source_id"] = eci_source_id
            conflicts_marked += 1
        elif verdict == "UNVERIFIED" and action == "mint-new":
            mint_new_deferred.append(
                f"{external_short}={proposed_pid} ({vrow.get('external_full', '')[:60]})"
            )
        # match + other combinations are no-ops at this layer.

    # Write back: parties.csv (mutated rows) + verdict.csv (conflict notes).
    if args.apply:
        _write_csv(PARTIES_CSV, parties_fields, parties_rows)
        _write_csv(args.verdict, verdict_fields, verdict_rows)

    # Stats.
    by_verdict_action: Counter[tuple[str, str]] = Counter()
    for vrow in verdict_rows:
        by_verdict_action[
            ((vrow.get("verdict") or ""), (vrow.get("action") or ""))
        ] += 1
    print(f"[recon-curate-eci-registered] verdict.csv = {args.verdict.as_posix()}")
    print(f"  ECI source_id (citation):   {eci_source_id}")
    print(f"  verdict rows total:         {len(verdict_rows)}")
    for (v, a), n in sorted(by_verdict_action.items()):
        print(f"    {v:>10}  {a:>10}  {n}")
    print(f"  enrich rows applied:        {enriched}")
    for field, n in sorted(enrich_changes.items()):
        print(f"    field={field:<20}  {n} cells")
    print(f"  alias-add rows applied:     {alias_added}")
    print(f"  alias collisions skipped:   {len(alias_collisions)}")
    if alias_collisions:
        for pid, sk in alias_collisions[:10]:
            print(f"    {pid} would have added alias {sk}")
        if len(alias_collisions) > 10:
            print(f"    ... +{len(alias_collisions) - 10} more")
    print(f"  conflict rows marked:       {conflicts_marked}")
    print(f"  mint-new deferred:          {len(mint_new_deferred)}")
    for entry in mint_new_deferred:
        print(f"    {entry}")
    print(f"  skipped (no canonical):     {skipped_no_canonical}")
    print(f"  skipped (no ECI record):    {skipped_no_eci}")
    print(f"  apply mode:                 {args.apply}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
