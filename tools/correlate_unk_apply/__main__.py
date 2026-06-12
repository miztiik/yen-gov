"""Apply ``tools.correlate_unk_via_tcpd``'s verdict.csv to parties.csv.

See the package docstring (``tools/correlate_unk_apply/__init__.py``) for
the full rationale + the design contract. This is the executable entry
point.

Run from the repo root:

    python -m tools.correlate_unk_apply
    python -m tools.correlate_unk_apply --verdict-csv <path>
    python -m tools.correlate_unk_apply --dry-run

Default picks the newest verdict.csv under
``datasets/ephemeral/party-parity/tcpd-correlate/<sha>/`` (mtime sort).

Idempotency contract:
  - alias-add: if the publisher label is already aliased to the target
    party_id (case-insensitive), no-op.
  - mint-new: if a row with ``proposed_party_id`` already exists, skip.
  - Re-running the same verdict over an already-applied parties.csv
    produces zero mutations.

Collision-skip contract (Holy Law #5 fail-loud surfacing):
  - alias-add target missing in parties.csv -> skip + log.
  - alias-add publisher label already aliased to a DIFFERENT party -> skip
    + log.
  - mint-new proposed_party_id collides with an existing party_id -> skip
    + log.
  - mint-new tcpd_frequent_abbrev or publisher label collides with an
    existing party's short/alias -> skip + log.

Surfaces ``disputed`` (216) + ``skip`` (420) verdict-row counts but does
NOT mutate on those: the curator reviews them out-of-band. See
``docs/concepts/party-identity.md`` for the per-class adjudication policy.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.canonical.citation import derive_source_id  # noqa: E402

PARTIES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
SOURCE_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "source.csv"
STATE_ISO_SEED = REPO_ROOT / "datasets" / "data" / "entities" / "state_iso_seed.csv"
VERDICT_ROOT = (
    REPO_ROOT / "datasets" / "ephemeral" / "party-parity" / "tcpd-correlate"
)

# Schema v1.1, 18 columns. MUST match the on-disk header.
PARTIES_FIELDNAMES = [
    "party_id",
    "short",
    "full",
    "eci_codes",
    "brand_colour",
    "symbol_asset",
    "wikipedia",
    "aliases",
    "recognition_scope",
    "home_state_codes",
    "founded_year",
    "dissolved_year",
    "predecessor_party_ids",
    "successor_party_ids",
    "name_history",
    "claims_to_parent_name",
    "name_native_script",
    "is_sentinel",
]

# TCPD per-party catalogue Party_Type -> parties.csv recognition_scope enum
# (columns.json: ["national", "state", "unrecognised_registered", "defunct",
# "sentinel"]). TCPD's free-text values map as follows; everything else
# (including blank) projects to empty (nullable column accepts it).
TCPD_PARTY_TYPE_TO_SCOPE: dict[str, str] = {
    "Local Party": "unrecognised_registered",
    "State-based Party": "state",
    "National Party": "national",
}

# TCPD per-party catalogue source citation (already in source.csv as
# src-4040a970f10c; verified here so the apply step is self-contained).
TCPD_CITATION_PRODUCER = "Trivedi Centre for Political Data, Ashoka University"
TCPD_CITATION_TITLE = (
    "Political Parties of India - per-party catalogue compiled 1962-2021 "
    "from ECI returns (TCPD compilation)"
)
TCPD_CITATION_VINTAGE = "2021"
TCPD_CITATION_URL = "https://tcpd.ashoka.edu.in/lok-dhaba/"
SOURCE_FIELDNAMES = ["source_id", "producer", "title", "vintage", "url"]


# --- helpers ----------------------------------------------------------------


def _latest_verdict_csv() -> Path:
    """Return the newest verdict.csv under the sha-tagged directory tree."""
    candidates = sorted(
        VERDICT_ROOT.glob("*/verdict.csv"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise SystemExit(
            f"no verdict.csv found under "
            f"{VERDICT_ROOT.relative_to(REPO_ROOT).as_posix()}; "
            f"run 'python -m tools.correlate_unk_via_tcpd' first."
        )
    return candidates[-1]


def _load_state_slug_to_iso() -> dict[str, str]:
    """Build ``lgd-slug -> ISO 3166-2`` map from ``state_iso_seed.csv``.

    Returns an empty map when the seed file is missing (the mint will then
    leave ``home_state_codes`` empty rather than fail loud, matching the
    existing parties.csv convention where 92% of rows carry no
    ``home_state_codes``).
    """
    out: dict[str, str] = {}
    if not STATE_ISO_SEED.exists():
        return out
    with STATE_ISO_SEED.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            slug = (row.get("slug") or "").strip()
            iso = (row.get("iso_3166_2") or "").strip()
            if slug and iso:
                out[slug] = iso
    return out


def _derive_home_state_codes(state_field: str, slug_to_iso: dict[str, str]) -> str:
    """Project pipe-delim verdict ``state`` into pipe-delim ISO codes."""
    if not state_field.strip():
        return ""
    slugs = [s.strip() for s in state_field.split("|") if s.strip()]
    isos = sorted({slug_to_iso[s] for s in slugs if s in slug_to_iso})
    return "|".join(isos)


def _aliases_union(existing: str, new_label: str) -> str | None:
    """Append ``new_label`` to existing aliases pipe-list (UPPER-cased).

    Returns the updated pipe-list, or ``None`` if ``new_label`` (compared
    case-insensitively) is already present.
    """
    upper_new = (new_label or "").strip().upper()
    if not upper_new:
        return None
    existing_tokens = [a.strip() for a in (existing or "").split("|") if a.strip()]
    existing_upper = {a.upper() for a in existing_tokens}
    if upper_new in existing_upper:
        return None
    return "|".join(existing_tokens + [upper_new])


def _build_alias_to_pid(rows: list[dict[str, str]]) -> dict[str, str]:
    """``UPPER(short|alias) -> party_id`` for collision detection.

    Mirrors the resolver's ``load_resolver`` index logic (party_resolver.py
    section "by_alias") so a collision flagged here is a collision the
    resolver would also raise via ``ValueError``.
    """
    out: dict[str, str] = {}
    for row in rows:
        pid = (row.get("party_id") or "").strip()
        if not pid:
            continue
        short = (row.get("short") or "").strip().upper()
        if short:
            out[short] = pid
        aliases_raw = (row.get("aliases") or "").strip()
        if aliases_raw:
            for alias in aliases_raw.split("|"):
                cleaned = alias.strip().upper()
                if cleaned:
                    out[cleaned] = pid
    return out


def _ensure_tcpd_citation(source_csv: Path) -> tuple[bool, str]:
    """Append the TCPD per-party catalogue citation row if not present.

    Returns ``(added, source_id)``. ``added`` is True if a new row was
    appended; False if the citation was already present. The source_id
    is the deterministic 12-char hash from ``derive_source_id``.
    """
    expected_sid = derive_source_id(
        TCPD_CITATION_PRODUCER, TCPD_CITATION_TITLE, TCPD_CITATION_VINTAGE,
    )
    existing_sids: set[str] = set()
    if source_csv.exists():
        with source_csv.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                existing_sids.add((row.get("source_id") or "").strip())
    if expected_sid in existing_sids:
        return False, expected_sid
    # Append row preserving LF line endings.
    with source_csv.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=SOURCE_FIELDNAMES, lineterminator="\n",
        )
        writer.writerow({
            "source_id": expected_sid,
            "producer": TCPD_CITATION_PRODUCER,
            "title": TCPD_CITATION_TITLE,
            "vintage": TCPD_CITATION_VINTAGE,
            "url": TCPD_CITATION_URL,
        })
    return True, expected_sid


# --- main loop --------------------------------------------------------------


def apply_verdict(
    *,
    parties_csv: Path,
    verdict_csv: Path,
    slug_to_iso: dict[str, str],
    dry_run: bool = False,
) -> tuple[Counter[str], dict[str, list[str]], list[dict[str, str]]]:
    """Apply ``verdict_csv`` to ``parties_csv`` in place.

    Returns ``(stats, skipped_examples, final_rows)``. ``stats`` is a
    Counter of action / outcome tallies; ``skipped_examples`` is a per-
    reason list of up to a few human-readable detail strings for the
    operator log. ``final_rows`` is the projected on-disk shape (used by
    tests to assert against without re-reading the file).
    """
    with parties_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        original_fieldnames = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    if original_fieldnames != PARTIES_FIELDNAMES:
        raise SystemExit(
            f"parties.csv columns drift detected.\n  expected: "
            f"{PARTIES_FIELDNAMES}\n  got:      {original_fieldnames}"
        )

    by_pid: dict[str, dict[str, str]] = {
        (row.get("party_id") or "").strip(): row
        for row in rows
        if (row.get("party_id") or "").strip()
    }
    alias_to_pid = _build_alias_to_pid(rows)

    with verdict_csv.open(encoding="utf-8", newline="") as fh:
        verdict_rows = list(csv.DictReader(fh))

    stats: Counter[str] = Counter()
    skipped: dict[str, list[str]] = {}

    def _skip(reason: str, detail: str) -> None:
        stats[f"skip:{reason}"] += 1
        skipped.setdefault(reason, []).append(detail)

    new_rows: list[dict[str, str]] = []

    for v in verdict_rows:
        action = (v.get("action") or "").strip()
        stats[f"action:{action}"] += 1

        if action == "alias-add":
            target_pid = (v.get("proposed_party_id") or "").strip()
            new_label = (v.get("party_short_raw") or "").strip()
            row = by_pid.get(target_pid)
            if row is None:
                _skip(
                    "alias-add-missing-target",
                    f"{new_label!r} -> {target_pid} (target row not in parties.csv)",
                )
                continue
            collision_pid = alias_to_pid.get(new_label.upper())
            if collision_pid is not None and collision_pid != target_pid:
                _skip(
                    "alias-add-collision",
                    f"{new_label!r} would alias {target_pid} but is already aliased to {collision_pid}",
                )
                continue
            updated = _aliases_union(row.get("aliases") or "", new_label)
            if updated is None:
                stats["alias-add:already-present"] += 1
                continue
            row["aliases"] = updated
            alias_to_pid[new_label.upper()] = target_pid
            stats["alias-add:applied"] += 1
            continue

        if action == "mint-new":
            new_pid = (v.get("proposed_party_id") or "").strip()
            new_label = (v.get("party_short_raw") or "").strip()
            tcpd_short = (v.get("tcpd_frequent_abbrev") or "").strip()
            tcpd_full = (v.get("tcpd_party_name") or "").strip()
            tcpd_type = (v.get("tcpd_party_type") or "").strip()
            state_field = (v.get("state") or "").strip()
            if new_pid in by_pid:
                _skip(
                    "mint-pid-collision",
                    f"{new_pid} would be minted but exists (short={by_pid[new_pid].get('short','')!r})",
                )
                continue
            short_value = tcpd_short or new_label
            short_upper = short_value.upper()
            collision_pid = alias_to_pid.get(short_upper)
            if collision_pid is not None:
                _skip(
                    "mint-short-collision",
                    f"{new_pid} would mint short={short_value!r} but that alias points at {collision_pid}",
                )
                continue
            label_upper = new_label.upper()
            if label_upper and label_upper != short_upper:
                collision_pid = alias_to_pid.get(label_upper)
                if collision_pid is not None:
                    _skip(
                        "mint-alias-collision",
                        f"{new_pid} would alias {new_label!r} but that label points at {collision_pid}",
                    )
                    continue
            home_iso = _derive_home_state_codes(state_field, slug_to_iso)
            scope = TCPD_PARTY_TYPE_TO_SCOPE.get(tcpd_type, "")
            alias_tokens: list[str] = []
            if label_upper and label_upper != short_upper:
                alias_tokens.append(label_upper)
            new_row = {fn: "" for fn in PARTIES_FIELDNAMES}
            new_row["party_id"] = new_pid
            new_row["short"] = short_value
            new_row["full"] = tcpd_full or new_label
            new_row["aliases"] = "|".join(alias_tokens)
            new_row["recognition_scope"] = scope
            new_row["home_state_codes"] = home_iso
            new_rows.append(new_row)
            by_pid[new_pid] = new_row
            alias_to_pid[short_upper] = new_pid
            for token in alias_tokens:
                alias_to_pid[token] = new_pid
            stats["mint-new:applied"] += 1
            continue

        if action == "disputed":
            stats["disputed:no-op"] += 1
            continue
        if action == "skip":
            stats["skip-source:no-op"] += 1
            continue
        stats[f"unknown-action:{action}"] += 1

    final_rows = rows + new_rows

    # Defensive: detect inadvertent dupe party_id (should be impossible given
    # the mint-pid-collision guard above, but the cost of a one-pass check is
    # near zero and a regression in the guard would silently corrupt parties.csv).
    seen: set[str] = set()
    for r in final_rows:
        pid = (r.get("party_id") or "").strip()
        if pid in seen:
            raise SystemExit(f"BUG: duplicate party_id {pid!r} in final rows; aborting apply.")
        seen.add(pid)

    if not dry_run:
        with parties_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=PARTIES_FIELDNAMES, lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(final_rows)

    return stats, skipped, final_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verdict-csv",
        type=Path,
        default=None,
        help=(
            "Path to verdict.csv. Default: newest under "
            "datasets/ephemeral/party-parity/tcpd-correlate/."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print stats but do not mutate parties.csv or source.csv.",
    )
    args = parser.parse_args()

    verdict_path = args.verdict_csv or _latest_verdict_csv()
    if not verdict_path.exists():
        raise SystemExit(f"verdict.csv not found at {verdict_path}")

    print(f"verdict.csv: {verdict_path.relative_to(REPO_ROOT).as_posix()}")
    print(f"parties.csv: {PARTIES_CSV.relative_to(REPO_ROOT).as_posix()}")
    print(f"source.csv:  {SOURCE_CSV.relative_to(REPO_ROOT).as_posix()}")
    print()

    slug_to_iso = _load_state_slug_to_iso()
    stats, skipped, final_rows = apply_verdict(
        parties_csv=PARTIES_CSV,
        verdict_csv=verdict_path,
        slug_to_iso=slug_to_iso,
        dry_run=args.dry_run,
    )

    if not args.dry_run:
        added, sid = _ensure_tcpd_citation(SOURCE_CSV)
        if added:
            print(f"source.csv: appended TCPD citation {sid}")
        else:
            print(f"source.csv: TCPD citation {sid} already present (no-op)")
    print()

    # Resolve the pre-existing row count from final_rows + the applied mints.
    n_minted = stats.get("mint-new:applied", 0)
    n_existing = len(final_rows) - n_minted
    print("=== apply stats ===")
    print(f"  verdict rows:           {stats.get('action:alias-add', 0) + stats.get('action:mint-new', 0) + stats.get('action:disputed', 0) + stats.get('action:skip', 0)}")
    print(f"  parties.csv before:     {n_existing} rows")
    print(f"  parties.csv after:      {len(final_rows)} rows (+{n_minted} mints)")
    print(f"  alias-add applied:      {stats.get('alias-add:applied', 0)}")
    print(f"  alias-add already-pres: {stats.get('alias-add:already-present', 0)}")
    print(f"  mint-new applied:       {n_minted}")
    print(f"  disputed (no-op):       {stats.get('disputed:no-op', 0)}")
    print(f"  skip-source (no-op):    {stats.get('skip-source:no-op', 0)}")
    print()
    print("=== collisions skipped ===")
    any_collision = False
    for reason in (
        "alias-add-missing-target",
        "alias-add-collision",
        "mint-pid-collision",
        "mint-short-collision",
        "mint-alias-collision",
    ):
        n = stats.get(f"skip:{reason}", 0)
        if n:
            any_collision = True
            print(f"  {reason}: {n}")
            for example in skipped.get(reason, [])[:3]:
                print(f"    e.g. {example}")
    if not any_collision:
        print("  (none)")
    print()
    if args.dry_run:
        print("DRY-RUN: parties.csv NOT modified.")
    else:
        print(f"parties.csv WRITTEN: {PARTIES_CSV.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
