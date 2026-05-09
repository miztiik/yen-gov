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
EVENTS_IN_ECI = DATASETS / "events" / "in" / "eci"
ELECTIONS_ROOT = DATASETS / "elections"
REFERENCE_STATES_ROOT = DATASETS / "reference" / "in" / "states"

# Known missing per-AC files where Section 10 intentionally has no publishable
# winner record (countermanded/postponed constituency).
ALLOWED_MISSING_RESULTS: dict[tuple[str, str], set[int]] = {
    ("AcGenMay2026", "S25"): {144},
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
    for event_dir in sorted(ELECTIONS_ROOT.iterdir()):
        if not event_dir.is_dir():
            continue

        metadata_path = EVENTS_IN_ECI / event_dir.name / "election.json"
        assert metadata_path.exists(), (
            f"missing event metadata for emitted event '{event_dir.name}': "
            f"expected {metadata_path}"
        )

        metadata = _load_json(metadata_path)
        declared_states = set(metadata.get("states", []))
        emitted_states = {d.name for d in event_dir.iterdir() if d.is_dir()}

        extra = sorted(emitted_states - declared_states)
        assert not extra, (
            f"event '{event_dir.name}' emits undeclared states in elections/: "
            f"{extra}; declared={sorted(declared_states)}"
        )


def test_results_cover_reference_constituency_numbers():
    for event_dir in sorted(ELECTIONS_ROOT.iterdir()):
        if not event_dir.is_dir():
            continue

        for state_dir in sorted(d for d in event_dir.iterdir() if d.is_dir()):
            reference_path = REFERENCE_STATES_ROOT / state_dir.name / "constituencies.json"
            if not reference_path.exists():
                continue

            reference = _load_json(reference_path)
            expected = {int(c["eci_no"]) for c in reference["constituencies"]}
            actual = _result_nos(state_dir / "results")
            allowed_missing = ALLOWED_MISSING_RESULTS.get((event_dir.name, state_dir.name), set())

            missing = expected - actual
            unexpected_missing = missing - allowed_missing
            extra = actual - expected

            assert not unexpected_missing, (
                f"{event_dir.name}/{state_dir.name}: unexpected missing result files "
                f"for eci_no={sorted(unexpected_missing)}"
            )
            assert not extra, (
                f"{event_dir.name}/{state_dir.name}: results contain unknown eci_no "
                f"values {sorted(extra)}"
            )

            if allowed_missing:
                assert missing == allowed_missing, (
                    f"{event_dir.name}/{state_dir.name}: allowlisted missing AC set "
                    f"drifted; expected {sorted(allowed_missing)}, got {sorted(missing)}"
                )


def test_result_name_reservation_matches_reference():
    for event_dir in sorted(ELECTIONS_ROOT.iterdir()):
        if not event_dir.is_dir():
            continue

        for state_dir in sorted(d for d in event_dir.iterdir() if d.is_dir()):
            reference_path = REFERENCE_STATES_ROOT / state_dir.name / "constituencies.json"
            if not reference_path.exists():
                continue

            reference = _load_json(reference_path)
            status = str(reference.get("status", "provisional"))
            reservation_by_no = {
                int(c["eci_no"]): str(c["reservation"])
                for c in reference["constituencies"]
            }

            mismatches: list[dict[str, object]] = []
            for result_file in sorted((state_dir / "results").glob("*.json")):
                if not result_file.is_file() or not result_file.stem.isdigit():
                    continue
                eci_no = int(result_file.stem)
                if eci_no not in reservation_by_no:
                    continue

                result_doc = _load_json(result_file)
                inferred = _reservation_from_result_name(str(result_doc.get("constituency_name", "")))
                expected = reservation_by_no[eci_no]
                if inferred != expected:
                    mismatches.append({"eci_no": eci_no, "expected": expected, "inferred": inferred})

            if status == "complete":
                assert not mismatches, (
                    f"{event_dir.name}/{state_dir.name}: reservation mismatches in complete "
                    f"reference file: {mismatches[:10]}"
                )
            else:
                explicit_reserved_mismatches = [
                    m for m in mismatches if str(m["inferred"]) in {"SC", "ST"}
                ]
                assert not explicit_reserved_mismatches, (
                    f"{event_dir.name}/{state_dir.name}: reservation mismatches where "
                    f"result names explicitly encode SC/ST: {explicit_reserved_mismatches[:10]}"
                )