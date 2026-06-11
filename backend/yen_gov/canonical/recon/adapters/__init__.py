"""Per-source parity adapter registry.

Two parallel adapter contracts live here:

  - ``ParityAdapter`` (registered in ``REGISTRY``) - the per-PARTY-ROSTER
    shape: adapters return ``Iterable[ShapeARow]`` for the per-publisher
    party identity reconciliation (PR-W-1 / W-2 / W-3 cohort). Driven by
    the ``parity`` CLI subcommand.
  - ``EventParityAdapter`` (registered in ``EVENT_REGISTRY``) - the
    per-CONSTITUENCY shape: adapters return
    ``Iterable[ConstituencyParityRow]`` for per-event winner
    reconciliation (PR-S-* + PR-PC-* cohort). Driven by the
    ``parity-event`` CLI subcommand.

The two registries share a namespace by convention only: source-id
suffix ``-parties`` / ``-registered`` indicates Shape-A registration;
suffix ``-state`` / ``-pc`` / ``-elections`` indicates Shape-B
registration. The CLI subcommand picks the registry; no polymorphic
dispatch.

Each adapter module exports a single ``ADAPTER`` instance and is wired
into the appropriate registry at module import time (typical pattern:
a top-level ``REGISTRY["<source>"] = ADAPTER`` or
``EVENT_REGISTRY["<source>"] = ADAPTER`` line at the bottom of this
``__init__.py``). The CLI subcommands look up the adapter via
``REGISTRY.get(source)`` / ``EVENT_REGISTRY.get(source)`` and exit
non-zero with a ``no adapter registered for source ...`` message on
miss.

The registries are process-local (module-level dicts) by design;
adapters ship as code, not as data, so the empty-registry boot-time
error is the fail-loud signal that an unmerged Wave B / Wave C PR is
being asked to run.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from ..shape_a import ShapeARow
from ..shape_b import ConstituencyParityRow


class ParityAdapter(Protocol):
    """The contract every per-party-roster parity adapter satisfies.

    Adapters are callables (typically frozen dataclasses with a
    ``__call__`` method) that, given the operator-supplied scoping flags,
    return an iterable of ``ShapeARow`` for the named source-vintage.

    The CLI passes ``root`` (repo root for adapter-side file reads) and
    the optional scoping flags from the command line. Adapters that don't
    use a particular flag SHOULD accept it and ignore it (so the CLI
    signature stays uniform across sources).
    """

    def __call__(
        self,
        *,
        root: Path,
        vintage: str,
        state: str | None = None,
        event: str | None = None,
        kind: str | None = None,
    ) -> Iterable[ShapeARow]:
        ...


class EventParityAdapter(Protocol):
    """The contract every per-event (per-constituency) parity adapter satisfies.

    Adapters are callables (typically frozen dataclasses with a
    ``__call__`` method) that, given the operator-supplied scoping flags
    (``state`` + ``event`` + ``kind`` REQUIRED), return an iterable of
    ``ConstituencyParityRow`` for the named source / event. PR-S-* /
    PR-PC-* PRs register adapters here.
    """

    def __call__(
        self,
        *,
        root: Path,
        vintage: str,
        state: str | None = None,
        event: str | None = None,
        kind: str | None = None,
    ) -> Iterable[ConstituencyParityRow]:
        ...


#: Source-id -> per-party-roster adapter map. PR-2 shipped EMPTY;
#: PR-W-1 + W-2 + W-3 + future per-roster PRs extend it.
REGISTRY: dict[str, ParityAdapter] = {}

#: Source-id -> per-event (per-constituency) adapter map. PR-S-TN-AE2026
#: introduced the registry; PR-PC-* + future per-event PRs extend it.
EVENT_REGISTRY: dict[str, EventParityAdapter] = {}


# --- Adapter registrations (one import line per Wave B + Wave C PR) ---------
#
# Each adapter module exports ADAPTER (a ParityAdapter or
# EventParityAdapter instance) and we register it here. Import order is
# significant only inasmuch as registry duplicates would raise - adapter
# modules MUST NOT register a duplicate source-id. Import errors here
# surface at first use of `python -m yen_gov parity --source ...`
# or `python -m yen_gov parity-event --source ...` (the CLI imports
# this module), not at module-load time of the wider canonical
# namespace.

# Per-party-roster adapters (REGISTRY) - PR-W-1 + W-2 + W-3.
from .tcpd_parties import ADAPTER as _TCPD_PARTIES_ADAPTER

REGISTRY["tcpd-parties"] = _TCPD_PARTIES_ADAPTER

from .eci_registered import ADAPTER as _ECI_REGISTERED_ADAPTER

REGISTRY["eci-registered"] = _ECI_REGISTERED_ADAPTER

from .wikipedia_parties import ADAPTER as _WIKIPEDIA_PARTIES_ADAPTER

REGISTRY["wikipedia-parties"] = _WIKIPEDIA_PARTIES_ADAPTER

# Per-event adapters (EVENT_REGISTRY) - PR-S-TN-AE2026.
from .yen_gov_elections import ADAPTER as _YEN_GOV_ELECTIONS_ADAPTER

EVENT_REGISTRY["yen-gov-elections"] = _YEN_GOV_ELECTIONS_ADAPTER

from .thecont1_state import ADAPTER as _THECONT1_STATE_ADAPTER

EVENT_REGISTRY["thecont1-state"] = _THECONT1_STATE_ADAPTER

from .tcpd_state import ADAPTER as _TCPD_STATE_ADAPTER

EVENT_REGISTRY["tcpd-state"] = _TCPD_STATE_ADAPTER


__all__ = [
    "ParityAdapter",
    "EventParityAdapter",
    "REGISTRY",
    "EVENT_REGISTRY",
]
