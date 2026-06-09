"""Tier-A contract tests for the G16 alias backfill (electoral.csv aliases column).

Asserts the 36 BOUND (state, lgd_canonical_name) -> eci_published_alias mappings
landed on the live ``datasets/data/entities/electoral.csv``, and that the
``_build_pc_lookup`` walk picks them up at the next ingest.

Real-file tests: this is a contract test against the live spine on disk, not a
fixture-driven unit test. The Tier-A scope is the as-committed CSV row shape
plus the lookup-walk invariant; the per-row build-and-write logic is covered
by ``test_parliament_2024_eci.py`` against synthetic fixtures.
"""

from __future__ import annotations

import csv
import io
import subprocess
import sys
from pathlib import Path

from yen_gov.canonical.reingest.parliament_2024_eci import (
    _build_pc_lookup,
    _normalise_pc_name,
)

# 36 BOUND mappings from the G16 alias backfill discovery (2026-06-09).
# Format: (state_slug, lgd_canonical_name) -> eci_published_alias (verbatim).
BOUND_ALIASES: dict[tuple[str, str], str] = {
    ("andhra-pradesh", "Anantapur"): "Ananthapur",
    ("andhra-pradesh", "Kurnool"): "Kurnoolu",
    ("andhra-pradesh", "Narasaraopet"): "Narsaraopet",
    ("andhra-pradesh", "Tirupati"): "Thirupathi",
    ("assam", "Mangaldoi"): "Darrang-Udalguri",
    ("assam", "Autonomous District"): "Diphu",
    ("assam", "Gauhati"): "Guwahati",
    ("bihar", "Pataliputra"): "Patliputra",
    ("chhattisgarh", "Janjgir Champa"): "JANJGIR-CHAMPA",
    ("jammu-and-kashmir", "Anantnag"): "ANANTNAG-RAJOURI",
    ("jharkhand", "Palamau"): "Palamu",
    ("karnataka", "Bengaluru North"): "Bangalore North",
    ("karnataka", "Bengaluru Rural"): "Bangalore Rural",
    ("karnataka", "Bengaluru South"): "Bangalore South",
    ("karnataka", "Bengaluru Central"): "Bangalore central",
    ("karnataka", "Belagavi"): "Belgaum",
    ("karnataka", "Ballari"): "Bellary",
    ("karnataka", "Vijayapura"): "Bijapur",
    ("karnataka", "Kalaburagi"): "Gulbarga",
    ("karnataka", "Mysuru"): "Mysore",
    ("karnataka", "Shivamogga"): "Shimoga",
    ("karnataka", "Tumakuru"): "Tumkur",
    ("karnataka", "Udupi Chikkamagaluru"): "Udupi Chikmagalur",
    ("maharashtra", "Bhandara - Gondiya"): "Bhandara Gondiya",
    ("maharashtra", "Gadchiroli-Chimur"): "Gadchiroli - Chimur",
    ("maharashtra", "Hatkanangle"): "Hatkanangale",
    ("maharashtra", "Mumbai North-Central"): "Mumbai North Central",
    ("maharashtra", "Mumbai North-East"): "Mumbai North East",
    ("maharashtra", "Mumbai North-West"): "Mumbai North West",
    ("maharashtra", "Mumbai South-Central"): "Mumbai South Central",
    ("maharashtra", "Ratnagiri - Sindhudurg"): "Ratnagiri- Sindhudurg",
    ("maharashtra", "Yavatmal-Washim"): "Yavatmal- Washim",
    ("telangana", "Mahabubnagar"): "Mahbubnagar",
    ("uttar-pradesh", "Bahraich"): "Baharaich",
    ("uttarakhand", "Hardwar"): "Haridwar",
    ("west-bengal", "Bardhaman - Durgapur"): "Bardhaman-Durgapur",
}


def _electoral_csv_path() -> Path:
    """Resolve ``datasets/data/entities/electoral.csv`` from the repo root.

    Walks up from this test file to the first ancestor containing
    ``datasets/`` (handles being run from ``backend/`` or repo root).
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "datasets" / "data" / "entities" / "electoral.csv"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("could not locate datasets/data/entities/electoral.csv")


def _load_pc_2008_rows() -> list[dict[str, str]]:
    path = _electoral_csv_path()
    with path.open(encoding="utf-8", newline="") as fh:
        return [
            r for r in csv.DictReader(fh)
            if r.get("entity_kind") == "pc"
            and (r.get("delim_year") or "").strip() == "2008"
        ]


def test_all_36_bound_rows_have_non_empty_alias_cell() -> None:
    """Every (state, lgd_canonical_name) in BOUND_ALIASES has its ECI variant set."""
    rows = _load_pc_2008_rows()
    by_key = {(r["state"], r["name"]): r for r in rows}
    missing = []
    for (state, name), expected_alias in BOUND_ALIASES.items():
        row = by_key.get((state, name))
        assert row is not None, f"spine row missing for ({state}, {name!r})"
        cell = (row.get("aliases") or "").strip()
        assert cell, f"aliases cell empty for ({state}, {name!r})"
        aliases = [a.strip() for a in cell.split("|") if a.strip()]
        if expected_alias not in aliases:
            missing.append((state, name, expected_alias, cell))
    assert not missing, f"missing aliases:\n" + "\n".join(
        f"  ({s}, {n!r}) expected {a!r} got {c!r}" for s, n, a, c in missing
    )


def test_each_eci_alias_appears_exactly_once_in_electoral_csv() -> None:
    """No alias-bind duplication or cross-state mis-assignment."""
    rows = _load_pc_2008_rows()
    expected_aliases = set(BOUND_ALIASES.values())
    seen: dict[str, list[tuple[str, str]]] = {alias: [] for alias in expected_aliases}
    for row in rows:
        cell = (row.get("aliases") or "").strip()
        if not cell:
            continue
        for alias in (a.strip() for a in cell.split("|") if a.strip()):
            if alias in expected_aliases:
                seen[alias].append((row["state"], row["name"]))
    bad = [(alias, hits) for alias, hits in seen.items() if len(hits) != 1]
    assert not bad, "alias duplication detected:\n" + "\n".join(
        f"  {alias!r} -> {hits}" for alias, hits in bad
    )


def test_karnataka_renames_target_correct_lgd_rows() -> None:
    """The 12 Karnataka Bengaluru/Belagavi/etc renames bind to the right spine rows."""
    rows = _load_pc_2008_rows()
    by_key = {(r["state"], r["name"]): r for r in rows}
    karnataka_cases = [
        ("Bengaluru North", "Bangalore North"),
        ("Bengaluru Rural", "Bangalore Rural"),
        ("Bengaluru South", "Bangalore South"),
        ("Bengaluru Central", "Bangalore central"),
        ("Belagavi", "Belgaum"),
        ("Ballari", "Bellary"),
        ("Vijayapura", "Bijapur"),
        ("Kalaburagi", "Gulbarga"),
        ("Mysuru", "Mysore"),
        ("Shivamogga", "Shimoga"),
        ("Tumakuru", "Tumkur"),
        ("Udupi Chikkamagaluru", "Udupi Chikmagalur"),
    ]
    for canonical, eci_variant in karnataka_cases:
        row = by_key.get(("karnataka", canonical))
        assert row is not None, f"spine row missing for karnataka/{canonical!r}"
        aliases = [a.strip() for a in (row.get("aliases") or "").split("|") if a.strip()]
        assert eci_variant in aliases, (
            f"karnataka/{canonical!r} aliases={aliases!r} missing {eci_variant!r}"
        )


def test_canonical_name_column_unchanged_for_aliased_rows() -> None:
    """LGD-canonical name (per Hans verdict Q2) MUST stay in the ``name`` column."""
    rows = _load_pc_2008_rows()
    by_key = {(r["state"], r["name"]): r for r in rows}
    for (state, name), _alias in BOUND_ALIASES.items():
        row = by_key.get((state, name))
        assert row is not None, f"spine row missing for ({state}, {name!r})"
        assert row["name"] == name, (
            f"canonical name drift at ({state}, expected {name!r}, got {row['name']!r})"
        )


def test_aliases_stored_verbatim_case_and_punctuation_preserved() -> None:
    """Hans verdict Q5: aliases are stored verbatim (preserve case + punctuation)."""
    rows = _load_pc_2008_rows()
    by_key = {(r["state"], r["name"]): r for r in rows}
    # Sample 5 entries that exercise different drift axes
    case_only = ("chhattisgarh", "Janjgir Champa", "JANJGIR-CHAMPA")
    jk_caps = ("jammu-and-kashmir", "Anantnag", "ANANTNAG-RAJOURI")
    karnataka_lower = ("karnataka", "Bengaluru Central", "Bangalore central")  # ECI 'central' lower-case
    maharashtra_space = ("maharashtra", "Ratnagiri - Sindhudurg", "Ratnagiri- Sindhudurg")
    assam_content = ("assam", "Autonomous District", "Diphu")
    for state, name, verbatim_alias in [
        case_only, jk_caps, karnataka_lower, maharashtra_space, assam_content
    ]:
        row = by_key.get((state, name))
        assert row is not None
        cell = (row.get("aliases") or "").strip()
        aliases = [a.strip() for a in cell.split("|") if a.strip()]
        assert verbatim_alias in aliases, (
            f"verbatim alias {verbatim_alias!r} missing from {state}/{name!r}; got {aliases!r}"
        )


def test_pc_lookup_walks_aliases_so_eci_names_resolve() -> None:
    """``_build_pc_lookup`` must register every alias as a binding key.

    The G16 ingest re-run after this PR drops unbound from 50 -> 14 because
    every BOUND ECI variant now resolves through the alias-walk in
    ``_build_pc_lookup``. This test pins the invariant.
    """
    lookup = _build_pc_lookup(_electoral_csv_path())
    missing = []
    for (state, canonical_name), eci_alias in BOUND_ALIASES.items():
        # Both the canonical and the ECI variant should resolve to the same row
        canonical_key = (state, _normalise_pc_name(canonical_name))
        alias_key = (state, _normalise_pc_name(eci_alias))
        bound_canonical = lookup.get(canonical_key)
        bound_alias = lookup.get(alias_key)
        if bound_canonical is None:
            missing.append(("canonical", state, canonical_name, canonical_key))
        if bound_alias is None:
            missing.append(("alias", state, eci_alias, alias_key))
        if bound_canonical and bound_alias and bound_canonical != bound_alias:
            missing.append((
                "mismatch", state, eci_alias,
                f"canonical={bound_canonical} alias={bound_alias}",
            ))
    assert not missing, "lookup-walk missing or mismatched:\n" + "\n".join(
        f"  {m}" for m in missing
    )


def test_backfill_script_is_idempotent(tmp_path: Path) -> None:
    """Running tools/_alias_backfill.tmp.py twice produces byte-identical electoral.csv.

    The script is the receipt for the alias backfill (kept post-merge); this
    test pins the idempotency contract so a future regen does not corrupt the
    aliases column.
    """
    here = Path(__file__).resolve()
    repo_root = next(p for p in here.parents if (p / "tools" / "_alias_backfill.tmp.py").exists())
    script = repo_root / "tools" / "_alias_backfill.tmp.py"
    csv_path = repo_root / "datasets" / "data" / "entities" / "electoral.csv"

    # Capture current bytes (the live file, with aliases already applied)
    before = csv_path.read_bytes()

    # Run the script (no-op since aliases are already present)
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"backfill script failed: {result.stderr}\nstdout: {result.stdout}"
    )
    after = csv_path.read_bytes()
    assert before == after, (
        "backfill script is NOT idempotent: byte-level diff detected on re-run"
    )
    # Sanity: the script reports zero updates on the idempotent re-run
    assert "0 alias cells updated this run" in result.stdout, (
        f"expected '0 alias cells updated' on idempotent re-run, got:\n{result.stdout}"
    )
