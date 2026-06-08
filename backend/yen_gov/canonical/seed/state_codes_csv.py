"""B2b.5.0b entities/state_codes.csv emitter.

Joins the committed LGD parsed snapshot (``datasets/data/entities/lgd/states.csv``,
the LGD-authority register from B2b.5.0a) with the committed ISO transcription
seed (``datasets/data/entities/state_iso_seed.csv``) to emit the LGD-spine
state/UT identity table ``datasets/data/entities/state_codes.csv``.

G8 (2026-06-08): the ISO seed moved out of ``datasets/reference/`` into
``datasets/data/entities/`` as part of the mechanical ``datasets/reference/``
reshape (plan-doc section 9 + section 21.2). The seed shape is unchanged.
G8-finish (2026-06-08): the LGD parsed snapshot also moved from
``datasets/reference/lgd/`` into ``datasets/data/entities/lgd/`` as part of
the full ``datasets/reference/`` tier retirement.

Per sub-plan section 0c.4 / round-8c:

- ``lgd_state_id``     (PK)  <- snapshot ``lgd_state_code`` (LGD-issued)
- ``lgd_name``               <- snapshot ``state_name`` (LGD authority)
- ``iso_3166_2``             <- ISO seed (ISO-issued; yen-gov transcribes)
- ``census_2001_code``       <- snapshot (LABEL only, NEVER a join key)
- ``census_2011_code``       <- snapshot (LABEL only, NEVER a join key)
- ``kind`` (state|ut)        <- snapshot (LGD authority)
- ``slug``                   <- ISO seed (yen-gov-authored; URL/display only)
- ``aliases`` (pipe-delim)   <- ISO seed (derived display synonyms; regenerable)

``eci_st_code`` is DROPPED (round-8: no authoritative ECI state-code registry).
Census codes are LABEL columns, never exact-match keys (they renumber across
2001/2011 + reorganizations and go null for post-2011 entities such as
Telangana / Ladakh / DNH-DD; a ``JOIN ON census_*_code`` silently drops them -
a phantom Rosling Gap). The two dated columns ARE the round-8 "when it was, when
it is not" temporality.

Authority split (provenance receipts in ``docs/concepts/lgd-authority.md``):
LGD columns trace to the dated LGD snapshot; ``iso_3166_2`` traces to ISO; the
ISO seed's state set MUST equal the LGD snapshot's state set (a new UT in the
snapshot with no ISO seed row fails loud - the iso-seed-coverage gate).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv


FILE_CLASS = "datasets/data/entities/state_codes.csv"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def emit(
    *,
    lgd_snapshot_states_csv: Path,
    state_iso_seed_csv: Path,
    out_path: Path,
) -> Path:
    """Emit ``out_path`` from the LGD snapshot + ISO seed; return the path.

    Raises:
        FileNotFoundError: either input is missing.
        ValueError: the ISO seed state set does not exactly equal the LGD
            snapshot state set (iso-seed-coverage), a required field is missing,
            or a duplicate ``lgd_state_id`` appears.
    """
    if not lgd_snapshot_states_csv.exists():
        raise FileNotFoundError(lgd_snapshot_states_csv)
    if not state_iso_seed_csv.exists():
        raise FileNotFoundError(state_iso_seed_csv)

    snapshot = _read_csv_rows(lgd_snapshot_states_csv)
    seed_rows = _read_csv_rows(state_iso_seed_csv)
    seed_by_code = {r["lgd_state_code"]: r for r in seed_rows}

    snap_codes = {r["lgd_state_code"] for r in snapshot}
    seed_codes = set(seed_by_code)
    if snap_codes != seed_codes:
        raise ValueError(
            "iso-seed-coverage: ISO seed state set does not equal the LGD "
            f"snapshot state set. snapshot-only={sorted(snap_codes - seed_codes)}, "
            f"seed-only={sorted(seed_codes - snap_codes)}. Add the missing ISO "
            "transcription row(s) to datasets/data/entities/state_iso_seed.csv."
        )

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for s in snapshot:
        code = s["lgd_state_code"]
        if code in seen:
            raise ValueError(f"duplicate lgd_state_id {code!r} in LGD snapshot")
        seen.add(code)
        seed = seed_by_code[code]
        name = s["state_name"].strip()
        kind = s["kind"].strip()
        iso = seed["iso_3166_2"].strip()
        slug = seed["slug"].strip()
        if not name:
            raise ValueError(f"state {code} missing state_name in snapshot")
        if kind not in ("state", "ut"):
            raise ValueError(f"state {code} unexpected kind {kind!r}")
        if not iso:
            raise ValueError(f"state {code} missing iso_3166_2 in seed")
        if not slug:
            raise ValueError(f"state {code} missing slug in seed")
        rows.append(
            {
                "lgd_state_id": code,
                "lgd_name": name,
                "iso_3166_2": iso,
                "census_2001_code": (s.get("census_2001_code") or "").strip() or None,
                "census_2011_code": (s.get("census_2011_code") or "").strip() or None,
                "kind": kind,
                "slug": slug,
                "aliases": (seed.get("aliases") or "").strip() or None,
            }
        )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
