"""IndiaVotes HTML scraper for the parity oracle.

Single-threaded, 1 req/sec, cache-first. Honours robots.txt-style etiquette
(low rate, citizen UA, no cookies). Never wired into CI; never imported from
the citizen pipeline. See README for the doctrinal "never CI" rationale.

Public surface:
- ``fetch_state_event(event_slug, state_slug, *, cache_root, force_refetch)``
  -> ``list[Path]`` of cached HTML page paths (one or more pages per state).
- ``parse_winners(html_paths)`` -> ``list[dict]`` of canonical winner rows.

The cache is keyed by ``<cache_root>/<YYYY-MM-DD>/<event>/<state>/<page>.html``
so re-runs on the same day are zero network traffic and a per-day refresh is
trivial. The CLI sets ``cache_root`` to
``datasets/ephemeral/indiavotes-snapshots/``; the ephemeral tier is gitignored.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "yen-gov-parity-oracle/0.1 "
    "(one-shot citizen audit; contact via github.com/yen-gov/yen-gov)"
)
REQUEST_INTERVAL_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 30.0
CACHE_MAX_AGE_DAYS = 7

# URL templates per body. IndiaVotes ships under at least two stable URL
# shapes; both keep the state-slug lowercase + hyphenated and the year as
# 4-digit YYYY. If a state's actual landing page diverges (e.g. NCT of Delhi
# slug shape), the operator must adjust this template in-place; the README
# documents the maintenance path.
URL_TEMPLATE_GENERAL = "https://www.indiavotes.com/lok-sabha/{year}/{state}"
URL_TEMPLATE_ASSEMBLY = "https://www.indiavotes.com/vidhan-sabha/{state}/{year}"


@dataclass(frozen=True)
class ResolvedTarget:
    """Resolved URL + cache path for one (event, state) probe."""

    url: str
    cache_path: Path
    event_slug: str
    state_slug: str


# Event-slug -> (body, year). Matches the PR-0 regex
# ``^(general|assembly)(-bye-[a-z0-9-]+|-\d{4})$`` for the non-bye case.
EVENT_REGEX = re.compile(r"^(general|assembly)-(\d{4})$")


def resolve_target(event_slug: str, state_slug: str, *, cache_root: Path) -> ResolvedTarget:
    """Translate an event-slug + state-slug into a URL + cache path."""

    match = EVENT_REGEX.match(event_slug)
    if not match:
        msg = (
            f"event_slug {event_slug!r} does not match the non-bye grammar "
            f"^(general|assembly)-\\d{{4}}$ (PR-0 contract). Bye-elections "
            "are out of scope for the v0.1 oracle."
        )
        raise ValueError(msg)
    body, year = match.group(1), match.group(2)
    if body == "general":
        url = URL_TEMPLATE_GENERAL.format(year=year, state=state_slug)
    else:
        url = URL_TEMPLATE_ASSEMBLY.format(state=state_slug, year=year)
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    cache_path = cache_root / today / event_slug / state_slug / "page-1.html"
    return ResolvedTarget(
        url=url,
        cache_path=cache_path,
        event_slug=event_slug,
        state_slug=state_slug,
    )


def _cache_is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now(tz=timezone.utc).timestamp() - path.stat().st_mtime
    return age < CACHE_MAX_AGE_DAYS * 86400


def fetch_state_event(
    event_slug: str,
    state_slug: str,
    *,
    cache_root: Path,
    force_refetch: bool = False,
) -> list[Path]:
    """Fetch the IndiaVotes page(s) for (event, state) into ``cache_root``.

    Returns the list of cached HTML page paths. Caller is responsible for
    feeding them to ``parse_winners``.

    Politeness invariants enforced here:
    - One state landing page per call (no recursive scrape).
    - 1 req/sec single-threaded.
    - Cache-first: ``CACHE_MAX_AGE_DAYS`` skip-window.
    - Citizen UA; no Cookie / Referer / yen-gov-tagged headers.

    Raises ``httpx.HTTPStatusError`` on 4xx/5xx so the CLI can degrade to
    G1-EVIDENCE (synthetic fixture) per the brief.
    """

    target = resolve_target(event_slug, state_slug, cache_root=cache_root)
    if _cache_is_fresh(target.cache_path) and not force_refetch:
        return [target.cache_path]
    target.cache_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, headers=headers) as client:
        time.sleep(REQUEST_INTERVAL_SECONDS)
        response = client.get(target.url, follow_redirects=True)
        response.raise_for_status()
    target.cache_path.write_text(response.text, encoding="utf-8")
    return [target.cache_path]


def parse_winners(html_paths: Iterable[Path]) -> list[dict]:
    """Parse cached IndiaVotes HTML pages into canonical winner rows.

    Output row shape (string fields; ints where natural):

        {
          "constituency_name": str,   # IndiaVotes display name, trimmed
          "winner_name": str,         # candidate name (no party suffix)
          "winner_party": str,        # raw party abbreviation extracted from
                                       # the candidate cell or the party column
          "votes": int | None,        # raw vote count, or None when IV publishes
                                       # a percentage (vote-share / vote-margin %)
                                       # that does not equate to yen-gov's raw count
          "margin": int | None,
        }

    IndiaVotes today (2026-06) ships state landing pages with the column
    layout ``['Constituency', 'Winner', 'Vote share', 'Margin over runner-up']``
    where the winner cell carries the party abbreviation in parens:
    ``'MAHESH KASHYAP(BJP)'``. We pull the party out of the candidate text
    when there is no dedicated Party column. Vote share / margin-pct are
    NOT comparable to yen-gov's raw vote counts, so we drop them into
    ``None`` rather than mis-coerce.

    Tolerant by design: an IndiaVotes layout shift should degrade gracefully
    (skip the unparseable row, keep the parseable ones). Skipped rows do NOT
    raise; they are silently dropped. Hard failure is reserved for missing
    files / malformed HTML.
    """

    rows: list[dict] = []
    for html_path in html_paths:
        html = html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "lxml")
        target_table = _find_results_table(soup)
        if target_table is None:
            continue
        header_index = _index_header_columns(target_table)
        if "constituency" not in header_index:
            continue
        for tr in target_table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue
            row = _extract_row(cells, header_index)
            if row is None:
                continue
            rows.append(row)
    return rows


def _find_results_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        header_cells = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if any("constituency" in cell for cell in header_cells):
            return table
    return None


def _index_header_columns(table) -> dict[str, int]:
    """Build a {normalised_header_label: column_index} map.

    Header tokens are matched on substrings so minor IndiaVotes wording
    drift (e.g. ``Winning candidate`` vs ``Winner``) keeps working. Vote
    SHARE (a %age) and Margin-over-runner-up (a %age + runner-up party)
    are NOT mapped to ``votes`` / ``margin``: IV's published columns are
    percentages and do not equate to yen-gov's raw counts. The operator
    eyeballs them in the CSV via the ``winner_name`` cell when needed.
    """

    index: dict[str, int] = {}
    headers = table.find_all("th")
    for i, th in enumerate(headers):
        label = th.get_text(strip=True).lower()
        if "constituency" in label:
            index["constituency"] = i
        elif label in ("winner", "winning candidate", "candidate"):
            index["winner_name"] = i
        elif "party" in label:
            index["winner_party"] = i
    return index


_PARTY_IN_CANDIDATE_RE = re.compile(r"^(?P<name>.*?)\((?P<party>[A-Za-z0-9_\-+]+)\)\s*$")
_RESERVATION_SUFFIX_RE = re.compile(r"(SC-ST|SC|ST)$")


def _split_candidate_cell(text: str) -> tuple[str, str]:
    """Split ``'MAHESH KASHYAP(BJP)'`` -> ``('MAHESH KASHYAP', 'BJP')``.

    Returns ``(text, '')`` when no party suffix is present.
    """

    if not text:
        return "", ""
    match = _PARTY_IN_CANDIDATE_RE.match(text)
    if match is None:
        return text, ""
    return match.group("name").strip(), match.group("party").strip()


def _strip_reservation_suffix(constituency: str) -> str:
    """Strip a trailing ``SC`` / ``ST`` / ``SC-ST`` reservation tag.

    IndiaVotes glues the reservation onto the constituency name with no
    separator (``BastarST``). yen-gov's electoral.csv carries the
    reservation in a separate column (``reservation``). Strip the suffix
    here so the constituency-name join key is stable across sources.
    """

    if not constituency:
        return constituency
    return _RESERVATION_SUFFIX_RE.sub("", constituency).strip()


def _extract_row(cells, header_index: dict[str, int]) -> dict | None:
    def get(name: str) -> str | None:
        idx = header_index.get(name)
        if idx is None or idx >= len(cells):
            return None
        return cells[idx].get_text(strip=True)

    constituency_raw = get("constituency")
    if not constituency_raw:
        return None
    constituency = _strip_reservation_suffix(constituency_raw)
    winner_text = get("winner_name") or ""
    winner_name, party_in_name = _split_candidate_cell(winner_text)
    winner_party = get("winner_party") or party_in_name
    return {
        "constituency_name": constituency,
        "winner_name": winner_name,
        "winner_party": winner_party,
        "votes": None,
        "margin": None,
    }
