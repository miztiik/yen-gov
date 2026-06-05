"""Golden-file + determinism tests for ``tools/lgd/parse_lgd_export.py`` (B2b.5.0a).

No mocks (Holy Law #7): the parser runs against trimmed-REAL LGD source fixtures
(byte-copied from the 2026-06-05 ephemeral exports) under
``backend/tests/fixtures/lgd/sources/`` and is asserted against committed golden
snapshot CSVs under ``backend/tests/fixtures/lgd/expected/``.

Adversarial fixture rows lock the three discipline points the parser must keep
(plan section 0c.8):

- a leading-zero district census code (``"000"``, ``"547"``) -> the no-integer-
  coercion rule for register codes;
- a non-ASCII (Devanagari) state local name -> UTF-8 round-trip;
- an AC spanning two districts (AC 3167 -> districts 747 + 510) -> the 1:many
  membership fan-out with a plurality ``is_primary``.

Per CLAUDE.md section 4, tests MAY import from ``tools/`` (one-way dependency).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_LGD = REPO_ROOT / "tools" / "lgd"
if str(_TOOLS_LGD) not in sys.path:
    sys.path.insert(0, str(_TOOLS_LGD))

import parse_lgd_export as P  # noqa: E402  (after sys.path manipulation)

FIXTURES = Path(__file__).parent / "fixtures" / "lgd"
SOURCES = FIXTURES / "sources"
EXPECTED = FIXTURES / "expected"

OUTPUT_FILES = (
    "states.csv",
    "districts.csv",
    "subdistricts.csv",
    "constituencies.csv",
    "constituency_district_membership.csv",
)


def _fixture_sources() -> dict[str, object]:
    return {
        "states": SOURCES / "All_Stateof_India_FIXTURE.csv",
        "districts": SOURCES / "All_Districtof_India_FIXTURE.csv",
        "subdistricts": SOURCES / "All_Sub_Districtof_India_FIXTURE.csv",
        "pri": [SOURCES / "Parliment_PRI_andhra_pradesh_FIXTURE.xlsx"],
    }


def _build(tmp_path: Path) -> Path:
    out = tmp_path / "lgd"
    P.build_snapshot(SOURCES, out, sources=_fixture_sources())
    return out


@pytest.mark.parametrize("name", OUTPUT_FILES)
def test_parser_matches_golden(tmp_path, name):
    """Each emitted snapshot CSV byte-equals its committed golden."""
    out = _build(tmp_path)
    got = (out / name).read_bytes()
    expected = (EXPECTED / name).read_bytes()
    assert got == expected, (
        f"{name} diverged from golden\n--- got ---\n"
        f"{got.decode('utf-8')}\n--- expected ---\n{expected.decode('utf-8')}"
    )


def test_outputs_are_lf_only_no_bom_trailing_newline(tmp_path):
    """Serialisation matches the canonical CSV discipline (LF, no BOM, trailing NL)."""
    out = _build(tmp_path)
    for name in OUTPUT_FILES:
        raw = (out / name).read_bytes()
        assert b"\r" not in raw, f"{name} must be LF-only"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{name} must have no BOM"
        assert raw.endswith(b"\n"), f"{name} must end with a trailing newline"


def test_rerun_is_byte_identical(tmp_path):
    """Two runs over the same inputs produce identical bytes (deterministic-re-run gate)."""
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    P.build_snapshot(SOURCES, out_a, sources=_fixture_sources())
    P.build_snapshot(SOURCES, out_b, sources=_fixture_sources())
    for name in OUTPUT_FILES:
        assert (out_a / name).read_bytes() == (out_b / name).read_bytes(), name


def test_receipt_records_sha256_and_counts(tmp_path):
    """The parse-receipt carries a sha256 per source + the output row counts (html-parse-receipt gate)."""
    out = _build(tmp_path)
    receipt = json.loads((out / "parse-receipt.json").read_text(encoding="utf-8"))
    assert receipt["snapshot_vintage"] == P.SNAPSHOT_VINTAGE
    # Every source carries a 64-hex-char sha256.
    all_sources = receipt["sources"] + receipt["pri_sources"]
    assert all_sources, "receipt must list sources"
    for s in all_sources:
        assert len(s["sha256"]) == 64
        assert all(c in "0123456789abcdef" for c in s["sha256"])
    out_rows = {o["file"]: o["rows"] for o in receipt["outputs"]}
    assert out_rows["constituencies.csv"] == 3  # 2 AC + 1 PC
    assert out_rows["constituency_district_membership.csv"] == 3


def test_leading_zero_census_codes_preserved(tmp_path):
    """District census code "000"/"547" survive (no integer coercion of register codes)."""
    out = _build(tmp_path)
    text = (out / "districts.csv").read_text(encoding="utf-8")
    assert "28,Andhra Pradesh,747,Dr. B.R. Ambedkar Konaseema,000,000" in text
    assert "28,Andhra Pradesh,510,Krishna,16,547" in text


def test_non_ascii_state_name_round_trips(tmp_path):
    """A Devanagari local name survives UTF-8 round-trip."""
    out = _build(tmp_path)
    text = (out / "states.csv").read_text(encoding="utf-8")
    assert "\u091b\u0924\u094d\u0924\u0940\u0938\u0917\u0922\u093c" in text  # chhattisgarh Devanagari


def test_multi_district_ac_is_primary_by_plurality(tmp_path):
    """AC 3167 spans districts 747 (2 villages) + 510 (1) -> 747 is_primary, 510 not."""
    out = _build(tmp_path)
    rows = (out / "constituency_district_membership.csv").read_text(encoding="utf-8").splitlines()
    by_key = {}
    for line in rows[1:]:
        state, ac, dist, vcount, prim = line.split(",")
        by_key[(ac, dist)] = (vcount, prim)
    assert by_key[("3167", "747")] == ("2", "true")
    assert by_key[("3167", "510")] == ("1", "false")
    # The wholly-inside AC is its own primary.
    assert by_key[("3166", "747")] == ("2", "true")


def test_constituencies_carry_eci_code_and_parent_pc(tmp_path):
    """ACs fold their ECI ballot serial + parent PC; PC rows have empty parent."""
    out = _build(tmp_path)
    rows = (out / "constituencies.csv").read_text(encoding="utf-8").splitlines()
    by_kind_code = {}
    for line in rows[1:]:
        state, kind, lgd, eci, name, parent = line.split(",")
        by_kind_code[(kind, lgd)] = (eci, name, parent)
    assert by_kind_code[("ac", "3166")] == ("163", "Amalapuram", "411")
    assert by_kind_code[("ac", "3167")] == ("165", "Gannavaram", "411")
    assert by_kind_code[("pc", "411")] == ("9", "Amalapuram", "")


def test_ut_without_districts_resolves_via_title(tmp_path):
    """Chandigarh (UT, no district rows in PRI) still resolves to its state via title.

    The fixture PRI is single-state AP; this asserts the title resolver helper
    handles the no-district-code UT case the production run hit (Chandigarh,
    Lakshadweep) without a regression to the district-join-only path.
    """
    state_name_to_code = {"CHANDIGARH": "4", "ANDHRA PRADESH": "28"}
    assert P._state_from_title(
        "State Of Chandigarh Parliament Constituency and Assembly Constituency "
        "along with coverage details PRI",
        state_name_to_code,
    ) == "4"
    assert P._state_from_title(
        "State Of The Dadra And Nagar Haveli And Daman And Diu Parliament ...",
        {"DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "38"},
    ) == "38"
