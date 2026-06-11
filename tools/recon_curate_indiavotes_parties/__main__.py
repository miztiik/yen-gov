"""Curator script: apply IndiaVotes parity verdict.csv to parties.csv.

NEVER CI. Operator-run only. Reads
``datasets/ephemeral/party-parity/indiavotes-parties/2026-06/<sha>/verdict.csv``
and applies the operator-curatable enrichments to
``datasets/data/entities/parties.csv``:

  - ``verdict == VERIFIED`` + ``action == alias-add``: APPEND IV's
    publisher abbreviation to the canonical row's ``aliases`` pipe-list.
    Collision-skip if the abbreviation is already claimed by another
    canonical party (the abbreviation-collision guard in the adapter
    should have surfaced this as a conflict; the curator skips
    defensively rather than corrupt parties.csv with a dual-keyed alias).
  - ``verdict == VERIFIED`` + ``action == match``: no-op (already aligned).
  - ``verdict == VERIFIED`` + ``action == conflict``: NO mutation. Marks
    the verdict row with ``curator_note`` + ``curator_source_id``
    pointing at IndiaVotes's source.csv row for hand-curation.
  - ``verdict == UNVERIFIED`` + ``action == mint-new``: AUTO-APPLY a new
    parties.csv row using IV's full_name + slug + recognition_scope (mapped
    from iv_type) + founded_year / dissolved_year (from active period).
    Per the 2026-06-11 user signoff "A - fix all UNK and rajasthan", this
    is the DOMINANT enrichment path; ~150 new parties are minted from
    the IV snapshot. Each mint carries the IV abbreviation in BOTH the
    ``short`` column (display) AND the ``aliases`` pipe-list (so the
    party_resolver picks it up immediately after the next
    ``elections_party_id_repair --reresolve-unk`` sweep).

Per CLAUDE.md section 10 (auto-correct BANNED on publisher disagreement)
+ Wave 0 / Hans verdict ("hand-curation is the only path"), this script
NEVER overwrites authored canonical cells. The user signoff
("fix all UNK and rajasthan", 2026-06-11) PROMOTED IV from Q1
secondary-lane to a NEW enrichment-source for parties.csv aliases +
mint-new rows; the mint path IS the explicit operator green-light for
auto-applying new rows under IV's authority. Q1 fact-class table for
the EXISTING canonical cells is UNCHANGED (TCPD still wins on full,
ECI on recognition, Wikipedia on colour). Mint-new rows of course
populate empty cells with IV's data; that is NOT an overwrite of
authored canonical data (no canonical data exists for those parties).

Run from the repo root (dry-run by default; pass --apply to write):

    python -m tools.recon_curate_indiavotes_parties \\
        --verdict datasets/ephemeral/party-parity/indiavotes-parties/2026-06/<sha>/verdict.csv \\
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

# Allow ``python -m tools.recon_curate_indiavotes_parties`` from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.canonical.citation import derive_source_id  # noqa: E402
from yen_gov.canonical.recon.adapters.indiavotes_parties import (  # noqa: E402
    DEFAULT_INDIAVOTES_CSV,
    _make_slug,
    _read_indiavotes_snapshot,
    dissolved_year_from_active_to,
    recognition_from_iv_type,
)

PARTIES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
SOURCE_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "source.csv"

#: IndiaVotes catalogue citation triple (per ADR-0032).
#: Carries vintage="2026-06" matching the operator snapshot window
#: (ADR-0042 publisher edition pin). The same triple anywhere in the
#: codebase yields the same source_id; that is the citation-ledger
#: invariant.
INDIAVOTES_PRODUCER = "IndiaVotes"
INDIAVOTES_TITLE = (
    "IndiaVotes party catalogue (operator-committed 2026-06 snapshot; "
    "listing of recognised parties + per-slug detail probes)"
)
INDIAVOTES_VINTAGE = "2026-06"
INDIAVOTES_URL = "https://www.indiavotes.com/parties"


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


def _ensure_indiavotes_source(*, apply: bool) -> str:
    """Find-or-add the IndiaVotes source.csv row; return source_id.

    Idempotent: if a row with the same (producer, title, vintage) triple
    already exists in source.csv, returns its source_id without
    modification. Otherwise appends a new row (only when --apply is
    passed; dry-run computes the id and returns it without writing).
    """
    source_id = derive_source_id(
        INDIAVOTES_PRODUCER, INDIAVOTES_TITLE, INDIAVOTES_VINTAGE
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
            "owner": INDIAVOTES_PRODUCER,
            "title": INDIAVOTES_TITLE,
            "vintage": INDIAVOTES_VINTAGE,
            "url": INDIAVOTES_URL,
        }
    )
    rows.sort(key=lambda r: r.get("source_id", ""))
    _write_csv(SOURCE_CSV, fieldnames, rows)
    return source_id


def _index_iv_by_abbrev() -> dict[str, dict[str, str]]:
    """Re-read IV snapshot, key by abbreviation.

    The adapter emits ``external_key = abbreviation`` and the verdict
    aggregator preserves that key on the surface columns. The curator
    uses it to look up the IV record carrying the mint payload
    (full_name + iv_type + active period).
    """
    iv_csv = REPO_ROOT / DEFAULT_INDIAVOTES_CSV
    if not iv_csv.exists():
        raise FileNotFoundError(
            f"IndiaVotes snapshot CSV not found at {iv_csv.as_posix()!r}; "
            f"required by recon-curate (cited in adapter docstring)."
        )
    records = _read_indiavotes_snapshot(iv_csv)
    out: dict[str, dict[str, str]] = {}
    for rec in records:
        if not rec.abbrev:
            continue
        # Keyed by abbrev (verdict.csv external_key carries the same).
        # Last-write-wins on rare duplicate slugs.
        out[rec.abbrev] = {
            "full": rec.full,
            "iv_type": rec.iv_type,
            "iv_url": rec.iv_url,
            "active_from": rec.active_from,
            "active_to": rec.active_to,
            "slug": rec.slug,
            "source_lane": rec.source_lane,
        }
    return out


def _claimed_aliases(parties_rows: list[dict[str, str]]) -> dict[str, str]:
    """Build alias-UPPER -> party_id map for collision detection.

    Includes BOTH the canonical ``short`` column AND every pipe-split
    alias on every row. The curator uses this map to skip alias-add
    actions that would create dual-keyed aliases (alias X mapping to
    parties.IN.A + parties.IN.B is fatal to the resolver per
    party_resolver.load_resolver's ValueError).
    """
    out: dict[str, str] = {}
    for row in parties_rows:
        pid = (row.get("party_id") or "").strip()
        if not pid:
            continue
        short = (row.get("short") or "").upper().strip()
        if short:
            out[short] = pid
        aliases_raw = (row.get("aliases") or "").strip()
        if aliases_raw:
            for a in aliases_raw.split("|"):
                v = a.strip().upper()
                if v:
                    out[v] = pid
    return out


def _apply_alias_add(
    canonical_row: dict[str, str],
    short_to_add: str,
    claimed: dict[str, str],
) -> tuple[bool, str]:
    """Append ``short_to_add`` to the canonical row's aliases pipe-list.

    Returns ``(changed, log_entry_or_skip_reason)``.

    Collision-skip rules:
      - empty / non-alphanumeric short -> skip.
      - already in canonical short or aliases -> skip (idempotent re-run).
      - claimed by a DIFFERENT canonical party_id -> skip with reason
        (the adapter's collision guard SHOULD have surfaced this as a
        conflict; defensive guard here ensures no dual-keyed alias slips
        through).
    """
    pid = (canonical_row.get("party_id") or "").strip()
    short_upper = (short_to_add or "").upper().strip()
    if not short_upper:
        return False, "skip-empty"
    canonical_short = (canonical_row.get("short") or "").upper().strip()
    if short_upper == canonical_short:
        return False, "skip-already-short"
    aliases_raw = (canonical_row.get("aliases") or "").strip()
    aliases_list: list[str] = []
    if aliases_raw:
        aliases_list = [a.strip() for a in aliases_raw.split("|") if a.strip()]
    if short_upper in {a.upper() for a in aliases_list}:
        return False, "skip-already-alias"
    existing_owner = claimed.get(short_upper)
    if existing_owner is not None and existing_owner != pid:
        return False, f"skip-collision-with-{existing_owner}"
    aliases_list.append(short_upper)
    canonical_row["aliases"] = "|".join(aliases_list)
    claimed[short_upper] = pid
    return True, short_upper


def _mint_new(
    iv_record: dict[str, str],
    external_key: str,
    proposed_pid: str,
    claimed: dict[str, str],
) -> tuple[dict[str, str] | None, str]:
    """Build a NEW parties.csv row from IV's catalogue payload.

    Returns ``(new_row_dict, reason)``. ``new_row_dict`` is None when
    the mint must be skipped (e.g. alias collision on the new short).

    Mint payload:
      - party_id: ``proposed_pid`` from the verdict (built by adapter
        via _make_slug(external_key); identity-preserving).
      - short: IV's abbreviation (verbatim, e.g. "KJP").
      - full: IV's full_name (verbatim, e.g. "Karnataka Jantha Paksha").
      - eci_codes: empty (Q1 ECI-owned; ECI's next list refresh fills).
      - brand_colour / symbol_asset / wikipedia: empty.
      - aliases: IV's abbreviation again (UPPER) so resolver hits even
        before the canonical short is repointed (idempotent re-run is
        safe: alias-add to a freshly-minted row sees the abbreviation
        already in aliases and skips).
      - recognition_scope: derived from IV's iv_type via the lookup
        table. Empty when IV publishes an unknown token.
      - home_state_codes: empty (IV does not publish a state code).
      - founded_year: from IV's active-period lower bound (if parseable).
      - dissolved_year: from IV's active-period upper bound when < 2026.
      - predecessor_party_ids / successor_party_ids / name_history:
        empty (no lineage signal from IV catalogue alone).
      - claims_to_parent_name: empty (false; only Q7 splits set this).
      - name_native_script: empty (IV catalogue is English-only).
      - is_sentinel: empty (false; sentinels are the 3 manually-curated
        rows).

    Collision guard: if the abbreviation is already claimed by ANOTHER
    canonical party_id (a slug that maps to an existing alias), skip
    the mint and surface for hand-curation. The adapter's collision
    guard should have caught this case as a conflict; this is a
    defensive backstop.
    """
    short_upper = (external_key or "").upper().strip()
    full_name = (iv_record.get("full") or "").strip()
    if not short_upper or not full_name:
        return None, "skip-empty-payload"
    existing = claimed.get(short_upper)
    if existing is not None:
        return None, f"skip-collision-with-{existing}"
    recognition = recognition_from_iv_type(iv_record.get("iv_type", ""))
    dissolved = dissolved_year_from_active_to(iv_record.get("active_to", ""))
    founded = (iv_record.get("active_from") or "").strip()
    new_row: dict[str, str] = {
        "party_id": proposed_pid,
        "short": short_upper,
        "full": full_name,
        "eci_codes": "",
        "brand_colour": "",
        "symbol_asset": "",
        "wikipedia": "",
        "aliases": short_upper,
        "recognition_scope": recognition,
        "home_state_codes": "",
        "founded_year": founded,
        "dissolved_year": dissolved,
        "predecessor_party_ids": "",
        "successor_party_ids": "",
        "name_history": "",
        "claims_to_parent_name": "",
        "name_native_script": "",
        "is_sentinel": "",
    }
    claimed[short_upper] = proposed_pid
    return new_row, "minted"


def main() -> int:  # noqa: C901 -- single-pass curator; branchy by nature.
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--verdict",
        type=Path,
        required=True,
        help="Path to the verdict.csv produced by `python -m yen_gov parity --source indiavotes-parties`.",
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

    # Read verdict.csv + parties.csv + project IV source-of-truth.
    verdict_fields, verdict_rows = _read_csv(args.verdict)
    parties_fields, parties_rows = _read_csv(PARTIES_CSV)
    parties_by_pid: dict[str, dict[str, str]] = {
        (r.get("party_id") or "").strip(): r for r in parties_rows if r.get("party_id")
    }
    iv_by_abbrev = _index_iv_by_abbrev()

    # Idempotent: ensure source.csv carries the IndiaVotes citation.
    iv_source_id = _ensure_indiavotes_source(apply=args.apply)

    # Pre-build the alias collision map.
    claimed_aliases = _claimed_aliases(parties_rows)

    aliases_added = 0
    mints_applied: list[str] = []
    mints_skipped: list[tuple[str, str]] = []  # (pid, reason)
    conflicts_marked = 0
    matches_seen = 0
    skipped_canonical_present_for_match = 0
    alias_skip_reasons: Counter[str] = Counter()

    for vrow in verdict_rows:
        verdict = (vrow.get("verdict") or "").strip()
        action = (vrow.get("action") or "").strip()
        proposed_pid = (vrow.get("proposed_party_id") or "").strip()
        external_key = (vrow.get("external_key") or "").strip()
        oracles_agreeing = (vrow.get("oracles_agreeing") or "").strip()

        # The aggregator collapses both legs of a matched pair into a
        # single verdict row per proposed_party_id. We dispatch on action,
        # not on which oracle the row was emitted by.
        if verdict == "VERIFIED" and action == "alias-add":
            canonical_row = parties_by_pid.get(proposed_pid)
            if canonical_row is None:
                skipped_canonical_present_for_match += 1
                continue
            changed, reason = _apply_alias_add(
                canonical_row, external_key, claimed_aliases
            )
            if changed:
                aliases_added += 1
            else:
                alias_skip_reasons[reason] += 1
        elif verdict == "VERIFIED" and action == "match":
            matches_seen += 1
        elif verdict == "UNVERIFIED" and action == "mint-new":
            iv_record = iv_by_abbrev.get(external_key)
            if iv_record is None:
                mints_skipped.append((proposed_pid, "no-iv-record"))
                continue
            new_row, reason = _mint_new(
                iv_record, external_key, proposed_pid, claimed_aliases
            )
            if new_row is None:
                mints_skipped.append((proposed_pid, reason))
                continue
            parties_rows.append(new_row)
            parties_by_pid[proposed_pid] = new_row
            mints_applied.append(proposed_pid)
        elif action == "conflict":
            conflicts_marked += 1
            if not (vrow.get("curator_note") or "").strip():
                vrow["curator_note"] = (
                    "IndiaVotes proposed an alias/mint that collided with a "
                    "different canonical party_id (abbreviation-collision "
                    "guard). Curator: investigate whether IndiaVotes's slug "
                    "should mint under a different parties.IN.<SLUG> id, "
                    "OR whether canonical already covers this party under "
                    "a different short."
                )
            if not (vrow.get("curator_source_id") or "").strip():
                vrow["curator_source_id"] = iv_source_id

    # Re-sort parties.csv by party_id when any mints landed (matches the
    # canonical writer chain convention; deterministic on-disk order).
    if mints_applied and args.apply:
        parties_rows.sort(key=lambda r: (r.get("party_id") or "").strip())

    # Write back parties.csv + verdict.csv when --apply.
    if args.apply:
        if aliases_added or mints_applied:
            _write_csv(PARTIES_CSV, parties_fields, parties_rows)
        if conflicts_marked:
            _write_csv(args.verdict, verdict_fields, verdict_rows)

    # Operator-readable summary.
    print(f"{'APPLIED' if args.apply else 'DRY-RUN'} IndiaVotes curator report:")
    print(f"  verdict.csv:        {args.verdict.as_posix()}")
    print(f"  parties.csv:        {PARTIES_CSV.as_posix()}")
    print(f"  source.csv id:      {iv_source_id}")
    print()
    print(f"  alias-add applied:  {aliases_added}")
    if alias_skip_reasons:
        print("  alias-add skipped:")
        for reason, count in alias_skip_reasons.most_common():
            print(f"    {count:4d}  {reason}")
    print(f"  matches (no-op):    {matches_seen}")
    print(f"  mints applied:      {len(mints_applied)}")
    if mints_applied:
        print("    sample (first 20):")
        for pid in mints_applied[:20]:
            print(f"      + {pid}")
    if mints_skipped:
        print(f"  mints skipped:      {len(mints_skipped)}")
        for pid, reason in mints_skipped[:20]:
            print(f"    - {pid}  ({reason})")
    print(f"  conflicts marked:   {conflicts_marked}")
    if skipped_canonical_present_for_match:
        print(
            f"  skipped (canonical missing for alias-add): "
            f"{skipped_canonical_present_for_match}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
