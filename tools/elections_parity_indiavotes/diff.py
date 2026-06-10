"""Pure diff engine and yen-gov CSV reader for the parity oracle.

Splits cleanly into:

- ``read_yengov_winners(summary_csv_path, event_slug, state_slug)`` ->
  ``list[dict]`` of canonical winner rows pulled from the canonical
  ``datasets/elections/{parliament,assembly}/.../summary.csv`` surface.
- ``compute_diff(indiavotes_winners, yengov_winners)`` -> ``list[dict]`` of
  per-constituency delta rows, one row per UNION key (so the operator sees
  agreements AND disagreements, not just deltas).

No I/O outside ``read_yengov_winners``. No imports from ``backend/``. The
diff engine is unit-testable in isolation against tiny synthetic fixtures.

Doctrinal note (fix-up of PR-W1c, 2026-06-10): the original oracle read
the long-format per-state CSV at
``datasets/data/datapoints/electoral/<state>_election_results.csv``. That
surface uses an entity_id grammar (``IN-PC-1976-S26-1``) DIFFERENT from
the canonical PC registry at ``datasets/data/entities/electoral.csv``
(``IN-PC-2008-chhattisgarh-294``), so the two surfaces shared no
entity_id join key and the diff engine reported 0% agreement.

The new ``summary.csv`` surface carries the canonical entity_id AND a
native ``constituency_name`` column, so the diff engine joins on
constituency-name directly with no electoral.csv name-map needed.
Event year + body live in the file-path partition; the event-slug ->
path translator lives in ``__main__.py::_resolve_summary_csv_path``.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path


def read_yengov_winners(
    summary_csv_path: Path,
    event_slug: str,
    state_slug: str,
) -> list[dict]:
    """Read yen-gov canonical summary.csv; return one winner row per constituency.

    ``summary_csv_path`` is the resolved on-disk path:
      - For general events:
        ``datasets/elections/parliament/election=<year>/summary.csv``
      - For assembly events:
        ``datasets/elections/assembly/state=<state>/election=<year>/summary.csv``

    ``event_slug`` matches the PR-0 grammar (``general-2024``,
    ``assembly-2023``). For general events the function filters rows to
    ``state == state_slug`` (parliament summary.csv is national-scope on
    disk); for assembly events the path partition already filters by
    state, so the state_slug arg is forwarded onto each output row but
    not used as a filter.

    Output row shape (matches the canonical summary.csv column names so
    callers can pivot on the same vocabulary the on-disk data uses):

        {
          "entity_id": str,           # e.g. "IN-PC-2008-chhattisgarh-294"
          "state_slug": str,          # e.g. "chhattisgarh"
          "constituency_name": str,   # e.g. "BASTAR" (from summary.csv natively)
          "winner_candidate": str | None,
          "winner_party_id": str,     # e.g. "parties.IN.BJP"
          "winner_party_short": str,  # e.g. "BJP" (from winner_party_short_raw column)
          "winner_votes": int | None,
          "winner_share_pct": float | None,
          "margin_votes": int | None,
          "margin_pct": float | None,
          "runnerup_candidate": str | None,
          "runnerup_party_id": str | None,
          "runnerup_party_short": str | None,
        }

    Returns ``[]`` if ``summary_csv_path`` does not exist (caller signals
    upstream missing data, not a function bug).
    """

    if not summary_csv_path.exists():
        return []

    is_general = event_slug.startswith("general")
    out: list[dict] = []
    with summary_csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row_state = (row.get("state") or "").strip()
            if is_general and row_state != state_slug:
                continue
            out.append(
                {
                    "entity_id": (row.get("entity_id") or "").strip(),
                    "state_slug": row_state or state_slug,
                    "constituency_name": (row.get("constituency_name") or "").strip(),
                    "winner_candidate": _str_or_none(row.get("winner_candidate")),
                    "winner_party_id": (row.get("winner_party_id") or "").strip(),
                    "winner_party_short": (row.get("winner_party_short_raw") or "").strip(),
                    "winner_votes": _int_or_none(row.get("winner_votes")),
                    "winner_share_pct": _float_or_none(row.get("winner_share_pct")),
                    "margin_votes": _int_or_none(row.get("margin_votes")),
                    "margin_pct": _float_or_none(row.get("margin_pct")),
                    "runnerup_candidate": _str_or_none(row.get("runnerup_candidate")),
                    "runnerup_party_id": _str_or_none(row.get("runnerup_party_id")),
                    "runnerup_party_short": _str_or_none(row.get("runnerup_party_short_raw")),
                }
            )
    return out


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


# --- diff engine ------------------------------------------------------------


_PARTY_SLUG_RE = re.compile(r"[^a-z0-9]+")


def normalise_party(party: str) -> str:
    """Normalise a party token for comparison.

    yen-gov publishes party identifiers as ``parties.IN.BJP`` (FK shape);
    IndiaVotes ships display abbreviations like ``BJP`` / ``INC`` / ``BSP``.
    For oracle purposes we extract the alpha-numeric tail and lowercase it.
    Lowercase FIRST so the [^a-z0-9] strip preserves alpha tokens.
    """

    if not party:
        return ""
    # Take the trailing token after a dot (handles ``parties.IN.BJP``).
    tail = party.rsplit(".", 1)[-1]
    return _PARTY_SLUG_RE.sub("", tail.lower())


def normalise_name(name: str) -> str:
    """Normalise a constituency display name for join-keying.

    Constituency names are the one column both sides print verbatim. Lower
    FIRST, then strip punctuation + runs of whitespace; the result is the
    join key.
    """

    if not name:
        return ""
    return _PARTY_SLUG_RE.sub("", name.lower())


def compute_diff(
    indiavotes_winners: list[dict],
    yengov_winners: list[dict],
    *,
    state_slug: str,
    event_slug: str,
) -> list[dict]:
    """Return one delta row per UNION constituency.

    Join key is the normalised constituency name. The new canonical
    summary.csv surface (PR-W1c fix-up, 2026-06-10) carries
    ``constituency_name`` natively, so no electoral.csv name-map JOIN is
    required on the yen-gov side; both inputs are joined symmetrically
    on ``normalise_name(constituency_name)``.

    Output columns match the CSV emitted by ``__main__``:

        state, event, constituency_name, source, winner_party, winner_name,
        votes, margin, agrees, delta_notes

    ``source`` is ``indiavotes`` or ``yen-gov``; ``agrees`` is True iff
    BOTH sides agree on the normalised winning party for the same
    constituency-name key. Rows where only one side reports a winner are
    emitted with ``agrees=False`` and a descriptive ``delta_notes``.

    Input shapes:

      indiavotes_winners[i] = {
        "constituency_name": str,
        "winner_name": str,
        "winner_party": str,
        "votes": int | None,
        "margin": int | None,
      }

      yengov_winners[i] = read_yengov_winners(...) row, carrying
        ``constituency_name`` + ``winner_party_id`` + ``winner_candidate``
        + ``winner_votes`` + ``margin_votes`` (canonical summary.csv
        column names).
    """

    yengov_by_key: dict[str, dict] = {}
    for row in yengov_winners:
        display = (row.get("constituency_name") or "").strip()
        key = normalise_name(display)
        if not key:
            continue
        yengov_by_key[key] = row

    iv_by_key: dict[str, dict] = {
        normalise_name(row["constituency_name"]): row for row in indiavotes_winners
    }

    out: list[dict] = []
    all_keys = sorted(set(yengov_by_key) | set(iv_by_key))
    for key in all_keys:
        iv = iv_by_key.get(key)
        yg = yengov_by_key.get(key)
        if iv is not None and yg is not None:
            agrees = normalise_party(iv["winner_party"]) == normalise_party(
                yg.get("winner_party_id", "")
            )
            delta_notes = "" if agrees else "party mismatch"
            display = (
                yg.get("constituency_name") or iv["constituency_name"]
            )
            out.append(
                _row(state_slug, event_slug, display, "indiavotes", iv, agrees, delta_notes)
            )
            out.append(
                _row(state_slug, event_slug, display, "yen-gov", yg, agrees, delta_notes)
            )
        elif iv is not None:
            out.append(
                _row(
                    state_slug,
                    event_slug,
                    iv["constituency_name"],
                    "indiavotes",
                    iv,
                    False,
                    "no yen-gov match",
                )
            )
        elif yg is not None:
            out.append(
                _row(
                    state_slug,
                    event_slug,
                    yg.get("constituency_name") or yg.get("entity_id", ""),
                    "yen-gov",
                    yg,
                    False,
                    "no indiavotes match",
                )
            )
    return out


def _row(
    state_slug: str,
    event_slug: str,
    constituency_name: str,
    source: str,
    record: dict,
    agrees: bool,
    delta_notes: str,
) -> dict:
    """Build one delta-CSV row.

    ``record`` is shaped by SOURCE: IndiaVotes rows carry the legacy
    ``winner_party`` / ``winner_name`` / ``votes`` / ``margin`` keys
    (from ``scrape.parse_winners``); yen-gov rows carry the canonical
    summary.csv keys (``winner_party_id`` / ``winner_candidate`` /
    ``winner_votes`` / ``margin_votes``). The dispatch on ``source``
    keeps the output CSV column shape stable so existing _ops/ consumers
    are not broken by the PR-W1c surface flip.
    """

    if source == "yen-gov":
        winner_party = record.get("winner_party_id", "")
        winner_name = record.get("winner_candidate") or ""
        votes = record.get("winner_votes")
        margin = record.get("margin_votes")
    else:
        winner_party = record.get("winner_party", "")
        winner_name = record.get("winner_name", "")
        votes = record.get("votes")
        margin = record.get("margin")
    return {
        "state": state_slug,
        "event": event_slug,
        "constituency_name": constituency_name,
        "source": source,
        "winner_party": winner_party,
        "winner_name": winner_name,
        "votes": votes if votes is not None else "",
        "margin": margin if margin is not None else "",
        "agrees": "true" if agrees else "false",
        "delta_notes": delta_notes,
    }


def agreement_pct(rows: list[dict]) -> float:
    """Return the % of distinct constituencies where the two sides agree.

    Each constituency contributes ONE comparison even though the row set
    emits two source-rows per constituency. Single-source rows (no match
    on the other side) count as a disagreement.
    """

    seen: dict[str, bool] = {}
    for row in rows:
        key = row["constituency_name"]
        agrees = row["agrees"] == "true"
        # Once we see ``true`` for a constituency, keep it true. ``false``
        # only sticks if all rows for that key are false.
        if key not in seen:
            seen[key] = agrees
        else:
            seen[key] = seen[key] or agrees
    if not seen:
        return 0.0
    n_agree = sum(1 for v in seen.values() if v)
    return 100.0 * n_agree / len(seen)
