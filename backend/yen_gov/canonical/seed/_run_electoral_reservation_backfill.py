"""PR-E-R in-place backfill of ``electoral.csv.reservation`` (2026-06-10).

Reads ``datasets/data/entities/electoral.csv`` row-by-row, populates the
``reservation`` column on AC + PC rows using the lookups built by
``reservation_sources``, and re-emits the file via ``csv_writer.write_csv``
(deterministic shape + skip-if-equal).

This is **in-place**: row identity (``entity_id``), every other column, and
the total row count are PRESERVED. Only the ``reservation`` cell flips
empty -> GEN/SC/ST. The 338 hand-curated ``eci<N>`` synthetic-key rows
(PRs #844 + #849 + #858 - LGD-register gap fills) are preserved as-is;
their reservation is populated via the same lookup using ``(state_code, eci_no)``
for ACs or ``(state_slug, normalised_pc_name)`` for PCs.

We do NOT call ``electoral_csv_from_snapshot.emit`` because that emitter
re-derives the row set from the LGD snapshot (4395 rows) and would drop the
338 hand-curated synthetic-key rows. PR-E-R is strictly a column-backfill,
NOT a row regeneration.

Sources (all optional; missing inputs leave gaps as ``reservation = ''``):

- ``datasets/data/entities/boundaries_sot/<S##>/constituencies.json``
  (committed; primary AC source - 4061 / 4189 ACs)
- ``datasets/ephemeral/All_States_AE.csv`` (TCPD; fallback AC for
  historical united-AP eci_no 176..294 + 10 Arunachal gap rows + 14 metro AC
  gaps in synthetic-key rows)
- ``datasets/ephemeral/All_States_GE.csv`` (TCPD; primary PC source -
  Constituency_Type is PC-level, matches 2008 Delim Order)
- ``datasets/ephemeral/2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv``
  (ECI Statement 33; PC cross-check)
- ``datasets/ephemeral/2019_india_loksabha_33. Constituency Wise Detailed Result.csv``
  (ECI Statement 33; older PC fallback)

Run from repo root:

    python -m yen_gov.canonical.seed._run_electoral_reservation_backfill
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from pathlib import Path

from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.seed import electoral_csv_from_snapshot as electoral
from yen_gov.canonical.seed import reservation_sources
from yen_gov.canonical.csv_validator import validate_csv


_AC_KINDS = {"ac"}
_PC_KINDS = {"pc"}


def backfill(
    *,
    electoral_csv: Path,
    ac_lookup: dict[tuple[str, int], str],
    pc_lookup: dict[tuple[str, str], str],
) -> tuple[int, int, int, int]:
    """Backfill ``reservation`` on every AC + PC row in ``electoral_csv``.

    Returns ``(ac_populated, ac_total, pc_populated, pc_total)``.
    """
    text = electoral_csv.read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, [])
    rows = list(reader)
    if not header:
        raise ValueError(f"{electoral_csv}: empty file (no header)")
    # Map by column name for index lookup.
    name_to_idx = {name: i for i, name in enumerate(header)}
    required = ("entity_kind", "state", "eci_no", "name", "reservation")
    for c in required:
        if c not in name_to_idx:
            raise ValueError(f"{electoral_csv}: missing column {c!r}")

    ac_pop = 0
    ac_total = 0
    pc_pop = 0
    pc_total = 0
    materialised: list[dict[str, str | None]] = []
    for raw in rows:
        row_dict: dict[str, str | None] = {}
        for col in header:
            v = raw[name_to_idx[col]]
            row_dict[col] = v if v != "" else None
        entity_kind = row_dict.get("entity_kind")
        if entity_kind in _AC_KINDS:
            ac_total += 1
            state_slug = row_dict.get("state") or ""
            eci_state_code = reservation_sources.SLUG_TO_ECI_STATE_CODE.get(state_slug)
            eci_no_str = row_dict.get("eci_no") or ""
            try:
                eci_no_int = int(eci_no_str) if eci_no_str else None
            except ValueError:
                eci_no_int = None
            res = None
            if eci_state_code and eci_no_int is not None:
                res = ac_lookup.get((eci_state_code, eci_no_int))
            if res:
                ac_pop += 1
                row_dict["reservation"] = res
        elif entity_kind in _PC_KINDS:
            pc_total += 1
            state_slug = row_dict.get("state") or ""
            pc_name = row_dict.get("name") or ""
            res = pc_lookup.get(
                (state_slug, reservation_sources._normalize_pc_with_alias(state_slug, pc_name))
            )
            if res:
                pc_pop += 1
                row_dict["reservation"] = res
        materialised.append(row_dict)

    # Coerce types per the writer contract: eci_no + delim_year are integer.
    typed_rows: list[dict[str, object]] = []
    for r in materialised:
        out: dict[str, object] = {}
        for col, val in r.items():
            if val is None:
                out[col] = None
                continue
            if col in ("delim_year", "eci_no"):
                try:
                    out[col] = int(val)
                except ValueError:
                    out[col] = val
            else:
                out[col] = val
        typed_rows.append(out)

    write_csv(
        path=electoral_csv,
        file_class=electoral.FILE_CLASS,
        rows=typed_rows,
    )
    return ac_pop, ac_total, pc_pop, pc_total


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    entities = repo_root / "datasets" / "data" / "entities"
    electoral_csv = entities / "electoral.csv"
    boundaries_sot_dir = entities / "boundaries_sot"
    ephemeral = repo_root / "datasets" / "ephemeral"
    tcpd_ae = ephemeral / "All_States_AE.csv"
    tcpd_ge = ephemeral / "All_States_GE.csv"
    eci_2024 = ephemeral / "2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv"
    eci_2019 = ephemeral / "2019_india_loksabha_33. Constituency Wise Detailed Result.csv"

    ac_lookup, bsot_lookup, tcpd_ae_lookup = reservation_sources.build_ac_reservation_lookup_with_components(
        boundaries_sot_dir,
        tcpd_ae_csv=tcpd_ae if tcpd_ae.exists() else None,
    )
    pc_lookup, tcpd_ge_lookup, eci_2024_lookup, _ = reservation_sources.build_pc_reservation_lookup_with_components(
        tcpd_ge_csv=tcpd_ge if tcpd_ge.exists() else None,
        eci_stmt33_2024_csv=eci_2024 if eci_2024.exists() else None,
        eci_stmt33_2019_csv=eci_2019 if eci_2019.exists() else None,
    )

    ac_pop, ac_total, pc_pop, pc_total = backfill(
        electoral_csv=electoral_csv,
        ac_lookup=ac_lookup,
        pc_lookup=pc_lookup,
    )
    print(f"electoral.csv reservation backfill:")
    print(f"  AC populated: {ac_pop}/{ac_total}")
    print(f"  PC populated: {pc_pop}/{pc_total}")
    print(f"  AC lookup keys: {len(ac_lookup)} (bsot {len(bsot_lookup)} + tcpd_ae {len(tcpd_ae_lookup)})")
    print(f"  PC lookup keys: {len(pc_lookup)} (tcpd_ge {len(tcpd_ge_lookup)} + eci_2024 {len(eci_2024_lookup)})")

    # Validator pass on the regenerated file.
    validate_csv(
        path=electoral_csv,
        file_class=electoral.FILE_CLASS,
        repo_root=repo_root,
    )
    print("  csv_validator: PASS")

    # PR-E-R parity verdict.csv emitters (operator audit; pre-loaded dicts
    # avoid the 108 MB TCPD AE re-read). Committed under the operator tier
    # (datasets/_ops/) - the ephemeral tier is gitignored and these verdicts
    # are the per-PR audit trail per Q3 (brief items 3-4 + plan section 0.4
    # default; the operator tier matches the audit-trail intent better than
    # writing to ephemeral and then force-adding).
    ops_dir = repo_root / "datasets" / "_ops" / "reservation-parity"
    if tcpd_ae.exists():
        verdict_ac = ops_dir / "ac-bsot-vs-tcpd.csv"
        n_disagree_ac = reservation_sources.emit_ac_parity_verdict(
            boundaries_sot_dir=boundaries_sot_dir,
            tcpd_ae_csv=tcpd_ae,
            out_path=verdict_ac,
            bsot_lookup=bsot_lookup,
            tcpd_lookup=tcpd_ae_lookup,
        )
        rel = verdict_ac.relative_to(repo_root).as_posix()
        print(f"  AC parity ({rel}): {n_disagree_ac} disagreements")
    if tcpd_ge.exists() and eci_2024.exists():
        verdict_pc = ops_dir / "pc-tcpd-vs-eci2024.csv"
        n_disagree_pc = reservation_sources.emit_pc_parity_verdict(
            tcpd_ge_csv=tcpd_ge,
            eci_stmt33_2024_csv=eci_2024,
            out_path=verdict_pc,
            tcpd_lookup=tcpd_ge_lookup,
            eci_2024_lookup=eci_2024_lookup,
        )
        rel = verdict_pc.relative_to(repo_root).as_posix()
        print(f"  PC parity ({rel}): {n_disagree_pc} disagreements")


if __name__ == "__main__":
    main()
