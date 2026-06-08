"""G1 (2026-06-08) veracity invariants for the TCPD-dialect aliases backfill.

The Phase G1 work adds an ``aliases`` column to
``datasets/data/entities/parties.csv`` that the elections writer expands
into its ``party_lookup`` (see
:func:`yen_gov.canonical.reingest.assembly_results.party_lookup_from_parties_csv`).
The previous cross-format parity gate (long-format CSV vs the retired
Parquet) is gone WITH the Parquet, so the veracity story for this PR
relies on three new in-format invariants:

1. Alias expansion: every UPPERCASE alias on a parties.csv row becomes a
   ``upper(alias) -> party_id`` entry in the lookup, alongside the existing
   ``upper(short) -> party_id`` entry. The TCPD dialects (CPM, ADMK, AAAP,
   TRS, ...) resolve to the SAME canonical id as the matching short.
2. Collision detection: if two distinct keys (short or alias) on disk would
   map to two different ``party_id`` values, the writer fails loud rather
   than silently picking one (Holy Law #5 + CLAUDE.md anti-patterns).
3. No-overwrite / PK-set / idempotent byte-stability across a re-emit cycle.
   Every pre-existing non-NULL ``party_id`` on the on-disk candidacies MUST
   survive the re-emit unchanged; the PK set MUST stay invariant; and two
   sequential emits MUST produce byte-identical output (deterministic
   writer).

Tests 1 + 2 stage tiny ``tmp_path`` fixtures (CLAUDE.md anti-pattern: no
real-corpus walk from pytest). Test 3 reads the on-disk TN 2021 candidacies
+ the local TCPD raw + re-emits to ``tmp_path``; it skips cleanly if either
prerequisite is absent (so CI on a slim checkout passes without it).
"""

from __future__ import annotations

import csv as _csv
from pathlib import Path

import pytest

from yen_gov.canonical.reingest import assembly_results


# --- Phase C.1: alias expansion --------------------------------------------


def test_party_lookup_aliases_expand_to_same_party_id(tmp_path: Path) -> None:
    """A non-empty pipe-delimited ``aliases`` value yields one extra
    ``upper(alias) -> party_id`` entry per alias, alongside the existing
    ``upper(short) -> party_id`` entry. UPPER-cased and stripped.
    """
    parties = tmp_path / "parties.csv"
    parties.write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia,aliases\n"
        "parties.IN.CPIM,CPI(M),Communist Party of India (Marxist),,,,,"
        "CPM|CPIM|CPI(MARXIST)\n"
        "parties.IN.AIADMK,AIADMK,All India Anna DMK,,,,,ADMK\n"
        "parties.IN.AAP,AAP,Aam Aadmi Party,,,,,AAAP\n"
        "parties.IN.BJP,BJP,Bharatiya Janata Party,,,,,\n",
        encoding="utf-8",
    )

    lookup = assembly_results.party_lookup_from_parties_csv(parties)

    # short column still resolves
    assert lookup["CPI(M)"] == "parties.IN.CPIM"
    assert lookup["AIADMK"] == "parties.IN.AIADMK"
    assert lookup["AAP"] == "parties.IN.AAP"
    assert lookup["BJP"] == "parties.IN.BJP"

    # every alias resolves to the SAME id as the short
    assert lookup["CPM"] == "parties.IN.CPIM"
    assert lookup["CPIM"] == "parties.IN.CPIM"
    assert lookup["CPI(MARXIST)"] == "parties.IN.CPIM"
    assert lookup["ADMK"] == "parties.IN.AIADMK"
    assert lookup["AAAP"] == "parties.IN.AAP"

    # empty aliases adds nothing (BJP only has its short key)
    assert "" not in lookup


def test_party_lookup_alias_keys_are_uppercased_and_trimmed(tmp_path: Path) -> None:
    """Aliases on disk may be authored with mixed case + surrounding
    whitespace; the lookup keys are always upper-cased + stripped.
    """
    parties = tmp_path / "parties.csv"
    parties.write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia,aliases\n"
        "parties.IN.JDS,JD(S),Janata Dal (Secular),,,,,jds | JANTA Dal (Secular)\n",
        encoding="utf-8",
    )

    lookup = assembly_results.party_lookup_from_parties_csv(parties)
    assert lookup["JDS"] == "parties.IN.JDS"
    assert lookup["JANTA DAL (SECULAR)"] == "parties.IN.JDS"
    # the mixed-case original is not present (only the upper form)
    assert "jds" not in lookup
    assert "JANTA Dal (Secular)" not in lookup


def test_party_lookup_backcompat_no_aliases_column(tmp_path: Path) -> None:
    """Fixtures authored before the ``aliases`` column (the existing test
    fleet) must still build a working short-only lookup.
    """
    parties = tmp_path / "parties.csv"
    parties.write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia\n"
        "parties.IN.DMK,DMK,Dravida Munnetra Kazhagam,,,,\n"
        "parties.IN.BJP,BJP,Bharatiya Janata Party,,,,\n",
        encoding="utf-8",
    )

    lookup = assembly_results.party_lookup_from_parties_csv(parties)
    assert lookup == {"DMK": "parties.IN.DMK", "BJP": "parties.IN.BJP"}


# --- Phase C.2: collision detection -----------------------------------------


def test_party_lookup_collision_short_vs_short_fails_loud(tmp_path: Path) -> None:
    """Two rows whose ``short`` upper-cases to the same key but point to
    different ``party_id`` values must raise ``ValueError`` (Holy Law #5).
    """
    parties = tmp_path / "parties.csv"
    parties.write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia,aliases\n"
        "parties.IN.AAA,DUPE,Party A,,,,,\n"
        "parties.IN.BBB,dupe,Party B,,,,,\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"party_lookup collision: key 'DUPE'"):
        assembly_results.party_lookup_from_parties_csv(parties)


def test_party_lookup_collision_alias_vs_short_fails_loud(tmp_path: Path) -> None:
    """An alias on one row that upper-cases to the same key as another row's
    short (or alias) but points to a different ``party_id`` is rejected.
    """
    parties = tmp_path / "parties.csv"
    parties.write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia,aliases\n"
        "parties.IN.REAL,REAL,Real Party,,,,,\n"
        "parties.IN.OTHER,OTHER,Other Party,,,,,REAL\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"party_lookup collision: key 'REAL'"):
        assembly_results.party_lookup_from_parties_csv(parties)


def test_party_lookup_idempotent_same_short_same_id_is_fine(tmp_path: Path) -> None:
    """Two rows that produce the SAME key -> SAME party_id mapping must NOT
    raise (only mismatched targets are the bug). Authoring an alias that
    equals the canonical short is harmless duplication.
    """
    parties = tmp_path / "parties.csv"
    parties.write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia,aliases\n"
        "parties.IN.CPIM,CPI(M),CPI Marxist,,,,,CPI(M)\n",
        encoding="utf-8",
    )

    lookup = assembly_results.party_lookup_from_parties_csv(parties)
    assert lookup == {"CPI(M)": "parties.IN.CPIM"}


# --- Phase C.3: no-overwrite + PK-set invariance + byte-stability ---------


def test_party_id_backfill_no_overwrite_across_re_emit(tmp_path: Path) -> None:
    """Central veracity gate (G1, 2026-06-08).

    Three assertions across a re-emit cycle:
    (a) NO-OVERWRITE: every pre-emit non-NULL party_id MUST equal the
        post-emit party_id at the same PK. NULL -> resolved is allowed;
        resolved -> different is forbidden.
    (b) PK-SET INVARIANT: the set of (constituency_no, candidate_name)
        in the re-emit equals the set in the pre-emit. No rows lost or
        added.
    (c) IDEMPOTENT BYTE-STABILITY: emit twice to two different tmp_paths;
        bytes are identical. Writer is deterministic.

    Reads on-disk TN 2021 assembly candidacies + the local TCPD source.
    Skips cleanly if either is absent.
    """
    from yen_gov.canonical.citation import derive_source_id
    from yen_gov.canonical.reingest.assembly_results import emit_state_assembly

    repo_root = Path(__file__).resolve().parents[2]
    ae_csv = repo_root / "datasets" / "ephemeral" / "All_States_AE.csv"
    electoral_csv = repo_root / "datasets" / "data" / "entities" / "electoral.csv"
    parties_csv = repo_root / "datasets" / "data" / "entities" / "parties.csv"
    on_disk_candidacies = (
        repo_root / "datasets" / "elections" / "assembly"
        / "state=tamil-nadu" / "election=2021" / "candidacies.csv"
    )
    if not ae_csv.exists() or not on_disk_candidacies.exists():
        pytest.skip("requires TCPD raw + on-disk TN 2021 candidacies")

    # Read pre-emit PKs + party_ids
    with on_disk_candidacies.open(encoding="utf-8", newline="") as fh:
        pre_rows = list(_csv.DictReader(fh))
    pre_by_pk: dict[tuple[int, str], str | None] = {}
    for r in pre_rows:
        key = (int(r["constituency_no"]), r["candidate_name"])
        pre_by_pk[key] = r["party_id"] or None

    # Re-emit to tmp_path using the production source_id (byte parity)
    source_id = derive_source_id(
        "Trivedi Centre for Political Data, Ashoka University",
        "Indian Assembly Elections - Constituency-wise candidate results "
        "(TCPD compilation of ECI returns)",
        "2026-06-05",
    )
    out_a = tmp_path / "a"
    out_a.mkdir()
    emit_state_assembly(
        ae_csv=ae_csv,
        electoral_csv=electoral_csv,
        out_root=out_a,
        state_name_tcpd="Tamil_Nadu",
        state_slug="tamil-nadu",
        source_id=source_id,
        parties_csv=parties_csv,
    )
    re_emit_candidacies = (
        out_a / "datasets" / "elections" / "assembly"
        / "state=tamil-nadu" / "election=2021" / "candidacies.csv"
    )
    with re_emit_candidacies.open(encoding="utf-8", newline="") as fh:
        post_rows = list(_csv.DictReader(fh))
    post_by_pk: dict[tuple[int, str], str | None] = {}
    for r in post_rows:
        key = (int(r["constituency_no"]), r["candidate_name"])
        post_by_pk[key] = r["party_id"] or None

    # (a) no-overwrite
    overwrites: list[str] = []
    for key, pre_pid in pre_by_pk.items():
        if pre_pid is None:
            continue
        post_pid = post_by_pk.get(key)
        if post_pid is None or post_pid == pre_pid:
            continue
        overwrites.append(f"{key}: {pre_pid!r} -> {post_pid!r}")
    assert not overwrites, (
        "party_id overwrite detected across re-emit:\n  "
        + "\n  ".join(overwrites[:10])
    )

    # (b) PK-set invariant
    assert set(pre_by_pk) == set(post_by_pk), (
        f"PK-set changed: pre={len(pre_by_pk)} post={len(post_by_pk)} "
        f"only_pre={len(set(pre_by_pk) - set(post_by_pk))} "
        f"only_post={len(set(post_by_pk) - set(pre_by_pk))}"
    )

    # (c) idempotent byte-stability: a second emit to fresh tmp_path
    out_b = tmp_path / "b"
    out_b.mkdir()
    emit_state_assembly(
        ae_csv=ae_csv,
        electoral_csv=electoral_csv,
        out_root=out_b,
        state_name_tcpd="Tamil_Nadu",
        state_slug="tamil-nadu",
        source_id=source_id,
        parties_csv=parties_csv,
    )
    re_emit_b = (
        out_b / "datasets" / "elections" / "assembly"
        / "state=tamil-nadu" / "election=2021" / "candidacies.csv"
    )
    assert re_emit_candidacies.read_bytes() == re_emit_b.read_bytes(), (
        "writer is non-deterministic: two emits produced different bytes"
    )
