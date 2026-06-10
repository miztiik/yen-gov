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
import re
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
ENTITIES_JSON = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"

# Event-slug regex pin lives here (single place); diff.py is grammar-free
# now that the surface flip (PR-W1c fix-up, 2026-06-10) put body + year
# into the file-path partition instead of a row column. Matches the PR-0
# non-bye grammar: ``general-YYYY`` / ``assembly-YYYY``.
_EVENT_REGEX = re.compile(r"^(general|assembly)-(\d{4})$")

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


def _resolve_summary_csv_path(
    event_slug: str,
    state_slug: str,
    *,
    repo_root: Path,
) -> Path:
    """Translate (event_slug, state_slug) into the canonical summary.csv path.

    For general events: ``datasets/elections/parliament/election=<year>/summary.csv``
    (parliament summary is national-scope; the reader filters by state).

    For assembly events: ``datasets/elections/assembly/state=<slug>/election=<year>/summary.csv``
    (the path partition already pins the state).

    Bye-elections are out of v0.1 scope (pinned by the PR-0 grammar in
    ``docs/architecture/frontend/url-grammar.md``); they require event-id
    grain URLs and a separate per-bye summary.csv shape.
    """

    match = _EVENT_REGEX.fullmatch(event_slug)
    if not match:
        msg = (
            f"event_slug {event_slug!r}: bye-elections out of v0.1 scope; "
            "pinned by PR-0 grammar ^(general|assembly)-\\d{4}$."
        )
        raise ValueError(msg)
    body, year = match.group(1), match.group(2)
    if body == "general":
        return (
            repo_root
            / "datasets"
            / "elections"
            / "parliament"
            / f"election={year}"
            / "summary.csv"
        )
    return (
        repo_root
        / "datasets"
        / "elections"
        / "assembly"
        / f"state={state_slug}"
        / f"election={year}"
        / "summary.csv"
    )


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

    # Resolve the canonical summary.csv path from (event, state). Fail
    # loudly if missing -- that means either the event has not been
    # ingested yet OR the slug is wrong.
    try:
        summary_csv = _resolve_summary_csv_path(
            event_slug, state_slug, repo_root=REPO_ROOT
        )
    except ValueError as exc:
        _die(str(exc))
        return 2  # unreachable; _die raises
    if not summary_csv.exists():
        _die(
            f"canonical summary.csv not found at "
            f"{summary_csv.relative_to(REPO_ROOT).as_posix()}; "
            "check the state-slug + event-slug; the event may not be "
            "ingested in this worktree."
        )

    print(
        f"[parity] reading yen-gov: {summary_csv.relative_to(REPO_ROOT).as_posix()}",
        file=sys.stderr,
    )
    yengov_winners = read_yengov_winners(summary_csv, event_slug, state_slug)
    print(
        f"[parity] yen-gov: {len(yengov_winners)} winner rows for {event_slug} / {state_slug}",
        file=sys.stderr,
    )

    print(
        f"[parity] fetching IndiaVotes for {event_slug} / {state_slug} "
        f"(cache: {CACHE_ROOT.relative_to(REPO_ROOT).as_posix()})",
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

    diff_rows = compute_diff(
        indiavotes_winners,
        yengov_winners,
        state_slug=state_slug,
        event_slug=event_slug,
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
            "One-shot offline parity oracle: yen-gov canonical summary.csv "
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


def _slugify(text: str) -> str:
    return text.strip().lower().replace(" ", "-").replace("&", "and")


def _die(msg: str) -> None:
    print(f"[parity] FATAL: {msg}", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
