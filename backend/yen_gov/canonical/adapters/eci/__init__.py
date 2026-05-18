"""ECI adapter — canonical emitter for ECI per-AC + per-state-party results.

Wraps the existing parsers under ``yen_gov.sources.eci.*``. The parsers already
do the hard HTML work; this adapter:

  1. Takes a parsed ConstituencyResult (one AC contest) plus event/state context.
  2. Resolves yen-gov canonical entity_ids (AC, candidate, party, state) per
     docs/architecture/data/canonical-store.md §3a.
  3. Emits per-candidate + materialised per-AC ObservationRows per
     docs/architecture/data/elections-indicators.md.
  4. Returns rows ready to bundle into a BatchEnvelope.

Per-state rollups (party-* and state-* indicators) are computed in
``rollups.py`` after all AC contests for the state are emitted.

Public surface kept narrow — `observations_from_constituency`,
`state_rollup_observations`, plus the identity helpers in ``identity``.
"""

from yen_gov.canonical.adapters.eci.identity import (
    ac_entity_id,
    candidate_entity_id,
    parse_period_label,
    party_rollup_entity_id,
    state_rollup_entity_id,
)
from yen_gov.canonical.adapters.eci.observations import (
    dim_rows_from_constituency,
    observations_from_constituency,
)
from yen_gov.canonical.adapters.eci.party_lookup import (
    PartyLookup,
    load_party_lookup,
    party_dim_rows,
)
from yen_gov.canonical.adapters.eci.rollups import state_rollup_observations

__all__ = [
    "PartyLookup",
    "ac_entity_id",
    "candidate_entity_id",
    "dim_rows_from_constituency",
    "load_party_lookup",
    "observations_from_constituency",
    "parse_period_label",
    "party_dim_rows",
    "party_rollup_entity_id",
    "state_rollup_entity_id",
    "state_rollup_observations",
]
