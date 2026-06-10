"""Reservation lookups for electoral.csv (AC GEN/SC/ST per the 2008 Delimitation Order).

This module is the single source of truth for joining the various external
reservation sources to ``datasets/data/entities/electoral.csv`` so the
``electoral_csv_from_snapshot`` emitter can populate the ``reservation``
column on AC and PC rows.

Sources (all OFF-CORPUS by default; the loaders SKIP cleanly when the
ephemeral CSV is not on disk, so existing tests + CI that do not stage the
ephemeral inputs still pass):

- **boundaries_sot** (committed): 31 hand-curated SoT files at
  ``datasets/data/entities/boundaries_sot/<S##>/constituencies.json``. Carries
  ``reservation`` in ``{GEN, SC, ST}`` per AC. Primary AC source.
- **TCPD All_States_AE.csv** (ephemeral): PC-level ``Constituency_Type``
  column. Fallback AC source for historical / gap rows not in boundaries_sot
  (e.g. pre-2014 united AP eci_no 176..294 + Arunachal AC gaps).
- **ECI Statement 33 (2024 + 2019 LS)** (ephemeral): per-candidate ``Category``
  column. Derived to PC reservation via the all-same-category rule
  (PC reservation = SC if every candidate is SC; ST if every candidate is ST;
  GEN otherwise). 2024 is primary, 2019 is fallback.
- **TCPD All_States_GE.csv** (ephemeral): PC-level ``Constituency_Type``
  column. Most-reliable PC source (PC-level not candidate-level) - this is
  the PRIMARY PC source, with ECI Statement 33 derivation as a CROSS-CHECK.

Per CLAUDE.md section 10, none of these are auto-corrected: the load_*
helpers return what each source asserts; the emit_*_parity_verdict helpers
surface disagreements at ``datasets/ephemeral/reservation-parity/<sha>/`` for
operator review.

Path keys:

- AC lookup key: ``(state_code, eci_no_int)`` where ``state_code`` is the ECI
  ``S##``/``U##`` 3-char code (NOT the LGD slug). The lookup is built per ECI
  state code and joined to electoral.csv via the LGD-slug-to-ECI-state-code
  table below.
- PC lookup key: ``(state_slug, pc_name_normalized)`` where ``state_slug`` is
  the LGD slug used in electoral.csv (e.g. ``tamil-nadu``) and
  ``pc_name_normalized`` is whitespace-collapsed lowercase of the PC name.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

Reservation = Literal["GEN", "SC", "ST"]


# ---------------------------------------------------------------------------
# Slug <-> ECI state code maps (electoral.csv uses LGD slugs; boundaries_sot
# directory names + ECI Stmt 33 join keys use ECI ``S##``/``U##`` codes).
# Hand-authored: a 36-entry table is cheaper than threading the full taxonomy
# loader into the emitter. Parity with the taxonomy is enforced by the
# Tier-A test suite (``test_electoral_reservation_populated``).
# ---------------------------------------------------------------------------

# slug -> ECI state code. The 36 rows cover all current 28 states + 8 UTs.
# NOTE: ``andaman-and-nicobar-islands`` differs from the ``andaman-and-nicobar``
# spelling in ``backend/yen_gov/canonical/historical_state_slug.py``; electoral.csv
# uses the LGD ``-islands`` suffix, so we honour the LGD slug here.
SLUG_TO_ECI_STATE_CODE: dict[str, str] = {
    "andhra-pradesh": "S01",
    "arunachal-pradesh": "S02",
    "assam": "S03",
    "bihar": "S04",
    "goa": "S05",
    "gujarat": "S06",
    "haryana": "S07",
    "himachal-pradesh": "S08",
    "karnataka": "S10",
    "kerala": "S11",
    "madhya-pradesh": "S12",
    "maharashtra": "S13",
    "manipur": "S14",
    "meghalaya": "S15",
    "mizoram": "S16",
    "nagaland": "S17",
    "odisha": "S18",
    "punjab": "S19",
    "rajasthan": "S20",
    "sikkim": "S21",
    "tamil-nadu": "S22",
    "tripura": "S23",
    "uttar-pradesh": "S24",
    "west-bengal": "S25",
    "chhattisgarh": "S26",
    "jharkhand": "S27",
    "uttarakhand": "S28",
    "telangana": "S29",
    # UTs (incl. the 3 with legislative assemblies: U05 Delhi, U07 Puducherry,
    # U08 J&K post-2019).
    "andaman-and-nicobar-islands": "U01",
    "chandigarh": "U02",
    "dadra-and-nagar-haveli-and-daman-and-diu": "U03",
    "lakshadweep": "U04",
    "delhi": "U05",
    "puducherry": "U07",
    "jammu-and-kashmir": "U08",
    "ladakh": "U09",
}

# TCPD state name -> LGD slug. TCPD uses underscore-separated names + a couple
# of historical forms (separate Dadra & Daman pre-2020 + Jammu_&_Kashmir pre-2019).
TCPD_STATE_NAME_TO_SLUG: dict[str, str] = {
    "Andaman_&_Nicobar_Islands": "andaman-and-nicobar-islands",
    "Andhra_Pradesh": "andhra-pradesh",
    "Arunachal_Pradesh": "arunachal-pradesh",
    "Assam": "assam",
    "Bihar": "bihar",
    "Chandigarh": "chandigarh",
    "Chhattisgarh": "chhattisgarh",
    "Dadra & Nagar Haveli And Daman & Diu": "dadra-and-nagar-haveli-and-daman-and-diu",
    "Dadra_&_Nagar_Haveli": "dadra-and-nagar-haveli-and-daman-and-diu",
    "Daman_&_Diu": "dadra-and-nagar-haveli-and-daman-and-diu",
    "Delhi": "delhi",
    "Goa": "goa",
    "Gujarat": "gujarat",
    "Haryana": "haryana",
    "Himachal_Pradesh": "himachal-pradesh",
    "Jammu_&_Kashmir": "jammu-and-kashmir",
    "Jharkhand": "jharkhand",
    "Karnataka": "karnataka",
    "Kerala": "kerala",
    "Ladakh": "ladakh",
    "Lakshadweep": "lakshadweep",
    "Madhya_Pradesh": "madhya-pradesh",
    "Maharashtra": "maharashtra",
    "Manipur": "manipur",
    "Meghalaya": "meghalaya",
    "Mizoram": "mizoram",
    "Nagaland": "nagaland",
    "Odisha": "odisha",
    "Puducherry": "puducherry",
    "Punjab": "punjab",
    "Rajasthan": "rajasthan",
    "Sikkim": "sikkim",
    "Tamil_Nadu": "tamil-nadu",
    "Telangana": "telangana",
    "Tripura": "tripura",
    "Uttar_Pradesh": "uttar-pradesh",
    "Uttarakhand": "uttarakhand",
    "West_Bengal": "west-bengal",
}

# ECI Statement 33 state name -> LGD slug (2024 + 2019 spellings).
ECI_STMT33_STATE_NAME_TO_SLUG: dict[str, str] = {
    "Andaman & Nicobar Islands": "andaman-and-nicobar-islands",
    "Andhra Pradesh": "andhra-pradesh",
    "Arunachal Pradesh": "arunachal-pradesh",
    "Assam": "assam",
    "Bihar": "bihar",
    "Chandigarh": "chandigarh",
    "Chhattisgarh": "chhattisgarh",
    "Dadra & Nagar Haveli and Daman & Diu": "dadra-and-nagar-haveli-and-daman-and-diu",
    "Dadra & Nagar Haveli": "dadra-and-nagar-haveli-and-daman-and-diu",  # 2019 split
    "Daman & Diu": "dadra-and-nagar-haveli-and-daman-and-diu",  # 2019 split
    "Goa": "goa",
    "Gujarat": "gujarat",
    "Haryana": "haryana",
    "Himachal Pradesh": "himachal-pradesh",
    "Jammu and Kashmir": "jammu-and-kashmir",
    "Jammu & Kashmir": "jammu-and-kashmir",
    "Jharkhand": "jharkhand",
    "Karnataka": "karnataka",
    "Kerala": "kerala",
    "Ladakh": "ladakh",
    "Lakshadweep": "lakshadweep",
    "Madhya Pradesh": "madhya-pradesh",
    "Maharashtra": "maharashtra",
    "Manipur": "manipur",
    "Meghalaya": "meghalaya",
    "Mizoram": "mizoram",
    "Nagaland": "nagaland",
    "NCT OF Delhi": "delhi",
    "Nct Of Delhi": "delhi",
    "Delhi": "delhi",
    "Odisha": "odisha",
    "Orissa": "odisha",  # legacy spelling
    "Puducherry": "puducherry",
    "Pondicherry": "puducherry",  # legacy spelling
    "Punjab": "punjab",
    "Rajasthan": "rajasthan",
    "Sikkim": "sikkim",
    "Tamil Nadu": "tamil-nadu",
    "Telangana": "telangana",
    "Tripura": "tripura",
    "Uttar Pradesh": "uttar-pradesh",
    "Uttarakhand": "uttarakhand",
    "West Bengal": "west-bengal",
}

# ECI Statement 33 maps "GENERAL" -> "GEN"; other categories (SC, ST, BL) are
# treated per ``derive_pc_reservation_from_candidate_cats`` below.
_ECI_CAT_TO_RESERVATION: dict[str, str] = {
    "GENERAL": "GEN",
    "GEN": "GEN",
    "SC": "SC",
    "ST": "ST",
}

_WS_RE = re.compile(r"[\s\-]+")  # collapse whitespace AND hyphens/dashes


def normalize_pc_name(name: str) -> str:
    """Normalise a PC name for cross-source join.

    Lowercase + strip + collapse internal whitespace AND hyphens. The hyphen
    collapse is needed because the LGD register uses "Mumbai North-Central"
    while TCPD/ECI use "Mumbai North Central"; "Janjgir Champa" vs
    "Janjgir-Champa"; "Bardhaman - Durgapur" vs "Bardhaman Durgapur" etc.

    Does NOT normalise ``&`` vs ``and`` (both spellings co-exist with
    matching reservations on either side; the few outliers
    (e.g. "Dadra & Nagar Haveli" vs "Dadar & Nagar Haveli") are spelling
    aliases handled by ``PC_NAME_ALIASES`` below).
    """
    return _WS_RE.sub(" ", name.strip().lower())


# Hand-curated alias map for PC name spellings that diverge across sources
# (modern Karnataka 2014 renames + a handful of state-name spelling drifts).
# Maps the electoral.csv (LGD-register) spelling -> the TCPD/ECI spelling
# that the lookup is keyed on. NORMALIZED on both sides via
# ``normalize_pc_name``. Hand-authored; CLAUDE.md Holy Law #6 does NOT
# forbid hand-curation - it forbids hardcoded TUNABLES. This is a name-
# crosswalk, not a tunable knob.
PC_NAME_ALIASES: dict[tuple[str, str], str] = {
    # Karnataka 2014 official renames (LGD updated; older publisher CSVs
    # carry the pre-2014 names).
    ("karnataka", "bengaluru central"): "bangalore central",
    ("karnataka", "bengaluru north"): "bangalore north",
    ("karnataka", "bengaluru rural"): "bangalore rural",
    ("karnataka", "bengaluru south"): "bangalore south",
    ("karnataka", "belagavi"): "belgaum",
    ("karnataka", "ballari"): "bellary",
    ("karnataka", "vijayapura"): "bijapur",
    ("karnataka", "kalaburagi"): "gulbarga",
    ("karnataka", "mysuru"): "mysore",
    ("karnataka", "shivamogga"): "shimoga",
    ("karnataka", "tumakuru"): "tumkur",
    ("karnataka", "udupi chikkamagaluru"): "udupi chikmagalur",
    # DNH+DD spelling drift.
    ("dadra-and-nagar-haveli-and-daman-and-diu", "dadra & nagar haveli"): "dadar & nagar haveli",
    # Telangana Mahabubnagar - LGD register spells "Mahabubnagar", ECI Stmt 33
    # spells "Mahbubnagar" (no second "a"). The 2008 Delim Order has this PC
    # as GEN.
    ("telangana", "mahabubnagar"): "mahbubnagar",
    # (handled via __init__-time prefill in build_pc_reservation_lookup.)
}


def _normalize_pc_with_alias(state_slug: str, pc_name: str) -> str:
    """Normalise + apply alias map.

    Useful both at lookup-build time (preserves the publisher key shape) and
    at row-lookup time (electoral.csv side wants its own name resolved into
    the publisher-spelling lookup key).
    """
    base = normalize_pc_name(pc_name)
    aliased = PC_NAME_ALIASES.get((state_slug, base))
    return aliased if aliased is not None else base


# ---------------------------------------------------------------------------
# boundaries_sot loader (committed; the primary AC source)
# ---------------------------------------------------------------------------


def load_ac_reservations_from_boundaries_sot(
    boundaries_sot_dir: Path,
) -> dict[tuple[str, int], Reservation]:
    """Read every ``<state_code>/constituencies.json`` under ``boundaries_sot_dir``.

    Returns ``(state_code_S##, eci_no_int) -> reservation``.
    Raises ``ValueError`` on any per-row reservation outside ``{GEN, SC, ST}``.
    Skips silently when ``boundaries_sot_dir`` does not exist.
    """
    out: dict[tuple[str, int], Reservation] = {}
    if not boundaries_sot_dir.exists():
        return out
    for state_dir in sorted(boundaries_sot_dir.iterdir()):
        if not state_dir.is_dir():
            continue
        cj = state_dir / "constituencies.json"
        if not cj.exists():
            continue
        payload = json.loads(cj.read_text(encoding="utf-8"))
        state_code = payload.get("state")
        body = payload.get("body")
        if body != "AC":
            continue
        for c in payload.get("constituencies", []):
            res = c.get("reservation")
            if res not in ("GEN", "SC", "ST"):
                raise ValueError(
                    f"{cj}: constituency eci_no={c.get('eci_no')!r} has "
                    f"reservation={res!r} not in {{GEN, SC, ST}}"
                )
            eci_no = int(c["eci_no"])
            out[(state_code, eci_no)] = res
    return out


# ---------------------------------------------------------------------------
# TCPD AE loader (fallback for AC gaps in boundaries_sot)
# ---------------------------------------------------------------------------


def load_ac_reservations_from_tcpd_ae(
    tcpd_ae_csv: Path,
    *,
    min_year: int = 2009,
) -> dict[tuple[str, int], Reservation]:
    """Read ``All_States_AE.csv`` and return ``(state_code_S##, eci_no) -> reservation``.

    Keeps the most-recent year per (state, AC) tuple. ``Constituency_Type``
    is PC-level (constant across all candidate rows of a given (state, AC, year)).
    Filters to ``Year >= min_year`` (default 2009) to stay within the in-force
    2008 delimitation cycle. State name maps via ``TCPD_STATE_NAME_TO_SLUG``
    -> ``SLUG_TO_ECI_STATE_CODE``. Skips silently when ``tcpd_ae_csv`` is
    missing.

    NORMALISATION: ``Constituency_Type`` ``"GEN"`` and ``"GENERAL"`` collapse
    to ``"GEN"`` (the canonical electoral.csv enum).
    """
    if not tcpd_ae_csv.exists():
        return {}
    latest: dict[tuple[str, int], tuple[int, str]] = {}  # (S##, eci_no) -> (year, type)
    with tcpd_ae_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            state_name = (row.get("State_Name") or "").strip()
            slug = TCPD_STATE_NAME_TO_SLUG.get(state_name)
            if not slug:
                continue
            state_code = SLUG_TO_ECI_STATE_CODE.get(slug)
            if not state_code:
                continue
            try:
                ac_no = int((row.get("Constituency_No") or "").strip())
                year = int((row.get("Year") or "").strip())
            except (TypeError, ValueError):
                continue
            if year < min_year:
                continue
            ct = (row.get("Constituency_Type") or "").strip()
            if ct in ("GEN", "GENERAL"):
                norm = "GEN"
            elif ct in ("SC", "ST"):
                norm = ct
            else:
                continue
            key = (state_code, ac_no)
            if key not in latest or latest[key][0] < year:
                latest[key] = (year, norm)
    return {k: v[1] for k, v in latest.items()}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TCPD GE loader (primary PC source - PC-level Constituency_Type)
# ---------------------------------------------------------------------------


def load_pc_reservations_from_tcpd_ge(
    tcpd_ge_csv: Path,
    *,
    min_year: int = 2009,
) -> dict[tuple[str, str], Reservation]:
    """Read ``All_States_GE.csv`` -> ``(state_slug, normalized_pc_name) -> reservation``.

    ``Constituency_Type`` is PC-level (constant across all candidate rows of
    a given (state, PC, year)). Keeps most-recent year per (state_slug, PC).
    Filters to ``Year >= min_year``. Skips silently when ``tcpd_ge_csv`` is
    missing.
    """
    if not tcpd_ge_csv.exists():
        return {}
    latest: dict[tuple[str, str], tuple[int, str]] = {}
    with tcpd_ge_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            state_name = (row.get("State_Name") or "").strip()
            slug = TCPD_STATE_NAME_TO_SLUG.get(state_name)
            if not slug:
                continue
            pc_name = (row.get("Constituency_Name") or "").strip()
            if not pc_name:
                continue
            try:
                year = int((row.get("Year") or "").strip())
            except (TypeError, ValueError):
                continue
            if year < min_year:
                continue
            ct = (row.get("Constituency_Type") or "").strip()
            if ct in ("GEN", "GENERAL"):
                norm = "GEN"
            elif ct in ("SC", "ST"):
                norm = ct
            else:
                continue
            key = (slug, normalize_pc_name(pc_name))
            if key not in latest or latest[key][0] < year:
                latest[key] = (year, norm)
    return {k: v[1] for k, v in latest.items()}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ECI Statement 33 loader (cross-check + secondary PC source)
# ---------------------------------------------------------------------------


def load_pc_reservations_from_eci_stmt33(
    csv_path: Path,
    *,
    header_row_index: int = 0,
) -> dict[tuple[str, str], Reservation]:
    """Read an ECI Statement 33 (Constituency-wise Detailed Result) CSV.

    ``header_row_index`` is the 0-based row index of the actual header line.
    The 2024 LS Stmt 33 file's header is on row 2 (rows 0-1 are titles and
    group-headers); the 2019 LS file's header is on row 0. Caller specifies.

    Returns ``(state_slug, normalized_pc_name) -> reservation``. Derived via
    the all-candidates-same-category rule: GEN if ANY candidate has
    ``Category = GENERAL``; SC if all candidates are SC; ST if all candidates
    are ST. Single-seat all-tribal areas (Ladakh, Lakshadweep, Nagaland,
    Mizoram) WILL derive as ST under this rule even though the 2008 Delim
    Order classifies them as GEN; the disagreement is surfaced in the verdict
    CSV. Skips silently when ``csv_path`` is missing.
    """
    if not csv_path.exists():
        return {}
    with csv_path.open(encoding="utf-8") as fh:
        lines = fh.readlines()
    if len(lines) <= header_row_index:
        return {}
    text = "".join(lines[header_row_index:])
    # The 2019 file header has padding spaces around column names; DictReader
    # handles this if we strip the keys before lookup.
    reader = csv.DictReader(io.StringIO(text, newline=""))

    # Map normalized header names -> actual header name.
    raw_fieldnames = reader.fieldnames or []
    norm_to_raw = {fn.strip().upper(): fn for fn in raw_fieldnames}

    def _col(row: dict[str, str], name_norm: str) -> str:
        raw = norm_to_raw.get(name_norm)
        if not raw:
            return ""
        return (row.get(raw) or "").strip()

    pc_cats: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in reader:
        state_name = _col(row, "STATE NAME")
        slug = ECI_STMT33_STATE_NAME_TO_SLUG.get(state_name)
        if not slug:
            continue
        pc_name = _col(row, "PC NAME")
        if not pc_name:
            continue
        cat = _col(row, "CATEGORY")
        if not cat:
            continue
        pc_cats[(slug, normalize_pc_name(pc_name))][cat.upper()] += 1

    out: dict[tuple[str, str], Reservation] = {}
    for key, cats in pc_cats.items():
        out[key] = _derive_pc_reservation_from_candidate_cats(cats)
    return out


def _derive_pc_reservation_from_candidate_cats(cats: Counter[str]) -> Reservation:
    """Apply the all-same-category rule to derive PC reservation.

    Rule:
      - all candidates SC -> SC
      - all candidates ST -> ST
      - otherwise (mixed or all GENERAL) -> GEN

    The "otherwise -> GEN" branch fires when any GENERAL candidate ran, OR
    when ECI marked the row with a non-{SC,ST} category like BL.
    """
    keys = set(cats.keys())
    if keys == {"SC"}:
        return "SC"
    if keys == {"ST"}:
        return "ST"
    return "GEN"


# ---------------------------------------------------------------------------
# Combined lookups (primary + fallback merge)
# ---------------------------------------------------------------------------


def build_ac_reservation_lookup(
    boundaries_sot_dir: Path,
    *,
    tcpd_ae_csv: Path | None = None,
) -> dict[tuple[str, int], Reservation]:
    """Primary boundaries_sot + fallback TCPD AE.

    Returns ``(state_code_S##, eci_no_int) -> reservation``. boundaries_sot
    wins; TCPD AE fills the gaps (historical united-AP eci_no 176..294 + the
    10 Arunachal AC gap rows + any other state where boundaries_sot under-
    covers the LGD register).
    """
    primary = load_ac_reservations_from_boundaries_sot(boundaries_sot_dir)
    if tcpd_ae_csv is None:
        return primary
    fallback = load_ac_reservations_from_tcpd_ae(tcpd_ae_csv)
    out = dict(fallback)
    out.update(primary)  # boundaries_sot wins
    return out


def build_ac_reservation_lookup_with_components(
    boundaries_sot_dir: Path,
    *,
    tcpd_ae_csv: Path | None = None,
) -> tuple[
    dict[tuple[str, int], Reservation],
    dict[tuple[str, int], Reservation],
    dict[tuple[str, int], Reservation],
]:
    """Like ``build_ac_reservation_lookup`` but returns the components too.

    Returns ``(merged, bsot, tcpd)`` so the caller can re-use the per-source
    dicts for verdict.csv without re-reading the 108 MB TCPD AE CSV twice.
    """
    bsot = load_ac_reservations_from_boundaries_sot(boundaries_sot_dir)
    tcpd: dict[tuple[str, int], Reservation] = {}
    if tcpd_ae_csv is not None:
        tcpd = load_ac_reservations_from_tcpd_ae(tcpd_ae_csv)
    merged = dict(tcpd)
    merged.update(bsot)
    return merged, bsot, tcpd


def build_pc_reservation_lookup_with_components(
    *,
    tcpd_ge_csv: Path | None = None,
    eci_stmt33_2024_csv: Path | None = None,
    eci_stmt33_2019_csv: Path | None = None,
) -> tuple[
    dict[tuple[str, str], Reservation],
    dict[tuple[str, str], Reservation],
    dict[tuple[str, str], Reservation],
    dict[tuple[str, str], Reservation],
]:
    """Like ``build_pc_reservation_lookup`` but returns components.

    Returns ``(merged, tcpd_ge, eci_2024, eci_2019)``.
    """
    tcpd_ge = (
        load_pc_reservations_from_tcpd_ge(tcpd_ge_csv) if tcpd_ge_csv else {}
    )
    eci_2024 = (
        load_pc_reservations_from_eci_stmt33(eci_stmt33_2024_csv, header_row_index=2)
        if eci_stmt33_2024_csv else {}
    )
    eci_2019 = (
        load_pc_reservations_from_eci_stmt33(eci_stmt33_2019_csv, header_row_index=0)
        if eci_stmt33_2019_csv else {}
    )
    merged: dict[tuple[str, str], Reservation] = dict(eci_2019)
    merged.update(eci_2024)
    merged.update(tcpd_ge)
    return merged, tcpd_ge, eci_2024, eci_2019


def build_pc_reservation_lookup(
    *,
    tcpd_ge_csv: Path | None = None,
    eci_stmt33_2024_csv: Path | None = None,
    eci_stmt33_2019_csv: Path | None = None,
) -> dict[tuple[str, str], Reservation]:
    """Primary TCPD GE + fallback ECI Stmt 33 (2024 -> 2019).

    Returns ``(state_slug, normalized_pc_name) -> reservation``.

    TCPD GE is PRIMARY because ``Constituency_Type`` is PC-level (clean) and
    the totals match the 2008 Delim Order published 84 SC + 47 ST + 412 GEN.
    ECI Stmt 33 derivation is a CROSS-CHECK (its ``Category`` column is
    candidate-level + over-counts ST in single-seat all-tribal UTs).
    """
    primary = (
        load_pc_reservations_from_tcpd_ge(tcpd_ge_csv) if tcpd_ge_csv else {}
    )
    fallback_2024 = (
        load_pc_reservations_from_eci_stmt33(eci_stmt33_2024_csv, header_row_index=2)
        if eci_stmt33_2024_csv
        else {}
    )
    fallback_2019 = (
        load_pc_reservations_from_eci_stmt33(eci_stmt33_2019_csv, header_row_index=0)
        if eci_stmt33_2019_csv
        else {}
    )
    out: dict[tuple[str, str], Reservation] = dict(fallback_2019)
    out.update(fallback_2024)
    out.update(primary)
    return out


# ---------------------------------------------------------------------------
# Verdict.csv emitters (parity surfaces; auto-correct is BANNED per
# CLAUDE.md section 10 - we surface disagreements for operator review).
# ---------------------------------------------------------------------------


def emit_ac_parity_verdict(
    *,
    boundaries_sot_dir: Path,
    tcpd_ae_csv: Path,
    out_path: Path,
    bsot_lookup: dict[tuple[str, int], Reservation] | None = None,
    tcpd_lookup: dict[tuple[str, int], Reservation] | None = None,
) -> int:
    """Emit AC-reservation parity boundaries_sot vs TCPD AE.

    Verdict.csv columns: ``state_code, eci_no, bsot_reservation,
    tcpd_reservation, agreement`` where ``agreement`` is ``AGREE``,
    ``DISAGREE``, ``BSOT_ONLY``, or ``TCPD_ONLY``. Returns the count of
    DISAGREE rows.

    Pre-loaded ``bsot_lookup`` / ``tcpd_lookup`` are honoured if passed
    (avoids re-reading the 108 MB TCPD AE on the verdict pass).
    """
    bsot = bsot_lookup if bsot_lookup is not None else load_ac_reservations_from_boundaries_sot(boundaries_sot_dir)
    tcpd = tcpd_lookup if tcpd_lookup is not None else load_ac_reservations_from_tcpd_ae(tcpd_ae_csv)
    keys = sorted(set(bsot.keys()) | set(tcpd.keys()))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_disagree = 0
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(
            ["state_code", "eci_no", "bsot_reservation", "tcpd_reservation", "agreement"]
        )
        for key in keys:
            state_code, eci_no = key
            b = bsot.get(key)
            t = tcpd.get(key)
            if b and t:
                ag = "AGREE" if b == t else "DISAGREE"
                if ag == "DISAGREE":
                    n_disagree += 1
            elif b:
                ag = "BSOT_ONLY"
            else:
                ag = "TCPD_ONLY"
            writer.writerow([state_code, eci_no, b or "", t or "", ag])
    return n_disagree


def emit_pc_parity_verdict(
    *,
    tcpd_ge_csv: Path,
    eci_stmt33_2024_csv: Path,
    out_path: Path,
    tcpd_lookup: dict[tuple[str, str], Reservation] | None = None,
    eci_2024_lookup: dict[tuple[str, str], Reservation] | None = None,
) -> int:
    """Emit PC-reservation parity TCPD GE vs ECI Stmt 33 2024 (derived).

    Verdict.csv columns: ``state_slug, pc_name, tcpd_reservation,
    eci_2024_derived_reservation, agreement``. Returns the count of DISAGREE
    rows.

    Pre-loaded ``tcpd_lookup`` / ``eci_2024_lookup`` are honoured if passed.
    """
    tcpd = tcpd_lookup if tcpd_lookup is not None else load_pc_reservations_from_tcpd_ge(tcpd_ge_csv)
    eci_2024 = eci_2024_lookup if eci_2024_lookup is not None else load_pc_reservations_from_eci_stmt33(
        eci_stmt33_2024_csv, header_row_index=2
    )
    keys = sorted(set(tcpd.keys()) | set(eci_2024.keys()))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_disagree = 0
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(
            [
                "state_slug",
                "pc_name_normalized",
                "tcpd_reservation",
                "eci_2024_derived_reservation",
                "agreement",
            ]
        )
        for key in keys:
            slug, pc = key
            t = tcpd.get(key)
            e = eci_2024.get(key)
            if t and e:
                ag = "AGREE" if t == e else "DISAGREE"
                if ag == "DISAGREE":
                    n_disagree += 1
            elif t:
                ag = "TCPD_ONLY"
            else:
                ag = "ECI_ONLY"
            writer.writerow([slug, pc, t or "", e or "", ag])
    return n_disagree
