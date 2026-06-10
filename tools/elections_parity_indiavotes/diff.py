"""Pure diff engine and yen-gov CSV reader for the parity oracle.

Splits cleanly into:

- ``read_yengov_winners(csv_path, event_slug)`` -> ``list[dict]`` of canonical
  winner rows pulled from the per-state long-format CSV.
- ``compute_diff(indiavotes_winners, yengov_winners)`` -> ``list[dict]`` of
  per-constituency delta rows, one row per UNION key (so the operator sees
  agreements AND disagreements, not just deltas).

No I/O outside ``read_yengov_winners``. No imports from ``backend/``. The
diff engine is unit-testable in isolation against tiny synthetic fixtures.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

# Event-slug -> period_label regex inside the per-state CSV. Today's data
# uses ECI event labels like ``LsGenJun2024`` (general 2024) and
# ``AcGenJun2024`` (assembly 2024). The oracle matches by the year-suffix
# only; this avoids hardcoding the publisher's per-event month token, which
# differs across years (LsGenApr2019 vs LsGenJun2024) and across states for
# assembly elections.
EVENT_GRAMMAR = re.compile(r"^(general|assembly)-(\d{4})$")

_BODY_TO_PREFIX = {"general": "LsGen", "assembly": "AcGen"}


def period_label_matcher(event_slug: str):
    """Return a predicate ``str -> bool`` over ``period_label`` strings.

    The predicate is True when the period_label matches the requested
    event-slug. For ``general-2024`` this accepts any ``LsGen*2024`` label;
    for ``assembly-2023`` any ``AcGen*2023`` label. Bye-elections are out of
    scope for v0.1.
    """

    match = EVENT_GRAMMAR.match(event_slug)
    if not match:
        msg = (
            f"event_slug {event_slug!r} does not match ^(general|assembly)-\\d{{4}}$ "
            "(PR-0 contract; bye-elections out of v0.1 scope)."
        )
        raise ValueError(msg)
    body, year = match.group(1), match.group(2)
    prefix = _BODY_TO_PREFIX[body]
    pattern = re.compile(rf"^{prefix}[A-Za-z]+{year}$")
    return pattern.fullmatch


def read_yengov_winners(csv_path: Path, event_slug: str) -> list[dict]:
    """Read yen-gov per-state CSV; return one winner row per constituency.

    Output row shape (mirrors ``scrape.parse_winners``):

        {
          "entity_id": str,           # e.g. "IN-PC-2008-S26-1"
          "winner_name": str,         # CANDIDATE id (yen-gov has IDs, not names yet)
          "winner_party": str,        # "parties.IN.BJP"
          "votes": int | None,        # pc-votes-polled (constituency total turnout)
          "margin": int | None,       # pc-margin-votes
        }

    Yen-gov rows are stored in long format; this function pivots the
    relevant indicator_ids per (entity_id, period_label) bucket and returns
    one row per entity.
    """

    matches_period = period_label_matcher(event_slug)
    body = event_slug.split("-")[0]
    indicator_prefix = "pc" if body == "general" else "ac"

    indicator_keys = {
        f"{indicator_prefix}-winner-candidate-id": "winner_name",
        f"{indicator_prefix}-winner-party-id": "winner_party",
        f"{indicator_prefix}-votes-polled": "votes",
        f"{indicator_prefix}-margin-votes": "margin",
    }

    buckets: dict[str, dict] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not matches_period(row.get("period_label", "")):
                continue
            indicator_id = row.get("indicator_id", "")
            field = indicator_keys.get(indicator_id)
            if field is None:
                continue
            entity_id = row["entity_id"]
            bucket = buckets.setdefault(
                entity_id,
                {
                    "entity_id": entity_id,
                    "winner_name": "",
                    "winner_party": "",
                    "votes": None,
                    "margin": None,
                },
            )
            text = (row.get("value_text") or "").strip()
            numeric = (row.get("value_numeric") or "").strip()
            if field in ("votes", "margin"):
                try:
                    bucket[field] = int(float(numeric)) if numeric else None
                except ValueError:
                    bucket[field] = None
            else:
                bucket[field] = text
    return list(buckets.values())


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


def _eci_no_from_entity_id(entity_id: str) -> str:
    """Extract the trailing ECI constituency number from an entity_id.

    Entity ids follow ``IN-PC-<delim_year>-S<state>-<eci_no>`` /
    ``IN-AC-<delim_year>-S<state>-<eci_no>``. Returns the ``eci_no`` tail
    as a string (preserves leading zeros if any).
    """

    return entity_id.rsplit("-", 1)[-1] if entity_id else ""


def compute_diff(
    indiavotes_winners: list[dict],
    yengov_winners: list[dict],
    *,
    state_slug: str,
    event_slug: str,
    yengov_name_by_entity_id: dict[str, str] | None = None,
) -> list[dict]:
    """Return one delta row per UNION constituency.

    Join key is the normalised constituency name. yen-gov rows are keyed by
    entity_id, but the data store currently does NOT carry a winner-NAME
    column for constituencies (only candidate IDs). To join against
    IndiaVotes the caller passes ``yengov_name_by_entity_id`` derived from
    ``datasets/data/entities/electoral.csv``. If the lookup is empty, the
    diff degrades to "IndiaVotes-only" rows -- still useful for surfacing
    that no yen-gov match was found.

    Output columns match the CSV emitted by ``__main__``:

        state, event, constituency_name, source, winner_party, winner_name,
        votes, margin, agrees, delta_notes

    ``source`` is ``indiavotes`` or ``yen-gov``; ``agrees`` is True iff
    BOTH sides agree on the normalised winning party for the same
    constituency-name key. Rows where only one side reports a winner are
    emitted with ``agrees=False`` and a descriptive ``delta_notes``.
    """

    name_map: dict[str, str] = yengov_name_by_entity_id or {}

    yengov_by_key: dict[str, dict] = {}
    for row in yengov_winners:
        entity_id = row["entity_id"]
        display = name_map.get(entity_id, "")
        key = normalise_name(display) if display else _eci_no_from_entity_id(entity_id)
        if not key:
            continue
        yengov_by_key[key] = {**row, "display_name": display or entity_id}

    iv_by_key: dict[str, dict] = {
        normalise_name(row["constituency_name"]): row for row in indiavotes_winners
    }

    out: list[dict] = []
    all_keys = sorted(set(yengov_by_key) | set(iv_by_key))
    for key in all_keys:
        iv = iv_by_key.get(key)
        yg = yengov_by_key.get(key)
        if iv is not None and yg is not None:
            agrees = normalise_party(iv["winner_party"]) == normalise_party(yg["winner_party"])
            delta_notes = "" if agrees else "party mismatch"
            display = yg["display_name"] or iv["constituency_name"]
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
                    yg["display_name"],
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
    return {
        "state": state_slug,
        "event": event_slug,
        "constituency_name": constituency_name,
        "source": source,
        "winner_party": record.get("winner_party", ""),
        "winner_name": record.get("winner_name", ""),
        "votes": record.get("votes") if record.get("votes") is not None else "",
        "margin": record.get("margin") if record.get("margin") is not None else "",
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
