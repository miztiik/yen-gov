"""IndiaVotes parity oracle CLI.

One-shot offline operator tool. NEVER CI.

Usage (run standalone from a clean venv with httpx + bs4 + lxml installed):

    python tools/elections_parity_indiavotes/__main__.py \
      --event general-2024 \
      --state chhattisgarh \
      --output datasets/_ops/elections-parity-vs-indiavotes-2026-06-10.csv

See ``tools/elections_parity_indiavotes/README.md`` for the politeness rules,
the synthetic-fixture fallback, and the post-mortem doctrine (Holy Law #5:
parity miss = fix the yen-gov ingest, not stash IndiaVotes rows in
``source.csv``).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# Allow ``python tools/elections_parity_indiavotes/__main__.py`` to work
# without a packaging step (per pyproject.toml comment: this tool ships as
# a script, not an installable package).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from diff import (  # noqa: E402  -- intentional after sys.path tweak
    agreement_pct,
    compute_diff,
    read_yengov_winners,
)
from scrape import fetch_state_event, parse_winners  # noqa: E402

# Repo-root resolution: this file lives at
# ``<repo>/tools/elections_parity_indiavotes/__main__.py``; parent.parent.parent
# is ``<repo>``. All on-disk paths derive from this constant so the tool
# behaves identically from any working directory.
REPO_ROOT = _HERE.parent.parent

CACHE_ROOT = REPO_ROOT / "datasets" / "ephemeral" / "indiavotes-snapshots"
ELECTORAL_DATAPOINTS_DIR = REPO_ROOT / "datasets" / "data" / "datapoints" / "electoral"
ENTITIES_JSON = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"

CSV_COLUMNS = [
    "state",
    "event",
    "constituency_name",
    "source",
    "winner_party",
    "winner_name",
    "votes",
    "margin",
    "agrees",
    "delta_notes",
]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    state_slug = args.state.lower()
    event_slug = args.event.lower()

    # Argument validation: state must be in entities.json (avoid typos like
    # ``chattisgarh`` silently 404'ing IndiaVotes).
    state_slugs = _load_state_slugs(ENTITIES_JSON)
    if state_slug not in state_slugs:
        _die(
            f"unknown state slug {state_slug!r}; valid: "
            + ", ".join(sorted(state_slugs))
        )

    # The per-state CSV is named ``<state>_election_results.csv`` after
    # the X1a-fu2 retire. Fail loudly if the file is missing -- that means
    # the W1a/W1b rename either hasn't landed in this worktree or the slug
    # is wrong.
    yengov_csv = ELECTORAL_DATAPOINTS_DIR / f"{state_slug}_election_results.csv"
    if not yengov_csv.exists():
        _die(
            f"yen-gov per-state CSV not found at {yengov_csv.relative_to(REPO_ROOT)}; "
            "check the state-slug or that PR-W1a landed in this worktree."
        )

    print(f"[parity] reading yen-gov: {yengov_csv.relative_to(REPO_ROOT)}", file=sys.stderr)
    yengov_winners = read_yengov_winners(yengov_csv, event_slug)
    print(
        f"[parity] yen-gov: {len(yengov_winners)} winner buckets for {event_slug}",
        file=sys.stderr,
    )

    print(
        f"[parity] fetching IndiaVotes for {event_slug} / {state_slug} "
        f"(cache: {CACHE_ROOT.relative_to(REPO_ROOT)})",
        file=sys.stderr,
    )
    try:
        html_paths = fetch_state_event(
            event_slug,
            state_slug,
            cache_root=CACHE_ROOT,
            force_refetch=args.force_refetch,
        )
    except Exception as exc:  # noqa: BLE001 -- broad by design; degrade gracefully
        print(
            f"[parity] IndiaVotes fetch FAILED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print(
            "[parity] degrade to the synthetic-fixture path: pass "
            "--fixture-html <path> to skip the network probe.",
            file=sys.stderr,
        )
        if args.fixture_html is None:
            return 2
        html_paths = [Path(args.fixture_html)]

    if args.fixture_html is not None:
        # Operator-pinned fixture overrides cache (G1-EVIDENCE path).
        html_paths = [Path(args.fixture_html)]

    indiavotes_winners = parse_winners(html_paths)
    print(
        f"[parity] IndiaVotes: parsed {len(indiavotes_winners)} winner rows "
        f"from {len(html_paths)} page(s)",
        file=sys.stderr,
    )

    name_map = _load_yengov_name_map(ENTITIES_JSON, state_slug)
    diff_rows = compute_diff(
        indiavotes_winners,
        yengov_winners,
        state_slug=state_slug,
        event_slug=event_slug,
        yengov_name_by_entity_id=name_map,
    )
    pct = agreement_pct(diff_rows)
    print(
        f"[parity] agreement: {pct:.1f}% across "
        f"{len({r['constituency_name'] for r in diff_rows})} distinct constituencies",
        file=sys.stderr,
    )

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(diff_rows)
    print(
        f"[parity] wrote {len(diff_rows)} rows -> "
        f"{output_path.relative_to(REPO_ROOT).as_posix()}",
        file=sys.stderr,
    )
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="elections_parity_indiavotes",
        description=(
            "One-shot offline parity oracle: yen-gov per-state election CSV "
            "vs IndiaVotes scraped HTML. NEVER CI. See README for rationale."
        ),
    )
    parser.add_argument(
        "--event",
        required=True,
        help="Event slug, e.g. 'general-2024' or 'assembly-2023'.",
    )
    parser.add_argument(
        "--state",
        required=True,
        help="State slug, e.g. 'chhattisgarh' or 'andhra-pradesh'.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help=(
            "Output CSV path. Relative paths resolve against the repo root. "
            "Convention: datasets/_ops/elections-parity-vs-indiavotes-YYYY-MM-DD.csv"
        ),
    )
    parser.add_argument(
        "--force-refetch",
        action="store_true",
        help="Bypass the 7-day cache window and re-fetch IndiaVotes.",
    )
    parser.add_argument(
        "--fixture-html",
        default=None,
        help=(
            "Path to a local IndiaVotes-shaped HTML fixture. Bypasses the "
            "live fetch. Used by the synthetic G1-EVIDENCE path when "
            "IndiaVotes is unreachable."
        ),
    )
    return parser.parse_args(argv)


def _load_state_slugs(entities_json: Path) -> set[str]:
    """Read entities.json and return the set of state display-name slugs."""

    data = json.loads(entities_json.read_text(encoding="utf-8"))
    slugs: set[str] = set()
    for entity in data.get("entities", []):
        if entity.get("entity_type") == "state":
            display = entity.get("display_name", "")
            slugs.add(_slugify(display))
    return slugs


def _load_yengov_name_map(entities_json: Path, state_slug: str) -> dict[str, str]:
    """Return ``{entity_id: display_name}`` for AC + PC in the requested state.

    The constituency display names live in
    ``datasets/data/entities/electoral.csv`` (the canonical store), but the
    cross-walk from state-slug to ECI state-code (``S26`` for chhattisgarh)
    flows through entities.json. We do the lookup once per CLI invocation.
    """

    data = json.loads(entities_json.read_text(encoding="utf-8"))
    state_code = None
    for entity in data.get("entities", []):
        if entity.get("entity_type") == "state" and _slugify(entity.get("display_name", "")) == state_slug:
            state_code = entity.get("entity_code")
            break
    if state_code is None:
        return {}

    electoral_csv = REPO_ROOT / "datasets" / "data" / "entities" / "electoral.csv"
    if not electoral_csv.exists():
        return {}
    out: dict[str, str] = {}
    state_token = f"-{state_code}-"
    with electoral_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            entity_id = row.get("entity_id", "")
            if state_token not in entity_id:
                continue
            out[entity_id] = row.get("name", "")
    return out


def _slugify(text: str) -> str:
    return text.strip().lower().replace(" ", "-").replace("&", "and")


def _die(msg: str) -> None:
    print(f"[parity] FATAL: {msg}", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
