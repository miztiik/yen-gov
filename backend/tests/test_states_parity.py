"""Parity oracle: legacy ``datasets/reference/in/states.json`` vs canonical
``datasets/taxonomy/entities.json``.

Pre-PR-T.0c-ii ``states.json`` was the SoT for the 28-state + 8-UT current
roster consumed by:

- ``backend/yen_gov/coverage.py`` (Holy Law #4 inventory: ``STATES_REL``)
- ``tools/lgd/backfill_lgd_codes.py`` (LGD code joins: ``STATES_JSON``)
- ``backend/yen_gov/sources/india_geodata/power_plants.py`` (name → ECI map)
- ``frontend/src/lib/data.ts::fetchStates`` (Home + StateTopic)
- ``backend/tests/test_datasets_integrity.py`` (``STATES_REGISTRY_PATH``)

Phase A of the T.0c-ii port — see
``TODO/20260521-states-json-port-blocker-entities-ut-gap.md`` — filled the
7-UT gap in ``taxonomy/entities.json`` (only Delhi was present prior). This
test is the back-stop that the gap remains filled and that the legacy file
and the canonical taxonomy stay in lockstep across the port (Phase B
backend repoint, Phase C frontend repoint + ``states.json`` deletion).

Holy Law #7: uses the REAL on-disk JSON files — no mocks. Reads two
named files (not a corpus walk per CLAUDE.md §10), so this is Tier-A
test code, not Tier-B corpus conformance. Skipped cleanly when either
file is absent.

Repo root injection: honours ``YEN_GOV_REPO_ROOT`` env var (same pattern
as ``backend/tests/test_admin_inventory.py`` and ADR-0026 / lessons.md
2026-05-16 monkeypatch-the-root convention) so fixture-driven tests can
re-target; defaults to the real repo at runtime.

Runs in <0.1s.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


def _repo_root() -> Path:
    """Resolve repo root honouring ``YEN_GOV_REPO_ROOT`` env var.

    Default: ``Path(__file__).parents[2]`` (backend/tests/x.py -> repo).
    """
    env = os.environ.get("YEN_GOV_REPO_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Documented name-display deviations.
#
# entities.json carries the TEMPORAL axis (entity_valid_from / entity_valid_to)
# so it disambiguates the post-2019 J&K UT (IN-U08) from the historic pre-2019
# composite J&K state (IN-S09) by suffixing the display_name with "(UT)".
# states.json is current-only and has no such sibling, so it carries the
# unsuffixed citizen name. This is correct authoring, not a drift — both
# rows refer to the same eci_code U08 with kind=union_territory / entity_type=ut.
#
# Add new entries here ONLY when adding a historic-sibling row that forces
# the current row to take a disambiguating suffix.
# ---------------------------------------------------------------------------
ALLOWED_NAME_DEVIATIONS: frozenset[tuple[str, str, str]] = frozenset({
    # (eci_code, states.json name, entities.json display_name)
    ("U08", "Jammu and Kashmir", "Jammu and Kashmir (UT)"),
})

# states.json kind -> entities.json entity_type
_KIND_TO_ENTITY_TYPE = {
    "state": "state",
    "union_territory": "ut",
}


def _states_json_path() -> Path:
    return _repo_root() / "datasets" / "reference" / "in" / "states.json"


def _entities_json_path() -> Path:
    return _repo_root() / "datasets" / "taxonomy" / "entities.json"


def _load_states() -> list[dict]:
    return json.loads(_states_json_path().read_text(encoding="utf-8"))["states"]


def _load_current_state_and_ut_entities() -> dict[str, dict]:
    """Index entities.json by entity_code, filtered to current state+UT rows."""
    entities = json.loads(_entities_json_path().read_text(encoding="utf-8"))["entities"]
    return {
        e["entity_code"]: e
        for e in entities
        if e["entity_type"] in ("state", "ut") and e.get("entity_valid_to") is None
    }


_skipif_missing = pytest.mark.skipif(
    not (_states_json_path().is_file() and _entities_json_path().is_file()),
    reason="legacy states.json or canonical entities.json absent from this checkout",
)


@_skipif_missing
def test_every_legacy_state_has_canonical_entity() -> None:
    """Every (eci_code, kind) in states.json must resolve to a current row.

    Asserts:
      - entity_code == eci_code (strict)
      - entity_type matches the kind mapping (strict)
      - entity_valid_to IS NULL (i.e. still a current entity)
    """
    states = _load_states()
    ents = _load_current_state_and_ut_entities()
    failures: list[str] = []
    for s in states:
        code = s["eci_code"]
        expected_type = _KIND_TO_ENTITY_TYPE[s["kind"]]
        ent = ents.get(code)
        if ent is None:
            failures.append(
                f"states.json {code} ({s['name']!r}) has no current entities.json row"
            )
            continue
        if ent["entity_type"] != expected_type:
            failures.append(
                f"states.json {code}: kind={s['kind']!r} expects entity_type="
                f"{expected_type!r}, got {ent['entity_type']!r}"
            )
    assert not failures, "\n".join(failures)


@_skipif_missing
def test_no_extra_current_state_or_ut_in_entities() -> None:
    """Inverse check: every current state+UT row in entities.json must appear in states.json."""
    states = _load_states()
    state_codes = {s["eci_code"] for s in states}
    ents = _load_current_state_and_ut_entities()
    extra = sorted(c for c in ents if c not in state_codes)
    assert not extra, (
        f"entities.json has current state+UT rows missing from legacy states.json: {extra}. "
        "Either add the row to states.json (parity surface) or mark the entity historical "
        "(set entity_valid_to)."
    )


@_skipif_missing
def test_count_parity_current_state_and_ut() -> None:
    """Cardinality must match: 28 states + 8 UTs = 36 on both sides today.

    The literal expectation is intentionally not hard-coded; we assert
    LEN-EQUALITY so the test stays correct if a new state/UT is added on
    both sides in lockstep (the per-row tests above catch one-sided adds).
    """
    states = _load_states()
    ents = _load_current_state_and_ut_entities()
    assert len(states) == len(ents), (
        f"count drift: states.json has {len(states)} rows, "
        f"entities.json current state+UT has {len(ents)}"
    )


@_skipif_missing
def test_display_name_parity_with_documented_deviations() -> None:
    """Citizen-shown name must match between the two surfaces.

    The ONLY permitted deviations are explicit historic-sibling
    disambiguations (e.g. IN-U08 carrying "(UT)" suffix because IN-S09
    historical state row exists). Tracked in ALLOWED_NAME_DEVIATIONS.
    """
    states = _load_states()
    ents = _load_current_state_and_ut_entities()
    drifts: list[tuple[str, str, str]] = []
    for s in states:
        code = s["eci_code"]
        ent = ents.get(code)
        if ent is None:
            continue  # caught by the other test
        legacy_name = s["name"]
        canonical_name = ent["display_name"]
        if legacy_name == canonical_name:
            continue
        if (code, legacy_name, canonical_name) in ALLOWED_NAME_DEVIATIONS:
            continue
        drifts.append((code, legacy_name, canonical_name))
    assert not drifts, (
        "display_name drift between states.json and entities.json that is not in "
        f"ALLOWED_NAME_DEVIATIONS:\n  "
        + "\n  ".join(f"{c}: states={l!r} entities={e!r}" for c, l, e in drifts)
    )
