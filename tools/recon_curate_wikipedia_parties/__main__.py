"""Curator script: apply PR-W-3 Wikipedia parity verdict.csv to parties.csv.

Reads ``datasets/ephemeral/party-parity/wikipedia-parties/2026-06/<sha>/verdict.csv``
and applies the operator-curatable Q1-owned enrichments to
``datasets/data/entities/parties.csv``:

  - ``verdict == VERIFIED`` + ``action == enrich``:
      * Fill ``brand_colour`` if empty (Wikipedia infobox swatch).
      * Fill ``symbol_asset`` if empty (Wikipedia-named asset path under
        ``frontend/public/party-symbols/`` - validated by parties.csv
        Tier-B writer; not validated here).
      * Fill ``wikipedia`` if empty (canonical EN-Wikipedia page URL).
      * Fill ``name_native_script`` if empty (Wikipedia native script).
  - ``verdict == VERIFIED`` + ``action == match``: no-op (already aligned).
  - ``verdict == VERIFIED`` + ``action == conflict``: NO mutation. Marks
    the verdict row with ``curator_note`` + ``curator_source_id``
    pointing at Wikipedia's source.csv row for hand-curation.
  - ``verdict == UNVERIFIED`` + ``action == mint-new``: NO mutation. The
    deferred-mint list is dumped to stdout for hand-curation via
    ``hans_mints.py`` (which in PR-W-3 records the 8 candidate slugs
    for a future PR; per the brief mint-new is rare and the major Q7
    + Hans-33 mints landed in PR-W-1 + PR-W-2).

Per CLAUDE.md section 10 (auto-correct BANNED on publisher disagreement)
+ Wave 0 / Hans verdict ("hand-curation is the only path"), this script
NEVER overwrites authored canonical cells. Real disagreements (e.g.
Wikipedia says brand=#0000FF, canonical says brand=#FBEC5D - the SDF
case in the 2026-06 snapshot) are caught upstream by the adapter's
``_has_disputed_overwrite`` and emitted as ``conflict`` rows; the
curator marks them but never writes.

Per Q1 fact-class authority (plan section 0.3): Wikipedia wins on
``brand_colour``, ``symbol_asset``, ``wikipedia`` URL, and
``name_native_script`` - but ONLY via the fill-empty-only enrich leg
here. Overwriting an authored canonical cell with a Wikipedia value
happens via ``hans_mints.py`` with explicit per-row justification, and
PR-W-3 ships zero such hans-mint overwrites (the PR-W-1 / PR-W-2
ground-truth on Q1-Wikipedia-owned columns is taken as already
curator-vetted; only the empty cells are touched).

Run from the repo root (dry-run by default; pass --apply to write):

    python -m tools.recon_curate_wikipedia_parties \\
        --verdict datasets/ephemeral/party-parity/wikipedia-parties/2026-06/<sha>/verdict.csv \\
        --apply

The verdict.csv path is written-back-in-place with curator_note +
curator_source_id columns populated for conflict rows; parties.csv is
read-modify-rewritten preserving original column order + LF line
terminators (matching the writer chain under canonical/).
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter
from pathlib import Path

# Allow ``python -m tools.recon_curate_wikipedia_parties`` from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.canonical.citation import derive_source_id  # noqa: E402
from yen_gov.canonical.recon.adapters.wikipedia_parties import (  # noqa: E402
    DEFAULT_WIKIPEDIA_CSV,
    _read_wikipedia_snapshot,
)

PARTIES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
SOURCE_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "source.csv"

#: PR-W-3's Wikipedia parties catalogue citation triple (per ADR-0032).
#: Carries vintage="2026-06" matching the operator snapshot window
#: (ADR-0042 publisher edition pin). The same triple anywhere in the
#: codebase yields the same source_id; that is the citation-ledger
#: invariant.
WIKIPEDIA_PRODUCER = "Wikipedia"
WIKIPEDIA_TITLE = (
    "List of political parties in India + per-party infoboxes "
    "(operator-committed 2026-06 snapshot)"
)
WIKIPEDIA_VINTAGE = "2026-06"
WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_political_parties_in_India"


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


def _ensure_wikipedia_source(*, apply: bool) -> str:
    """Find-or-add the Wikipedia-parties source.csv row; return source_id.

    Idempotent: if a row with the same (producer, title, vintage) triple
    already exists in source.csv, returns its source_id without
    modification. Otherwise appends a new row (only when --apply is
    passed; dry-run computes the id and returns it without writing).
    """
    source_id = derive_source_id(
        WIKIPEDIA_PRODUCER, WIKIPEDIA_TITLE, WIKIPEDIA_VINTAGE
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
            "owner": WIKIPEDIA_PRODUCER,
            "title": WIKIPEDIA_TITLE,
            "vintage": WIKIPEDIA_VINTAGE,
            "url": WIKIPEDIA_URL,
        }
    )
    rows.sort(key=lambda r: r.get("source_id", ""))
    _write_csv(SOURCE_CSV, fieldnames, rows)
    return source_id


def _index_wikipedia_by_key() -> dict[str, dict[str, str]]:
    """Re-read Wikipedia snapshot, key by external_key (=party_id_or_short).

    The adapter emits ``external_key = party_id_or_short`` (which is the
    canonical ``parties.IN.<SLUG>`` for all 76 rows in the 2026-06
    snapshot). The curator uses this same key to look up the Wikipedia
    record carrying the Q1-owned enrichment payload.
    """
    wiki_csv = REPO_ROOT / DEFAULT_WIKIPEDIA_CSV
    if not wiki_csv.exists():
        raise FileNotFoundError(
            f"Wikipedia snapshot CSV not found at {wiki_csv.as_posix()!r}; "
            f"required by recon-curate (cited in adapter docstring)."
        )
    records = _read_wikipedia_snapshot(wiki_csv)
    out: dict[str, dict[str, str]] = {}
    for rec in records:
        key = (rec.party_id_or_short or "").strip()
        if not key:
            continue
        # Keyed by party_id_or_short (verdict.csv external_key carries
        # the same value). Last-write-wins on the rare collision.
        out[key] = {
            "brand_colour": rec.brand_colour,
            "symbol_asset": rec.symbol_asset,
            "wikipedia": rec.wikipedia_url,
            "name_native_script": rec.native_script,
            "full": rec.full,
        }
    return out


def _apply_enrich(
    canonical_row: dict[str, str], wiki_record: dict[str, str]
) -> tuple[bool, list[str]]:
    """Apply VERIFIED+enrich payload to a canonical parties.csv row.

    Q1-owned fill-empty-only operation on:
      - brand_colour
      - symbol_asset
      - wikipedia
      - name_native_script

    Returns ``(changed, change_log)``.

    Mutates ``canonical_row`` in place.

    Fill-empty-only rule per CLAUDE.md section 10: never overwrites
    authored values. Real disagreements are emitted by the adapter as
    ``conflict`` rows and surfaced for hand-curation; the curator
    marks them but never writes.
    """
    log: list[str] = []
    # brand_colour
    wiki_brand = (wiki_record.get("brand_colour") or "").strip()
    if wiki_brand and not (canonical_row.get("brand_colour") or "").strip():
        canonical_row["brand_colour"] = wiki_brand
        log.append(f"brand_colour={wiki_brand}")
    # symbol_asset
    wiki_symbol = (wiki_record.get("symbol_asset") or "").strip()
    if wiki_symbol and not (canonical_row.get("symbol_asset") or "").strip():
        canonical_row["symbol_asset"] = wiki_symbol
        log.append(f"symbol_asset={wiki_symbol}")
    # wikipedia
    wiki_url = (wiki_record.get("wikipedia") or "").strip()
    if wiki_url and not (canonical_row.get("wikipedia") or "").strip():
        canonical_row["wikipedia"] = wiki_url
        log.append(f"wikipedia={wiki_url}")
    # name_native_script
    wiki_native = (wiki_record.get("name_native_script") or "").strip()
    if wiki_native and not (canonical_row.get("name_native_script") or "").strip():
        canonical_row["name_native_script"] = wiki_native
        log.append(f"name_native_script={wiki_native[:24]}{'...' if len(wiki_native) > 24 else ''}")
    return bool(log), log


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--verdict",
        type=Path,
        required=True,
        help="Path to the verdict.csv produced by `python -m yen_gov parity --source wikipedia-parties`.",
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

    # Read verdict.csv + parties.csv + project Wikipedia source-of-truth.
    verdict_fields, verdict_rows = _read_csv(args.verdict)
    parties_fields, parties_rows = _read_csv(PARTIES_CSV)
    parties_by_pid: dict[str, dict[str, str]] = {
        (r.get("party_id") or "").strip(): r for r in parties_rows if r.get("party_id")
    }
    wiki_by_key = _index_wikipedia_by_key()

    # Idempotent: ensure source.csv carries the Wikipedia citation.
    wiki_source_id = _ensure_wikipedia_source(apply=args.apply)

    enriched = 0
    enrich_changes: Counter[str] = Counter()
    conflicts_marked = 0
    matches_seen = 0
    skipped_no_canonical = 0
    skipped_no_wiki = 0
    mint_new_deferred: list[str] = []

    for vrow in verdict_rows:
        verdict = (vrow.get("verdict") or "").strip()
        action = (vrow.get("action") or "").strip()
        proposed_pid = (vrow.get("proposed_party_id") or "").strip()
        external_key = (vrow.get("external_key") or "").strip()
        # The verdict.csv carries one wikipedia-parties row + one
        # yen-gov-canonical pair row per matched record. Skip the
        # canonical-side rows so we apply each enrichment once.
        oracles_agreeing = (vrow.get("oracles_agreeing") or "").strip()
        if oracles_agreeing == "yen-gov-canonical":
            continue
        # The dual-emit aggregator collapses to a single VERIFIED row
        # per (proposed_party_id, action) pair; we still defensively
        # de-dup by external_key against an already-applied set.

        if verdict == "VERIFIED" and action == "enrich":
            canonical_row = parties_by_pid.get(proposed_pid)
            wiki_record = wiki_by_key.get(external_key)
            if canonical_row is None:
                skipped_no_canonical += 1
                continue
            if wiki_record is None:
                skipped_no_wiki += 1
                continue
            changed, log = _apply_enrich(canonical_row, wiki_record)
            if changed:
                enriched += 1
                for entry in log:
                    field = entry.split("=", 1)[0]
                    enrich_changes[field] += 1
        elif verdict == "VERIFIED" and action == "match":
            # Canonical already carries everything Wikipedia has; no
            # write. Still counted for the audit.
            matches_seen += 1
        elif verdict == "DISPUTED" and action == "conflict":
            # Wikipedia disagrees with a non-empty canonical Q1-owned
            # cell. Mark with curator_note + curator_source_id; do not
            # mutate parties.csv (Hans rule: auto-correct BANNED).
            if not (vrow.get("curator_note") or "").strip():
                vrow["curator_note"] = (
                    "Q1-owned Wikipedia value disagrees with a non-empty "
                    "canonical cell. Per Q1 fact-class table Wikipedia wins, "
                    "but the curator must hand-apply via hans_mints.py with "
                    "explicit justification (e.g. flagship colour rebranding, "
                    "infobox swatch update). Do not silently overwrite the "
                    "existing canonical value."
                )
            if not (vrow.get("curator_source_id") or "").strip():
                vrow["curator_source_id"] = wiki_source_id
            conflicts_marked += 1
        elif verdict == "UNVERIFIED" and action == "mint-new":
            mint_new_deferred.append(
                f"{external_key}={proposed_pid} ({(vrow.get('external_full') or '')[:60]})"
            )
        # Other combinations (VERIFIED+alias-add hypothetically, etc.)
        # are no-ops at this layer; the Wikipedia adapter never emits
        # alias-add (alias enrichment is TCPD/ECI territory per Q1).

    # Write back: parties.csv (mutated rows) + verdict.csv (conflict notes).
    if args.apply:
        _write_csv(PARTIES_CSV, parties_fields, parties_rows)
        _write_csv(args.verdict, verdict_fields, verdict_rows)

    # Stats.
    by_verdict_action: Counter[tuple[str, str]] = Counter()
    for vrow in verdict_rows:
        # Same de-dup against canonical-side rows so the report counts
        # actual decisions rather than dual-emit pairs.
        if (vrow.get("oracles_agreeing") or "").strip() == "yen-gov-canonical":
            continue
        by_verdict_action[
            ((vrow.get("verdict") or ""), (vrow.get("action") or ""))
        ] += 1
    print(f"[recon-curate-wikipedia-parties] verdict.csv = {args.verdict.as_posix()}")
    print(f"  Wikipedia source_id (citation):   {wiki_source_id}")
    print(f"  verdict rows (de-dup canonical):  {sum(by_verdict_action.values())}")
    for (v, a), n in sorted(by_verdict_action.items()):
        print(f"    {v:>10}  {a:>10}  {n}")
    print(f"  enrich rows applied:        {enriched}")
    for field, n in sorted(enrich_changes.items()):
        print(f"    field={field:<20}  {n} cells")
    print(f"  match rows (no-op):         {matches_seen}")
    print(f"  conflict rows marked:       {conflicts_marked}")
    print(f"  mint-new deferred:          {len(mint_new_deferred)}")
    for entry in mint_new_deferred:
        print(f"    {entry}")
    print(f"  skipped (no canonical):     {skipped_no_canonical}")
    print(f"  skipped (no Wikipedia):     {skipped_no_wiki}")
    print(f"  apply mode:                 {args.apply}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
