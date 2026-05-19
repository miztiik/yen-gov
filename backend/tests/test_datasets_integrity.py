"""Repository-level dataset consistency checks.

These tests are intentionally stdlib-only so they can run in constrained
environments while still catching high-value contract drift:

1. Emitted event/state slices under datasets/elections must be declared in the
   corresponding datasets/events/in/eci/<event>/election.json metadata.
2. Result file numbers must match reference constituency numbers, with an
   explicit allowlist for known countermanded/postponed ACs.
3. Reservation markers encoded in result constituency names should align with
   the reference reservation map.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
DATASETS = REPO / "datasets"
ELECTIONS_ROOT = DATASETS / "elections"
REFERENCE_STATES_ROOT = DATASETS / "reference" / "in" / "states"
ELECTION_EVENTS_PATH = DATASETS / "reference" / "in" / "election-events.json"

# Known missing per-AC files where Section 10 intentionally has no publishable
# winner record (countermanded/postponed constituency).
ALLOWED_MISSING_RESULTS: dict[tuple[str, str], set[int]] = {
    ("AcGenMay2026", "S25"): {144},
    # Karnataka 2018: AC 173 Jayanagar was countermanded after a candidate's
    # death and the result was declared in a 2018 by-election rather than
    # the general election. Bootstrap pulled S10 reference from AcGenMay2023
    # (which has all 224), so the AcGenMay2018 results legitimately miss 173.
    ("AcGenMay2018", "S10"): {173},
    # Meghalaya 2023: AC 23 Sohiong was countermanded after a candidate's
    # death; held as a by-election on 22 May 2023. Section 10 Statistical
    # Report covers 59 of 60 ACs.
    ("AcGenFeb2023", "S15"): {23},
    # Nagaland 2023: AC 31 Akuluto was uncontested — Y. Patton (BJP) declared
    # elected unopposed. Section 10 Statistical Report has no row for it
    # (no poll = no result tally).
    ("AcGenFeb2023", "S17"): {31},
    # Tamil Nadu 2016: AC 134 Aravakurichi and AC 174 Thanjavur were
    # countermanded due to cash-for-votes seizures; held as by-elections on
    # 19 November 2016. Section 10 Report has 232 of 234 ACs.
    ("AcGenMay2016", "S22"): {134, 174},
    # Meghalaya 2018: AC 43 Williamnagar was countermanded after a
    # candidate's death; held as a by-election later. Section 10 carries
    # the candidate roster but with NULL vote columns (parser now coerces
    # NULL -> 0 and the mapper drops zero-vote AC sections).
    ("AcGenFeb2018", "S15"): {43},
    # Nagaland 2018: AC 11 Northern Angami-II — Neiphiu Rio (NDPP)
    # declared elected unopposed. Section 10 carries the roster with NULL
    # vote cells; no poll was held.
    ("AcGenFeb2018", "S17"): {11},
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _result_nos(results_dir: Path) -> set[int]:
    if not results_dir.exists():
        return set()
    return {
        int(p.stem)
        for p in results_dir.glob("*.json")
        if p.is_file() and p.stem.isdigit()
    }


def _reservation_from_result_name(name: str) -> str:
    upper = name.upper().strip()
    if upper.endswith("(SC)"):
        return "SC"
    if upper.endswith("(ST)"):
        return "ST"
    return "GEN"


def test_emitted_states_are_declared_in_event_metadata():
    # Retired 2026-05-19 (PR-Q, TODO row 1.8d). This walked both
    # ``ELECTIONS_ROOT`` and ``EVENTS_IN_ECI / <event> / election.json`` to
    # check declared_states (in JSON metadata) matched the on-disk state
    # directory list. Both directory walks are the CLAUDE.md §10
    # corpus-walker anti-pattern, and the JSON contract surface itself has
    # been deleted in this PR — ``datasets/events/in/eci/`` was a parallel
    # projection of the EVENTS Python registry in
    # ``backend/yen_gov/sources/eci/events.py`` and added no information
    # the registry didn't already hold. The replacement gates are:
    #   * ``test_election_events_catalogue_matches_backend_registry`` below
    #     compares the EVENTS Python registry against
    #     ``datasets/reference/in/election-events.json`` (citizen catalogue)
    #     — this is the load-bearing contract that prevents drift;
    #   * canonical adapter (``backend/yen_gov/canonical/adapters/``) writes
    #     ``dim_acs`` rows keyed on ``(event_id, state)`` directly from the
    #     EVENTS registry, so any mis-declared state is rejected at write
    #     time, not at test time.
    pass


def test_results_cover_reference_constituency_numbers():
    # Retired 2026-05-19 (PR-P, TODO row 1.8c). The per-AC
    # ``datasets/elections/<event>/<state>/results/<ac>.json`` shards this
    # test walked have been deleted; canonical Parquet
    # (``election_results.parquet`` + ``dim_acs.parquet`` +
    # ``dim_candidates.parquet``) is now the single source of truth.
    # Walking thousands of files inside pytest was the CLAUDE.md §10
    # corpus-walker anti-pattern in the first place (see
    # /memories/lessons.md, 2026-05-16 validator descope). The replacement
    # gates are:
    #   * canonical adapter (``backend/yen_gov/canonical/adapters/``) writes
    #     dim_acs rows from the same reference catalogue this test consumed;
    #   * extended Playwright (``frontend/e2e/golden-path.spec.ts``) covers
    #     TN + KL + WB AC#1 routes proving the canonical loader resolves
    #     dim_acs ⋈ observations across states without per-state holes;
    #   * the Tier-B local validator (``python -m yen_gov validate --root .``)
    #     still checks any per-AC JSON that re-appears on disk.
    # If parser regression coverage for the legacy emit path becomes
    # important (e.g. operator-only re-emits via ``eci-statreport-emit-local``),
    # add fixture-based parser unit tests in ``backend/tests/`` against
    # tmp_path XLSX fixtures — that tests CODE, not DATA.
    pass


def test_result_name_reservation_matches_reference():
    # Retired 2026-05-19 (PR-P, TODO row 1.8c) for the same reason as
    # ``test_results_cover_reference_constituency_numbers`` above. The
    # reservation truth that this test verified (per-AC JSON name suffix
    # ``(SC)`` / ``(ST)`` matches reference catalogue) now lives in
    # ``dim_acs.reservation`` in the canonical Parquet, populated directly
    # from the reference catalogue at adapter time. There is no parallel
    # JSON projection to drift against.
    pass


def test_election_events_catalogue_matches_backend_registry():
    """The hand-authored citizen-facing catalogue (datasets/reference/in/
    election-events.json, ADR-0023) must agree with the backend's
    authoritative `events.py` registry on every (state, event_id) pair.

    This is the load-bearing contract that lets the frontend resolve
    `defaultEventForState(state)` without bundling Python. If the two ever
    drift, the frontend will 404 on a state we have data for, or claim we
    have data for a state that's never been ingested. Either way, this
    test fails LOUDLY at CI rather than silently in production.
    """
    from yen_gov.sources.eci.events import EVENTS  # local import: keeps stdlib-only top of file

    catalogue = _load_json(ELECTION_EVENTS_PATH)
    catalogue_pairs: set[tuple[str, str]] = {
        (state_code, str(entry["event_id"]))
        for state_code, entries in catalogue["states"].items()
        for entry in entries
    }
    backend_pairs: set[tuple[str, str]] = {
        (state_code, info.event_id) for (state_code, _year), info in EVENTS.items()
    }

    only_in_backend = sorted(backend_pairs - catalogue_pairs)
    only_in_catalogue = sorted(catalogue_pairs - backend_pairs)

    assert not only_in_backend, (
        "events.py declares (state, event_id) pairs missing from "
        "datasets/reference/in/election-events.json — citizens will see "
        f"states with no election link in the UI: {only_in_backend}"
    )
    assert not only_in_catalogue, (
        "election-events.json declares (state, event_id) pairs not in "
        "events.py — frontend will 404 trying to fetch nonexistent "
        f"artifacts: {only_in_catalogue}"
    )


def test_election_events_default_uniqueness():
    """Per state: at most one event has `default: true` so
    /s/<state>/elections has a deterministic landing event.

    The data_status ↔ result.summary.json alignment assertion that used
    to live alongside this one retired in PR-O.3b-main (TODO row
    ``1.8b-writers-b-main``): per-event ``result.summary.json`` shards
    are no longer written — the canonical store
    (``datasets/elections/election_results.parquet``) is the single
    source of truth, and the frontend e2e suite catches any 404 caused
    by a status-vs-data drift. Walking the real on-disk corpus from a
    pytest test also violated CLAUDE.md §10.
    """
    catalogue = _load_json(ELECTION_EVENTS_PATH)

    for state_code, entries in catalogue["states"].items():
        defaults = [e for e in entries if e.get("default") is True]
        assert len(defaults) <= 1, (
            f"state {state_code}: more than one event marked default=true "
            f"({[e['event_id'] for e in defaults]}); /s/<state>/elections "
            f"would not have a deterministic landing event."
        )


# ---------------------------------------------------------------------------
# state-tiers.json contract tests (P3.1 IA reset)
# ---------------------------------------------------------------------------

STATE_TIERS_PATH = DATASETS / "reference" / "in" / "state-tiers.json"
STATES_REGISTRY_PATH = DATASETS / "reference" / "in" / "states.json"
TOPIC_CATALOGUE_PATH = DATASETS / "reference" / "in" / "topic-catalogue.json"


def _known_state_codes() -> set[str]:
    states_doc = _load_json(STATES_REGISTRY_PATH)
    return {s["eci_code"] for s in states_doc["states"]}


def _known_tier_ids() -> set[str]:
    tiers_doc = _load_json(STATE_TIERS_PATH)
    return {t["id"] for t in tiers_doc["tiers"]}


def test_state_tiers_codes_are_known_states():
    """Every member of every tier must be a real ECI code in states.json.
    Catches typos (S30, U10) and stale memberships after a state split."""
    known = _known_state_codes()
    tiers_doc = _load_json(STATE_TIERS_PATH)
    for tier in tiers_doc["tiers"]:
        unknown = set(tier["members"]) - known
        assert not unknown, (
            f"tier {tier['id']} references unknown ECI codes: {sorted(unknown)}"
        )


def test_state_tiers_ut_partition():
    """The three UT tiers must partition the UT space exactly once each.
    ut_legislature and ut_no_legislature are disjoint and union to
    every UT EXCEPT U05 (NCT-Delhi, which has its own singleton tier
    because Article 239AA is sui generis)."""
    tiers = {t["id"]: set(t["members"]) for t in _load_json(STATE_TIERS_PATH)["tiers"]}
    ut_with = tiers.get("ut_legislature", set())
    ut_without = tiers.get("ut_no_legislature", set())
    nct = tiers.get("nct_delhi", set())

    assert ut_with & ut_without == set(), (
        f"ut_legislature and ut_no_legislature overlap: {ut_with & ut_without}"
    )
    assert nct == {"U05"}, f"nct_delhi must be exactly {{'U05'}}, got {nct}"

    all_uts = {c for c in _known_state_codes() if c.startswith("U")}
    covered = ut_with | ut_without | nct
    assert covered == all_uts, (
        f"UT tiers do not cover every UT exactly once. "
        f"Missing: {all_uts - covered}; extra: {covered - all_uts}"
    )


def test_state_tiers_full_coverage():
    """Union of every tier with non-empty membership must cover every
    state and UT in states.json. Empty tiers (e.g. fc_horizontal_devolution
    awaiting recon) are skipped — their absence is honest signal, not
    failure."""
    known = _known_state_codes()
    union: set[str] = set()
    for tier in _load_json(STATE_TIERS_PATH)["tiers"]:
        if tier["members"]:
            union.update(tier["members"])
    missing = known - union
    assert not missing, (
        f"states/UTs not in any tier (would be invisible to peer-set filters): "
        f"{sorted(missing)}"
    )


def test_state_tiers_nct_delhi_singleton():
    """NCT-Delhi tier is intentionally a singleton (Article 239AA sui
    generis); regression-protect against accidental membership churn."""
    tiers = {t["id"]: t for t in _load_json(STATE_TIERS_PATH)["tiers"]}
    nct = tiers["nct_delhi"]
    assert nct["members"] == ["U05"], (
        f"nct_delhi must remain a singleton == ['U05']; got {nct['members']}"
    )
    assert nct["definition_kind"] == "constitutional"


def test_topic_catalogue_peer_set_default_resolves():
    """Every topic-level and artifact-level peer_set_default in the
    topic catalogue must resolve to a known tier id or ll. This is the
    contract that lets the resolver always return a valid PeerSet without
    runtime guards."""
    valid = _known_tier_ids() | {"all"}
    catalogue = _load_json(TOPIC_CATALOGUE_PATH)

    for topic in catalogue["topics"]:
        topic_default = topic.get("peer_set_default")
        if topic_default is not None:
            assert topic_default in valid, (
                f"topic {topic['id']} declares unknown peer_set_default "
                f"{topic_default}; valid: {sorted(valid)}"
            )
        for art in topic.get("artifacts", []):
            art_default = art.get("peer_set_default")
            if art_default is not None:
                assert art_default in valid, (
                    f"topic {topic['id']} artifact {art.get('id')} "
                    f"declares unknown peer_set_default {art_default}; "
                    f"valid: {sorted(valid)}"
                )


def test_no_indicator_notes_sidecars_exist():
    """Indicator metadata was folded into the indicator artifact itself
    in the v1.5 -> v1.6 migration (commit 6 of the folded-indicator PR).

    `.notes.json` sidecars are NO LONGER a supported overlay. Any new
    sidecar appearing here would silently be ignored by the frontend
    and would route hand-curated editorial content (editor_note_md,
    policy_context, chart_defaults, related) into a dead file.

    If this test fails, fold the sidecar's fields into the indicator's
    inline `methodology` block and delete the sidecar.
    """
    indicators_root = DATASETS / "indicators"
    sidecars = sorted(p.relative_to(REPO).as_posix() for p in indicators_root.rglob("*.notes.json"))
    assert sidecars == [], (
        "Found .notes.json sidecars under datasets/indicators/; these "
        "must be folded into the indicator's inline `methodology` "
        "block. Offenders: " + ", ".join(sidecars)
    )

