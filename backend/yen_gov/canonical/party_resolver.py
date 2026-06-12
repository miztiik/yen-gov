"""Central party resolver — single seam for publisher-string → canonical party_id.

Per Wave 0 / Gregor section 4 verdict (extracted into PR-1 of the 2026-06-10
electoral-data-quality plan), the resolver is centralised here so the second
publisher-string-to-id path that produced the TN-2026 AIADMK empty-party_id
bug cannot exist by accident. Every adapter imports the resolver from this
single seam and either:

  - calls the lenient CSV-backed API (``resolve`` / ``PartyResolver.resolve``)
    which returns ``parties.IN.UNK`` on miss and carries the publisher label
    in the row's ``party_short_raw`` column (CLAUDE.md section 10 "no silent
    demotion"), OR

  - calls the fail-loud API (``PartyResolver.resolve_strict`` /
    ``PartyLookup.resolve``) which raises ``UnknownPartyError`` on miss.

Two surfaces co-exist in this module by design:

  1. **CSV-backed PartyResolver** (the NEW seam, reads
     ``datasets/data/entities/parties.csv`` per Holy Law #6 and the
     long-format-CSV doctrine). The brief's public ``resolve()`` function
     and ``load_resolver()`` loader live here. The lenient
     ``parties.IN.UNK``-on-miss behaviour is the PR-3 / parity-CLI contract.

  2. **JSON-backed PartyLookup** (the LEGACY shape, reads
     ``datasets/taxonomy/parties.json``) — lifted verbatim from the now-deleted
     ``backend/yen_gov/canonical/adapters/eci/party_lookup.py``. Preserves the
     6 production callers + 5 test callers byte-identically (their behaviour
     is fail-loud + ``party_full`` kwarg + JSON-roster dim-row builders).
     Future PRs may migrate these callers to the CSV-backed resolver and the
     legacy class can then retire.

Both APIs share ``UnknownPartyError`` and the ``SENTINELS`` constants.
"""

from __future__ import annotations

import csv
import functools
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final


# --- shared constants -------------------------------------------------------

#: Canonical-id sentinels for the three CSV-rows added by PR-0 to parties.csv.
#: Lifted as importable constants per Q5 (section 0.4 of the plan-doc).
SENTINELS: Final[dict[str, str]] = {
    "UNK": "parties.IN.UNK",
    "IND": "parties.IN.IND",
    "NOTA": "parties.IN.NOTA",
}

#: Direct-import convenience for the dominant fallback sentinel.
UNK: Final[str] = SENTINELS["UNK"]


#: Upper-cased ``full`` values that never identify a real party and so MUST
#: NOT enter the by_alias index even when otherwise unique. These strings
#: appear in 60 ``parties.csv`` rows (audit 2026-06-11) as publisher-side
#: back-fill for parties whose full name was never recorded; they would
#: otherwise produce false positive resolves for any candidacy row whose
#: ``party_short_raw`` happens to equal the placeholder string. The
#: dedupe tool (``tools.dedupe_parties_csv``) mirrors this constant in its
#: own Class-B skiplist; keep the two in sync.
_SENTINEL_FULL_PLACEHOLDERS: Final[frozenset[str]] = frozenset({
    "NA'S",
    "EXPANDED PARTY NAME NOT RELEASED BY THE ECI",
    "UNKNOWN PARTY",
})


#: Default location of the long-format parties.csv on disk
#: (``datasets/data/entities/parties.csv``, schema v1.1). Resolved relative to
#: the repo root using the same ``parents[3]`` idiom as
#: ``canonical/concept_registry.py`` and ``canonical/csv_columns.py``.
DEFAULT_PARTIES_CSV: Final[Path] = (
    Path(__file__).resolve().parents[3]
    / "datasets"
    / "data"
    / "entities"
    / "parties.csv"
)


class UnknownPartyError(LookupError):
    """A party string was not resolvable to any party_id in the roster.

    Raised only from the fail-loud API surfaces (``PartyLookup.resolve``,
    ``PartyResolver.resolve_strict``). Lenient surfaces return
    ``parties.IN.UNK`` instead. Lifted verbatim from the retired
    ``adapters/eci/party_lookup.py``.
    """


# --- CSV-backed PartyResolver (the NEW seam) --------------------------------


@dataclass(frozen=True)
class PartyResolver:
    """Resolves publisher-side party strings to canonical ``party_id`` values.

    Reads ``datasets/data/entities/parties.csv`` (schema v1.1, 18 columns).
    The resolver builds three reverse indexes:

      - ``by_alias``: UPPER-cased short / full / pipe-delimited alias →
        ``party_id``. Case-insensitive at lookup time (caller upper-cases
        the input).
      - ``by_eci_code``: stringified per-party ECI code → ``party_id``
        (parties.csv ``eci_codes`` column; today scalar, future-compatible
        with pipe-delim per Q1).
      - ``by_party_id``: ``party_id`` → ``party_id`` (identity round-trip
        so callers that already hold a canonical id can validate it cheaply).

    Constructed via ``load_resolver(parties_csv)``. Frozen + lru-cached at
    the loader so the same in-memory map is shared across a backfill run.
    """

    by_alias: dict[str, str] = field(default_factory=dict)
    by_eci_code: dict[str, str] = field(default_factory=dict)
    by_party_id: dict[str, str] = field(default_factory=dict)

    def resolve(
        self,
        party_short: str | None,
        eci_code: str | None,
        is_nota: bool = False,
        is_independent: bool = False,
        scope_hint: str | None = None,
    ) -> str:
        """Return ``party_id``; returns ``parties.IN.UNK`` on miss.

        Priority: NOTA flag → independent flag → ECI code → alias match.

        ``scope_hint`` is accepted for forward compatibility with the
        time-collision rule (Q4): once parties.csv carries ``valid_from`` /
        ``valid_to`` columns and a publisher's short collides across vintages,
        the hint will pick the right row. Today (v1.1) no rows carry vintage
        columns and the hint is ignored. Callers may pass a state-code or
        period_label string today and stay forward-compatible.

        This is the LENIENT API. Callers that need fail-loud (e.g. backfills
        where an unknown party is a data-integrity event, not a UX state)
        call ``resolve_strict`` instead.
        """
        del scope_hint  # forward-compat parameter; unused at v1.1.
        if is_nota:
            return SENTINELS["NOTA"]
        if is_independent:
            return SENTINELS["IND"]
        if eci_code:
            hit = self.by_eci_code.get(eci_code.strip())
            if hit is not None:
                return hit
        if party_short:
            key = party_short.strip().upper()
            if not key:
                return UNK
            hit = self.by_alias.get(key)
            if hit is not None:
                return hit
            # The caller may already hold a canonical party_id (e.g. UPSERT
            # path from PR-3's corpus regen). Round-trip it cheaply rather
            # than treating it as an unknown alias.
            id_hit = self.by_party_id.get(party_short.strip())
            if id_hit is not None:
                return id_hit
        return UNK

    def resolve_strict(
        self,
        party_short: str | None,
        eci_code: str | None,
        is_nota: bool = False,
        is_independent: bool = False,
        scope_hint: str | None = None,
    ) -> str:
        """Same as ``resolve`` but raises ``UnknownPartyError`` on miss.

        Opt-in fail-loud surface for callers that treat an unknown party as a
        data-integrity event (Wave 0 / Doctrine #2). Keeps the locked
        deterministic-priority + fail-loud rule available even though the
        default ``resolve`` path is lenient.
        """
        pid = self.resolve(
            party_short=party_short,
            eci_code=eci_code,
            is_nota=is_nota,
            is_independent=is_independent,
            scope_hint=scope_hint,
        )
        if pid == UNK and not is_nota and not is_independent:
            raise UnknownPartyError(
                f"Cannot resolve party: short={party_short!r} "
                f"eci_code={eci_code!r}. Extend "
                f"datasets/data/entities/parties.csv aliases."
            )
        return pid


def _compute_full_collision_set(rows: list[dict]) -> set[str]:
    """Return the set of upper-cased ``full`` values that appear on more
    than one non-sentinel row in ``rows``.

    Used by ``load_resolver`` to skip ambiguous full-name fallback
    candidates (see the resolver's docstring "Collision skip" rule). Rows
    where ``is_sentinel == "true"`` (the parties.IN.UNK / parties.IN.IND /
    parties.IN.NOTA singletons) are excluded - they intentionally share
    placeholder ``full`` values (``Unresolved Party``, ``Independent``,
    ``None of the Above``) and must not be treated as a real-party
    collision.
    """
    counter: Counter[str] = Counter()
    for r in rows:
        if (r.get("is_sentinel") or "").strip().lower() == "true":
            continue
        full = (r.get("full") or "").strip().upper()
        if full:
            counter[full] += 1
    return {f for f, c in counter.items() if c > 1}


@functools.lru_cache(maxsize=4)
def load_resolver(parties_csv: Path = DEFAULT_PARTIES_CSV) -> PartyResolver:
    """Load ``datasets/data/entities/parties.csv`` into a ``PartyResolver``.

    Caches up to 4 distinct paths so tests using tmp_path don't accidentally
    share state with production-root callers. A missing file yields an empty
    resolver (every lookup returns ``parties.IN.UNK``) so caller code path
    branches are uniform.

    Each row contributes up to three groups of keys to ``by_alias``:

      1. ``short`` (upper-cased) - always added.
      2. ``aliases`` (pipe-list, upper-cased) - always added.
      3. ``full`` (upper-cased) - added as a CONDITIONAL fallback so the
         resolver can resolve publisher strings that match the canonical
         long form when no explicit alias / short is available. Three skip
         rules apply (PR-Q1 commit 2, 2026-06-12):

           - **Sentinel-placeholder skip**: ``full`` values in
             ``_SENTINEL_FULL_PLACEHOLDERS`` (``NA'S``, ``EXPANDED PARTY
             NAME NOT RELEASED BY THE ECI``, ``UNKNOWN PARTY``) never enter
             the index. ~60 rows carry one of these strings in lieu of a
             real name.
           - **Collision skip**: a ``full`` value that appears on more than
             one non-sentinel row is dropped from the fallback index.
             Today (2026-06-12) this covers 8 distinct fulls including the
             AJSU/AJSUP, JJP/JNJP, RLP/RALTP, ICSP/ICP, SKPP/SRPP, and
             AD(S)/ADAL dual-spelling pairs that defer to a Hans+Max
             curator review (see ``docs/architecture/data/party-lineage.md``).
             The dedupe tool (``tools.dedupe_parties_csv``, commit 1) had
             already retired 3 PR-952 self-duplicates; the surviving
             collisions are genuine identity questions, not authoring
             mistakes.
           - **Explicit-alias-wins skip**: a ``full`` whose upper-cased
             form is already present in the by_alias index (via a short or
             alias on ANOTHER row) does NOT overwrite that mapping. This
             preserves the priority `short / alias > full` and prevents a
             curator from accidentally creating an FK flip by adding a
             ``full`` value that collides with another party's short.

    Collisions among ``short`` / ``aliases`` keys still raise ``ValueError``
    (Holy Law #5 structural fail-loud) - a ``short`` collision is a
    parties.csv authoring bug, not a publisher-side ambiguity, and must
    be fixed at the data layer rather than papered over here. Idempotent
    same-key -> same-pid pairs from any source are fine.
    """
    by_alias: dict[str, str] = {}
    by_eci: dict[str, str] = {}
    by_pid: dict[str, str] = {}
    if not parties_csv.exists():
        return PartyResolver(
            by_alias=by_alias, by_eci_code=by_eci, by_party_id=by_pid,
        )
    with parties_csv.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    # Pre-scan to compute the set of upper-cased ``full`` values that
    # appear on more than one non-sentinel row. Those are dropped from
    # the conditional full-fallback below (see docstring).
    full_collisions = _compute_full_collision_set(rows)
    for row in rows:
        pid = (row.get("party_id") or "").strip()
        if not pid:
            continue
        # Rows missing ``short`` are skipped entirely (preserves the
        # legacy ``party_lookup_from_parties_csv`` contract validated by
        # test_assembly_results::test_party_lookup_skips_rows_missing_short_or_party_id).
        short = (row.get("short") or "").strip().upper()
        if not short:
            continue
        by_pid[pid] = pid
        keys: list[str] = [short]
        aliases_raw = (row.get("aliases") or "").strip()
        if aliases_raw:
            for alias in aliases_raw.split("|"):
                cleaned = alias.strip().upper()
                if cleaned:
                    keys.append(cleaned)
        for key in keys:
            existing = by_alias.get(key)
            if existing is not None and existing != pid:
                raise ValueError(
                    f"party_lookup collision: key {key!r} maps to both "
                    f"{existing!r} and {pid!r}; resolve by editing "
                    f"datasets/data/entities/parties.csv"
                )
            by_alias[key] = pid
        # Conditional full-name fallback (PR-Q1 commit 2 / 2026-06-12).
        # Adds the upper-cased ``full`` to by_alias only when the three
        # skip rules in the docstring all clear. Unlike the short/alias
        # block above, a collision here is NOT raised: the collision-skip
        # rule already excluded multi-row fulls, and the explicit-alias-wins
        # skip handles the case where a short/alias on another row holds
        # the same key. Both branches preserve deterministic resolution
        # without forcing a fail-loud at load time.
        full = (row.get("full") or "").strip().upper()
        if (
            full
            and full not in _SENTINEL_FULL_PLACEHOLDERS
            and full not in full_collisions
            and full not in by_alias
        ):
            by_alias[full] = pid
        eci_raw = (row.get("eci_codes") or "").strip()
        if eci_raw:
            # parties.csv today carries a scalar eci code per row;
            # pipe-delim is supported for forward compatibility (Q1).
            tokens = eci_raw.split("|") if "|" in eci_raw else [eci_raw]
            for token in tokens:
                code = token.strip()
                if not code:
                    continue
                existing = by_eci.get(code)
                if existing is not None and existing != pid:
                    raise ValueError(
                        f"eci_code collision: code {code!r} maps to both "
                        f"{existing!r} and {pid!r}; resolve by editing "
                        f"datasets/data/entities/parties.csv"
                    )
                by_eci[code] = pid
    return PartyResolver(
        by_alias=by_alias, by_eci_code=by_eci, by_party_id=by_pid,
    )


def resolve(
    party_short: str | None,
    eci_code: str | None,
    is_nota: bool = False,
    is_independent: bool = False,
    scope_hint: str | None = None,
) -> str:
    """Convenience: resolve via the default-loaded resolver.

    Reads ``DEFAULT_PARTIES_CSV`` once (lru-cached via ``load_resolver``).
    Lenient (returns ``parties.IN.UNK`` on miss). Convenient for short
    scripts + the parity-CLI adapters; production adapters typically hold
    their own resolver instance for testability.
    """
    return load_resolver().resolve(
        party_short=party_short,
        eci_code=eci_code,
        is_nota=is_nota,
        is_independent=is_independent,
        scope_hint=scope_hint,
    )


# --- LEGACY JSON-backed PartyLookup (lifted from eci/party_lookup.py) -------
#
# The legacy class + helpers are lifted verbatim into this module so all 11
# import sites can repoint at ``yen_gov.canonical.party_resolver`` and keep
# their existing fail-loud + party_full + dim-row-builder behaviour
# byte-identically. The legacy module ``adapters/eci/party_lookup.py`` is
# deleted in this PR; future PRs may migrate these callers onto the
# CSV-backed ``PartyResolver`` and retire the legacy class.


@dataclass(frozen=True)
class PartyLookup:
    """Resolves ECI-side identifiers to canonical party_ids (LEGACY).

    Lifted from ``adapters/eci/party_lookup.py``. Constructed via
    ``load_party_lookup(datasets_root)``. Pure in-memory map; safe to share
    across all batches in a backfill run. Fail-loud: ``resolve`` raises
    ``UnknownPartyError`` on miss (callers that want lenient fallback wrap
    via the existing ``_LenientPartyLookup`` shim or use ``PartyResolver``).
    """

    by_alias: dict[str, str]      # lowercase alias -> party_id
    by_eci_code: dict[str, str]   # eci numeric string -> party_id

    def resolve(
        self,
        *,
        party_full: str | None = None,
        party_short: str | None = None,
        eci_code: str | None = None,
        is_independent: bool = False,
        is_nota: bool = False,
    ) -> str:
        """Return party_id, raising UnknownPartyError if unresolvable.

        Resolution order:
            1. NOTA flag -> parties.IN.NOTA.
            2. Independent flag -> parties.IN.IND.
            3. ECI numeric code (most reliable when present).
            4. party_short alias (case-insensitive).
            5. party_full alias (case-insensitive).
        """
        if is_nota:
            return SENTINELS["NOTA"]
        if is_independent:
            return SENTINELS["IND"]
        if eci_code and eci_code in self.by_eci_code:
            return self.by_eci_code[eci_code]
        for candidate in (party_short, party_full):
            if not candidate:
                continue
            key = candidate.strip().lower()
            if key in self.by_alias:
                return self.by_alias[key]
        raise UnknownPartyError(
            f"Cannot resolve party: short={party_short!r} full={party_full!r} "
            f"eci_code={eci_code!r}. Extend datasets/taxonomy/parties.json."
        )


def load_party_lookup(datasets_root: Path) -> PartyLookup:
    """Load ``datasets/taxonomy/parties.json`` into a PartyLookup (LEGACY).

    Lifted from ``adapters/eci/party_lookup.py``. Builds both indexes in a
    single pass. Aliases include short_name + full_name + every entry in the
    explicit ``aliases`` list. The raw roster is stashed on the instance so
    ``party_dim_rows`` / ``party_alliance_dim_rows`` can emit canonical
    writer rows without a second read.
    """
    path = datasets_root / "taxonomy" / "parties.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    by_alias: dict[str, str] = {}
    by_eci: dict[str, str] = {}
    for row in raw["parties"]:
        pid = row["party_id"]
        for alias in (row["short_name"], row["full_name"], *row.get("aliases", [])):
            by_alias[alias.strip().lower()] = pid
        for code in row.get("eci_codes", []):
            by_eci[code] = pid
    lookup = PartyLookup(by_alias=by_alias, by_eci_code=by_eci)
    # Stash raw roster on the (frozen) dataclass via object.__setattr__ —
    # registry() needs it; we don't want to break the frozen-shared-safe
    # contract for the resolution path.
    object.__setattr__(lookup, "_roster", raw["parties"])
    return lookup


def party_dim_rows(lookup: PartyLookup, *, source_id: str) -> list[dict]:
    """Build dim_parties payload dicts from a loaded lookup (LEGACY).

    Lifted from ``adapters/eci/party_lookup.py``. Returns plain dicts (not
    PartyDimRow) to avoid a circular import with canonical/envelope; the
    driver wraps these in PartyDimRow before envelope construction.
    ``source_id`` is the provenance row for the parties.json registry
    itself, NOT the per-AC contest sources.
    """
    roster: list[dict] = getattr(lookup, "_roster", [])
    out: list[dict] = []
    for row in roster:
        eci_codes = row.get("eci_codes") or []
        brand = row.get("brand_colour") or {}
        symbol = row.get("election_symbol") or {}
        out.append({
            "party_id": row["party_id"],
            "eci_code": eci_codes[0] if eci_codes else None,
            "short_name": row["short_name"],
            "full_name": row["full_name"],
            "recognition": row.get("recognition"),
            "source_id": source_id,
            # PR-SYM-6b mirror columns (all nullable). Flatten the nested
            # taxonomy/parties.json objects so a single dim_parties JOIN
            # carries everything the frontend resolver + symbol chip need.
            "brand_colour_hex": brand.get("hex"),
            "brand_colour_confidence": brand.get("confidence"),
            "wikipedia_url": row.get("wikipedia_url"),
            "election_symbol_asset_path": symbol.get("asset_path"),
            # Normalise source data render_mode to canonical dim enum.
            # parties.json schema accepts the descriptive 'monochrome';
            # dim-parties.schema.json v1.1 uses the semantic 'recolourable'
            # (= consumer may tint with brand_colour_hex). Other values
            # ('source_coloured', 'silhouette') pass through unchanged.
            "election_symbol_render_mode": (
                "recolourable"
                if symbol.get("render_mode") == "monochrome"
                else symbol.get("render_mode")
            ),
        })
    return out


def party_alliance_dim_rows(lookup: PartyLookup, *, source_id: str) -> list[dict]:
    """Build dim_party_alliances payload dicts from a loaded lookup (LEGACY).

    Lifted from ``adapters/eci/party_lookup.py``. Flattens each party's
    ``alliance_history[]`` into one row per (party_id, period_label) pair.
    Parties without an ``alliance_history`` entry contribute zero rows
    (absence rather than nulls). An explicit
    ``{"period_label": ..., "alliance": null}`` history entry surfaces as a
    row with alliance=None — that is "non-aligned this event", distinct from
    "alliance was never declared".
    """
    roster: list[dict] = getattr(lookup, "_roster", [])
    out: list[dict] = []
    for row in roster:
        history = row.get("alliance_history") or []
        for entry in history:
            out.append({
                "party_id": row["party_id"],
                "short_name": row["short_name"],
                "period_label": entry["period_label"],
                "alliance": entry.get("alliance"),
                "source_id": source_id,
            })
    return out


__all__ = [
    # NEW CSV-backed public API (the brief's surface)
    "DEFAULT_PARTIES_CSV",
    "PartyResolver",
    "SENTINELS",
    "UNK",
    "UnknownPartyError",
    "load_resolver",
    "resolve",
    # LEGACY JSON-backed surface (lifted from eci/party_lookup.py)
    "PartyLookup",
    "load_party_lookup",
    "party_alliance_dim_rows",
    "party_dim_rows",
]
