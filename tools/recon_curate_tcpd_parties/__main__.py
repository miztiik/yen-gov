"""Curator script: apply PR-W-1 TCPD parity verdict.csv to parties.csv.

Reads ``datasets/ephemeral/party-parity/tcpd-parties/2021/<sha>/verdict.csv``
and applies the operator-curatable enrichments to
``datasets/data/entities/parties.csv``:

  - ``verdict == VERIFIED`` + ``action == enrich``:
      * Fill ``founded_year`` if empty (TCPD ``Start_Year``).
      * Fill ``recognition_scope`` if empty (TCPD ``Party_Type`` -> enum).
      * Append any new TCPD abbreviation to ``aliases`` (pipe-delim, UPPER).
  - ``verdict == VERIFIED`` + ``action == match``: no-op (already aligned).
  - ``verdict == VERIFIED`` + ``action == conflict``: NO mutation. Adds a
    ``curator_note`` to the verdict.csv naming the collision and a
    ``curator_source_id`` pointing at TCPD's source.csv row (PR-W-1
    minted, see _ensure_tcpd_source).
  - ``verdict == UNVERIFIED`` + ``action == mint-new``: NO mutation. The
    deferred-mint list is dumped to stdout for Hans-catalogue review.

Per CLAUDE.md section 10 (auto-correct BANNED on publisher disagreement)
+ Wave 0 / Hans verdict ("hand-curation is the only path"), this script
NEVER mutates parties.csv beyond strict fill-empty-cells-only operations.
It does not overwrite existing canonical data. Real disagreements stay
in the verdict.csv as ledger rows for the curator to action manually.

Run from the repo root (dry-run by default; pass --apply to write):

    python -m tools.recon_curate_tcpd_parties \\
        --verdict datasets/ephemeral/party-parity/tcpd-parties/2021/<sha>/verdict.csv \\
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

# Allow ``python -m tools.recon_curate_tcpd_parties`` from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.canonical.citation import derive_source_id  # noqa: E402
from yen_gov.canonical.recon.adapters.tcpd_parties import (  # noqa: E402
    DEFAULT_TCPD_CSV,
    _PARTY_TYPE_TO_RECOGNITION,
    _group_tcpd_rows_by_party_id,
)

PARTIES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
SOURCE_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "source.csv"

#: PR-W-1's TCPD parties catalogue citation triple (per ADR-0032). The
#: same triple yields the same source_id everywhere; this is the row
#: derive_source_id returns for. Carries vintage="2021" matching the
#: compilation cutoff (ADR-0042 publisher edition anchor).
TCPD_PARTIES_PRODUCER = "Trivedi Centre for Political Data, Ashoka University"
TCPD_PARTIES_TITLE = (
    "Political Parties of India - per-party catalogue compiled "
    "1962-2021 from ECI returns (TCPD compilation)"
)
TCPD_PARTIES_VINTAGE = "2021"
TCPD_PARTIES_URL = "https://tcpd.ashoka.edu.in/lok-dhaba/"


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """Write CSV with deterministic LF + no trailing comma (matches writer chain)."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        # Fill missing keys with empty (CSV-stable across writers).
        full = {k: (row.get(k) or "") for k in fieldnames}
        writer.writerow(full)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _ensure_tcpd_source(*, apply: bool) -> str:
    """Find-or-add the TCPD-parties-catalogue source.csv row; return source_id.

    Idempotent: if a row with the same (producer, title, vintage) triple
    already exists in source.csv, returns its source_id without
    modification. Otherwise appends a new row (only when --apply is
    passed; dry-run computes the id and returns it without writing).
    """
    source_id = derive_source_id(
        TCPD_PARTIES_PRODUCER, TCPD_PARTIES_TITLE, TCPD_PARTIES_VINTAGE
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
            "owner": TCPD_PARTIES_PRODUCER,
            "title": TCPD_PARTIES_TITLE,
            "vintage": TCPD_PARTIES_VINTAGE,
            "url": TCPD_PARTIES_URL,
        }
    )
    # source.csv is sorted lexicographically by source_id in upstream
    # writers (entity-seed.py emits sorted); keep the convention.
    rows.sort(key=lambda r: r.get("source_id", ""))
    _write_csv(SOURCE_CSV, fieldnames, rows)
    return source_id


def _index_tcpd_by_party_id() -> dict[str, dict[str, str]]:
    """Re-read TCPD CSV and project to {tcpd_party_id: {start_year, type, abbrevs}}.

    Lifted from the adapter's grouping so the curator can resolve verdict
    rows back to the original TCPD party row for enrichment payload
    (founded_year, recognition_scope, alias-list).
    """
    tcpd_csv = REPO_ROOT / DEFAULT_TCPD_CSV
    if not tcpd_csv.exists():
        raise FileNotFoundError(
            f"TCPD CSV not found at {tcpd_csv.as_posix()!r}; "
            f"required by recon-curate (cited in adapter docstring)."
        )
    with tcpd_csv.open(encoding="utf-8", newline="") as fh:
        raw = list(csv.DictReader(fh))
    out: dict[str, dict[str, str]] = {}
    for tp in _group_tcpd_rows_by_party_id(raw):
        out[tp.party_id] = {
            "start_year": str(tp.start_year) if tp.start_year else "",
            "party_type": tp.party_type,
            "abbrevs": "|".join(tp.all_abbrevs),
        }
    return out


def _apply_enrich(
    canonical_row: dict[str, str],
    tcpd_record: dict[str, str],
    claimed_aliases: dict[str, str],
) -> tuple[bool, list[str], list[str]]:
    """Apply VERIFIED+enrich payload to a canonical parties.csv row.

    Returns ``(changed, change_log, skipped_collisions)``.
      - ``changed`` is True iff any cell was modified.
      - ``change_log`` is the per-cell human-readable mutation list.
      - ``skipped_collisions`` is the list of TCPD abbreviations that
        would have collided with another canonical party's alias key
        (e.g. TCPD AIADMK's "ADK" alias would collide with canonical
        parties.IN.ADK's short). Collisions are SKIPPED so the resolver
        load doesn't fail-loud on duplicate alias key.

    Mutates ``canonical_row`` AND ``claimed_aliases`` in place (the
    latter so subsequent ``_apply_enrich`` calls in the same pass see
    the freshly-added aliases as claimed).

    Fill-empty-only rule: writes to founded_year + recognition_scope ONLY
    when the canonical cell is empty. Never overwrites authored values.
    """
    log: list[str] = []
    skipped: list[str] = []
    pid = (canonical_row.get("party_id") or "").strip()
    # founded_year
    if tcpd_record["start_year"] and not (canonical_row.get("founded_year") or "").strip():
        canonical_row["founded_year"] = tcpd_record["start_year"]
        log.append(f"founded_year={tcpd_record['start_year']}")
    # recognition_scope (only when canonical is empty AND the TCPD type maps)
    rec_scope = _PARTY_TYPE_TO_RECOGNITION.get(tcpd_record["party_type"])
    if rec_scope and not (canonical_row.get("recognition_scope") or "").strip():
        canonical_row["recognition_scope"] = rec_scope
        log.append(f"recognition_scope={rec_scope}")
    # alias-add: union TCPD's abbreviations with canonical aliases column,
    # but skip any abbreviation already claimed by a DIFFERENT canonical
    # party (would cause party_resolver to fail-loud on collision).
    canonical_short = (canonical_row.get("short") or "").upper().strip()
    aliases_raw = (canonical_row.get("aliases") or "").strip()
    current_aliases: set[str] = set()
    if aliases_raw:
        for a in aliases_raw.split("|"):
            v = a.strip().upper()
            if v:
                current_aliases.add(v)
    new_aliases: list[str] = []
    for abbrev in (tcpd_record["abbrevs"] or "").split("|"):
        v = abbrev.strip().upper()
        if not v or v == canonical_short or v in current_aliases:
            continue
        claimed_by = claimed_aliases.get(v)
        if claimed_by is not None and claimed_by != pid:
            skipped.append(f"{v}->{claimed_by}")
            continue
        new_aliases.append(v)
        current_aliases.add(v)
        claimed_aliases[v] = pid
    if new_aliases:
        existing_ordered = [a.strip() for a in aliases_raw.split("|") if a.strip()]
        merged = existing_ordered + new_aliases
        canonical_row["aliases"] = "|".join(merged)
        log.append(f"aliases+=[{'|'.join(new_aliases)}]")
    return bool(log), log, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--verdict",
        type=Path,
        required=True,
        help="Path to the verdict.csv produced by `python -m yen_gov parity --source tcpd-parties`.",
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

    # Read verdict.csv + parties.csv + project TCPD source-of-truth.
    verdict_fields, verdict_rows = _read_csv(args.verdict)
    parties_fields, parties_rows = _read_csv(PARTIES_CSV)
    parties_by_pid: dict[str, dict[str, str]] = {
        (r.get("party_id") or "").strip(): r for r in parties_rows if r.get("party_id")
    }
    tcpd_by_pid = _index_tcpd_by_party_id()

    # Build the claimed-alias index across ALL canonical parties so
    # _apply_enrich can skip TCPD abbreviations that would collide with
    # a different party's short or aliases (the party_resolver loader
    # fails-loud on duplicate keys; this skip-policy keeps the parity
    # idempotent rather than crashing post-apply).
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

    # Idempotent: ensure source.csv carries the TCPD-parties citation.
    tcpd_source_id = _ensure_tcpd_source(apply=args.apply)

    enriched = 0
    enrich_changes: Counter[str] = Counter()
    alias_collisions: list[tuple[str, str]] = []  # (party_id, "alias->claimed_by")
    conflicts_marked = 0
    skipped_no_canonical = 0
    skipped_no_tcpd = 0

    for vrow in verdict_rows:
        verdict = (vrow.get("verdict") or "").strip()
        action = (vrow.get("action") or "").strip()
        proposed_pid = (vrow.get("proposed_party_id") or "").strip()
        external_key = (vrow.get("external_key") or "").strip()

        if verdict == "VERIFIED" and action == "enrich":
            canonical_row = parties_by_pid.get(proposed_pid)
            tcpd_record = tcpd_by_pid.get(external_key)
            if canonical_row is None:
                skipped_no_canonical += 1
                continue
            if tcpd_record is None:
                skipped_no_tcpd += 1
                continue
            changed, log, skipped = _apply_enrich(
                canonical_row, tcpd_record, claimed_aliases
            )
            if changed:
                enriched += 1
                for entry in log:
                    field = entry.split("=", 1)[0].split("+=", 1)[0]
                    enrich_changes[field] += 1
            for sk in skipped:
                alias_collisions.append((proposed_pid, sk))
        elif verdict == "VERIFIED" and action == "conflict":
            # Mark the verdict row with a curator note pointing at TCPD source.
            if not (vrow.get("curator_note") or "").strip():
                vrow["curator_note"] = (
                    "abbreviation/slug collision: TCPD party shares a short "
                    "with a different canonical party. Curator: mint TCPD as "
                    "a new id (e.g. parties.IN.<UPPER_FULL_PREFIX>) and add "
                    "the upstream short to canonical's aliases only if both "
                    "parties genuinely share the publisher's preferred short."
                )
            if not (vrow.get("curator_source_id") or "").strip():
                vrow["curator_source_id"] = tcpd_source_id
            conflicts_marked += 1
        # UNVERIFIED + mint-new + VERIFIED + match are no-ops at this layer.

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
    print(f"[recon-curate-tcpd-parties] verdict.csv = {args.verdict.as_posix()}")
    print(f"  TCPD source_id (citation):  {tcpd_source_id}")
    print(f"  verdict rows total:         {len(verdict_rows)}")
    for (v, a), n in sorted(by_verdict_action.items()):
        print(f"    {v:>10}  {a:>10}  {n}")
    print(f"  enrich rows applied:        {enriched}")
    for field, n in sorted(enrich_changes.items()):
        print(f"    field={field:<20}  {n} cells")
    print(f"  alias collisions skipped:   {len(alias_collisions)}")
    if alias_collisions:
        # Print first 10 for the operator audit.
        for pid, sk in alias_collisions[:10]:
            print(f"    {pid} would have added alias {sk}")
        if len(alias_collisions) > 10:
            print(f"    ... +{len(alias_collisions) - 10} more")
    print(f"  conflict rows marked:       {conflicts_marked}")
    print(f"  skipped (no canonical):     {skipped_no_canonical}")
    print(f"  skipped (no TCPD record):   {skipped_no_tcpd}")
    print(f"  apply mode:                 {args.apply}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
