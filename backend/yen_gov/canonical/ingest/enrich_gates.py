"""The six India-discontinuity ENRICH gates (Row 6, plan section 3).

India's administrative + statistical reality breaks at seams a generic
ingestion engine would silently paper over. Each gate below RAISES a typed
error on bad input rather than best-guessing -- the engineering contract's
fail-fast-at-the-boundary rule (CLAUDE.md Holy Law #5). They run in ENRICH,
after the raw cell is parsed but before it becomes a canonical row, where the
publisher's verbatim entity/period labels and the resolution context are still
in hand.

The six (plan section 3 "India-discontinuity enrich gates"):

1. **bifurcation** -- Andhra/Telangana 2014 is an id-REUSE: ``IN-S01``
   (andhra-pradesh) stays valid across the split. But Telangana did NOT exist
   before 2014, and Jammu & Kashmir ceased to be a STATE in 2019 (it became a
   UT, with Ladakh splitting off). A pre-2014 Telangana row or a post-2019
   "J&K state" row is a category error -> FAIL (or be force-tagged by an
   explicit operator acknowledgement).
2. **code-authority** -- an entity label MUST resolve through ONE issuing
   authority (LGD / Census / ECI) to ONE code. An unmapped label or an
   ambiguous multi-candidate match FAILS; the engine never best-guesses which
   district a colliding name means.
3. **fiscal-year != calendar-year** -- a fiscal-year series ("2015-16") MUST
   anchor to its fiscal-year-start integer (2015), consistently. Treating a
   fiscal label as a calendar year (or mixing the two) FAILS.
4. **provisional-vs-revised** -- an estimate carries a status
   (provisional/first_release -> revised -> final). A provisional value MUST
   NOT silently overwrite an already-final one (a downgrade); the status ties
   to the year-checkpoint's ``estimate_status`` so a re-open is honest.
5. **price-basis** -- a constant-price (real) value MUST NOT be UPSERTed into a
   current-price (nominal) cell. The two are different facts; splicing them is a
   lie the gate refuses.
6. **publisher-bounded-universe** -- when a publisher only covers a bounded set
   of entities, the engine MUST NOT synthesise phantom rows for the entities it
   omits. An entity outside the declared universe FAILS.

Each gate is a pure function (no I/O); the inputs that need pre-canonicalisation
context (raw labels, resolution candidates, estimate status) are passed
explicitly so the gates stay unit-testable without walking the corpus. The
publish-seam composite in the orchestrator invokes the subset checkable on a
canonical batch + concept (price-basis, bifurcation, bounded-universe); the
label/period/status gates serve the ENRICH stage of a batch-producing adapter.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from yen_gov.canonical.ingest.spec import PriceBasis


class EnrichGateError(Exception):
    """Base for the India-discontinuity ENRICH gate violations."""


class BifurcationError(EnrichGateError):
    """A row attributes an observation to a state outside its administrative lifespan."""


class CodeAuthorityError(EnrichGateError):
    """An entity label is unmapped or ambiguously mapped across code authorities."""


class FiscalCalendarError(EnrichGateError):
    """A fiscal-year period was treated as (or mixed with) a calendar year."""


class EstimateStatusError(EnrichGateError):
    """A provisional estimate would silently overwrite a more-final one."""


class PriceBasisError(EnrichGateError):
    """A constant-price value would be UPSERTed into a current-price cell."""


class PublisherBoundedUniverseError(EnrichGateError):
    """A row was synthesised for an entity outside the publisher's bounded universe."""


# --------------------------------------------------------------------------- #
# (1) bifurcation / state-lifespan
# --------------------------------------------------------------------------- #


class StateLifespan(BaseModel):
    """The administrative lifespan of a re-organised state, as a fail rule.

    ``born`` is the first year the entity legally exists as a distinct unit (a
    row earlier than this is a category error). ``state_dissolved`` is the first
    year the entity is no longer a STATE (a ``state``-kind row at or after this
    is a category error -- the unit became a UT). ``None`` on either side means
    "no constraint on that edge".
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    born: int | None = None
    state_dissolved: int | None = None


#: The known India state re-organisation seams the bifurcation gate enforces.
#: andhra-pradesh is DELIBERATELY ABSENT: the 2014 split reused ``IN-S01`` for
#: the residual state, so andhra-pradesh rows stay valid at every year (the
#: plan's id-REUSE rule). telangana is the NEW unit (born 2014); ladakh is the
#: NEW UT (born 2019); jammu-and-kashmir stops being a STATE in 2020 (the
#: reorganisation took effect 2019-10-31, so the first fully-UT year is 2020).
STATE_LIFESPANS: dict[str, StateLifespan] = {
    "telangana": StateLifespan(born=2014),
    "ladakh": StateLifespan(born=2019),
    "jammu-and-kashmir": StateLifespan(state_dissolved=2020),
}


class EntityObservation(BaseModel):
    """An enriched candidate the bifurcation gate reasons over."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(min_length=1)
    time: int = Field(ge=1850, le=2100)
    entity_kind: str | None = None


def check_bifurcation(
    candidates: Iterable[EntityObservation],
    *,
    force_tagged: Iterable[tuple[str, int]] = (),
    lifespans: Mapping[str, StateLifespan] | None = None,
) -> None:
    """Raise :class:`BifurcationError` on a row outside a state's lifespan.

    ``force_tagged`` is the escape hatch (plan: "FAIL or be force-tagged"): an
    explicit ``(entity_id, time)`` acknowledgement permits an otherwise-illegal
    row (e.g. a deliberately back-cast Telangana series the operator vouches
    for). ``lifespans`` overrides the default table for tests.
    """
    table = dict(STATE_LIFESPANS if lifespans is None else lifespans)
    forced = {(e, t) for e, t in force_tagged}
    for cand in candidates:
        rule = table.get(cand.entity_id)
        if rule is None:
            continue
        if (cand.entity_id, cand.time) in forced:
            continue
        if rule.born is not None and cand.time < rule.born:
            raise BifurcationError(
                f"{cand.entity_id!r} did not exist before {rule.born}; a "
                f"{cand.time} row attributes an observation to a state that had "
                "not yet been formed (its territory belonged to the parent "
                "state). Re-attribute to the parent or force-tag if intentional."
            )
        if (
            rule.state_dissolved is not None
            and cand.time >= rule.state_dissolved
            and (cand.entity_kind is None or cand.entity_kind == "state")
        ):
            raise BifurcationError(
                f"{cand.entity_id!r} ceased to be a state in "
                f"{rule.state_dissolved}; a {cand.time} state-kind row is a "
                "category error (the unit was reorganised into a union "
                "territory). Use the union-territory entity or force-tag."
            )


# --------------------------------------------------------------------------- #
# (2) code-authority
# --------------------------------------------------------------------------- #

#: The issuing authorities a label may legitimately resolve through.
KNOWN_CODE_AUTHORITIES: frozenset[str] = frozenset({"lgd", "census", "eci"})


class EntityResolution(BaseModel):
    """The outcome of resolving a publisher's raw entity label to a code.

    ``resolved_entity_id`` is the single code the label mapped to (``None`` if
    nothing matched); ``candidates`` is every code the label could mean (more
    than one = ambiguous); ``authority`` is the issuing authority that produced
    the match.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_label: str = Field(min_length=1)
    resolved_entity_id: str | None = None
    candidates: tuple[str, ...] = ()
    authority: str | None = None


def check_code_authority(resolutions: Iterable[EntityResolution]) -> None:
    """Raise :class:`CodeAuthorityError` on an unmapped or ambiguous resolution.

    A label is acceptable iff it resolved to exactly one code through a known
    authority (LGD / Census / ECI). Zero candidates (unmapped), more than one
    candidate (ambiguous), a missing ``resolved_entity_id``, or an unknown
    authority all FAIL -- the engine never best-guesses an identity.
    """
    for res in resolutions:
        if res.authority is None or res.authority not in KNOWN_CODE_AUTHORITIES:
            raise CodeAuthorityError(
                f"label {res.raw_label!r} resolved through authority "
                f"{res.authority!r}, not one of {sorted(KNOWN_CODE_AUTHORITIES)}; "
                "an entity code must come from a named issuing authority."
            )
        if len(res.candidates) > 1:
            raise CodeAuthorityError(
                f"label {res.raw_label!r} is ambiguous: it matches "
                f"{list(res.candidates)} under {res.authority!r}. Refusing to "
                "best-guess which entity is meant; disambiguate upstream."
            )
        if res.resolved_entity_id is None or not res.candidates:
            raise CodeAuthorityError(
                f"label {res.raw_label!r} did not resolve to any code under "
                f"{res.authority!r}; refusing to invent an entity id."
            )
        if res.resolved_entity_id not in res.candidates:
            raise CodeAuthorityError(
                f"label {res.raw_label!r} resolved to "
                f"{res.resolved_entity_id!r} which is not among its candidate "
                f"set {list(res.candidates)}; the resolution is inconsistent."
            )


# --------------------------------------------------------------------------- #
# (3) fiscal-year != calendar-year
# --------------------------------------------------------------------------- #


def fiscal_year_start(period_label: str) -> int:
    """Parse a fiscal-year label (``2015-16`` / ``2015-2016``) to its start year.

    Raises :class:`FiscalCalendarError` if the label is not a fiscal-year span
    (e.g. a bare ``2015``) or the two halves are not consecutive years.
    """
    text = period_label.strip()
    if "-" not in text:
        raise FiscalCalendarError(
            f"{period_label!r} is not a fiscal-year span (expected e.g. "
            "'2015-16'); a bare year is a calendar label."
        )
    left, _, right = text.partition("-")
    if not left.isdigit() or not right.isdigit():
        raise FiscalCalendarError(
            f"{period_label!r} is not a parseable fiscal-year span."
        )
    start = int(left)
    end = int(right) if len(right) == 4 else (start // 100) * 100 + int(right)
    if end != start + 1:
        raise FiscalCalendarError(
            f"fiscal-year span {period_label!r} does not cover two consecutive "
            f"years (parsed start={start}, end={end})."
        )
    return start


def check_fiscal_calendar(
    period_label: str,
    time: int,
    *,
    basis: str,
) -> None:
    """Raise :class:`FiscalCalendarError` on a fiscal/calendar period mismatch.

    ``basis`` is the indicator's declared period semantics:
    ``"fiscal_year_start"`` (the canonical ``time`` MUST equal the fiscal
    year's start, so ``2015-16`` -> 2015) or ``"calendar_year"`` (the label
    MUST be a bare year equal to ``time``). The gate refuses to silently equate
    a fiscal span with a calendar year.
    """
    if basis == "fiscal_year_start":
        start = fiscal_year_start(period_label)
        if time != start:
            raise FiscalCalendarError(
                f"fiscal-year {period_label!r} starts in {start} but the row's "
                f"time is {time}; a fiscal-year series must anchor to its "
                "fiscal-year-start integer, not the end year or the calendar year."
            )
        return
    if basis == "calendar_year":
        text = period_label.strip()
        if not text.isdigit():
            raise FiscalCalendarError(
                f"calendar-year indicator got non-calendar label {period_label!r}; "
                "a fiscal span cannot be read as a calendar year."
            )
        if int(text) != time:
            raise FiscalCalendarError(
                f"calendar-year label {period_label!r} != row time {time}."
            )
        return
    raise FiscalCalendarError(
        f"unknown period basis {basis!r}; expected 'fiscal_year_start' or "
        "'calendar_year'."
    )


# --------------------------------------------------------------------------- #
# (4) provisional-vs-revised
# --------------------------------------------------------------------------- #

#: Estimate-status ranks (higher = more authoritative). ``mixed`` is a series
#: that blends releases and never downgrades a per-cell final, so it ranks with
#: revised. The enums mirror indicators.json ``revision_tier`` values.
ESTIMATE_RANK: dict[str, int] = {
    "provisional": 0,
    "first_release": 0,
    "revised": 1,
    "mixed": 1,
    "final": 2,
}


def check_estimate_status(new_status: str, prior_status: str | None) -> None:
    """Raise :class:`EstimateStatusError` on a status DOWNGRADE.

    A new value may keep or raise the estimate authority (provisional -> revised
    -> final) but MUST NOT silently downgrade it: replacing an already-``final``
    cell with a ``provisional`` one discards a settled number. ``prior_status``
    ``None`` (no incumbent) always passes. Ties to the year-checkpoint
    ``estimate_status`` (Row 2): a re-open that lowers authority is the case
    this refuses.
    """
    if prior_status is None:
        return
    if new_status not in ESTIMATE_RANK:
        raise EstimateStatusError(
            f"unknown estimate status {new_status!r}; expected one of "
            f"{sorted(ESTIMATE_RANK)}."
        )
    if prior_status not in ESTIMATE_RANK:
        raise EstimateStatusError(
            f"unknown prior estimate status {prior_status!r}; expected one of "
            f"{sorted(ESTIMATE_RANK)}."
        )
    if ESTIMATE_RANK[new_status] < ESTIMATE_RANK[prior_status]:
        raise EstimateStatusError(
            f"estimate status downgrade {prior_status!r} -> {new_status!r}: a "
            "provisional value must not silently overwrite a more-final one. "
            "Keep the final value or record the revision explicitly."
        )


# --------------------------------------------------------------------------- #
# (5) price-basis
# --------------------------------------------------------------------------- #


def check_price_basis(
    incoming: PriceBasis | None,
    expected: PriceBasis | None,
) -> None:
    """Raise :class:`PriceBasisError` when the batch price basis differs from the cell.

    The destination cell's basis is the indicator concept's declared
    ``price_basis``; the ``incoming`` basis is the batch's. A constant-price
    (real) value UPSERTed into a current-price (nominal) cell -- or any
    basis/base-year mismatch -- splices two incompatible monetary facts and
    FAILS. ``None``-vs-``None`` (non-monetary) passes.
    """
    if incoming == expected:
        return
    raise PriceBasisError(
        f"price-basis mismatch: incoming {incoming!r} would be UPSERTed into a "
        f"cell whose concept declares {expected!r}. Constant-price (real) and "
        "current-price (nominal) values are different facts and must not be "
        "spliced into one series."
    )


# --------------------------------------------------------------------------- #
# (6) publisher-bounded-universe
# --------------------------------------------------------------------------- #


def check_publisher_bounded_universe(
    batch_entities: Iterable[str],
    *,
    allowed_entities: Sequence[str] | None,
) -> None:
    """Raise :class:`PublisherBoundedUniverseError` on a phantom entity.

    When an indicator is publisher-bounded (its source only covers a fixed set
    of entities), ``allowed_entities`` is that universe and any batch entity
    outside it is a synthesised phantom -> FAIL. ``allowed_entities`` ``None``
    means the indicator is not bounded (the publisher covers the open universe),
    so the gate is a no-op.
    """
    if allowed_entities is None:
        return
    allowed = set(allowed_entities)
    phantoms = sorted({e for e in batch_entities if e not in allowed})
    if phantoms:
        raise PublisherBoundedUniverseError(
            f"batch carries {len(phantoms)} entity(ies) outside the publisher's "
            f"bounded universe: {phantoms}. The publisher does not report these; "
            "refusing to synthesise phantom rows for them."
        )


__all__ = [
    "ESTIMATE_RANK",
    "KNOWN_CODE_AUTHORITIES",
    "STATE_LIFESPANS",
    "BifurcationError",
    "CodeAuthorityError",
    "EnrichGateError",
    "EntityObservation",
    "EntityResolution",
    "EstimateStatusError",
    "FiscalCalendarError",
    "PriceBasisError",
    "PublisherBoundedUniverseError",
    "StateLifespan",
    "check_bifurcation",
    "check_code_authority",
    "check_estimate_status",
    "check_fiscal_calendar",
    "check_price_basis",
    "check_publisher_bounded_universe",
    "fiscal_year_start",
]
