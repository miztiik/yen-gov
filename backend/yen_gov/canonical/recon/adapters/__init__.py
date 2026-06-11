"""Per-source parity adapter registry.

PR-2 ships an EMPTY registry. PR-W-1 (TCPD parties), PR-W-2 (ECI registered
list), PR-W-3 (Wikipedia per-party infobox), and each Stream X PR each add
one adapter module under this package:

    backend/yen_gov/canonical/recon/adapters/<source>.py

The module exports a single ``ADAPTER`` instance that satisfies the
``ParityAdapter`` Protocol below, and self-registers in ``REGISTRY`` at
import time (typical pattern: a top-level
``REGISTRY["<source>"] = ADAPTER`` line at the bottom of the adapter
module). The ``parity`` CLI in ``backend/yen_gov/cli.py`` looks up the
adapter via ``REGISTRY.get(source)`` and exits non-zero with a
``no adapter registered for source ...`` message on miss.

The registry is process-local (a module-level dict) by design; adapters
ship as code, not as data, so the empty-registry boot-time error is the
fail-loud signal that an unmerged Wave B PR is being asked to run.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from ..shape_a import ShapeARow


class ParityAdapter(Protocol):
    """The contract every parity adapter satisfies.

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


#: Source-id -> adapter map. PR-2 shipped EMPTY; Wave B + Stream X PRs
#: extend it by appending ``REGISTRY["<source>"] = ADAPTER`` to their own
#: adapter module (PR-W-1 onwards).
REGISTRY: dict[str, ParityAdapter] = {}


# --- Adapter registrations (one import line per Wave B + Stream X PR) -------
#
# Each adapter module exports ADAPTER (a ParityAdapter instance) and we
# register it here. Import order is significant only inasmuch as registry
# duplicates would raise — adapter modules MUST NOT register a duplicate
# source-id. Import errors here surface at first use of `python -m yen_gov
# parity --source ...` (the CLI imports this module), not at module-load
# time of the wider canonical namespace.

from .tcpd_parties import ADAPTER as _TCPD_PARTIES_ADAPTER

REGISTRY["tcpd-parties"] = _TCPD_PARTIES_ADAPTER

from .eci_registered import ADAPTER as _ECI_REGISTERED_ADAPTER

REGISTRY["eci-registered"] = _ECI_REGISTERED_ADAPTER

from .wikipedia_parties import ADAPTER as _WIKIPEDIA_PARTIES_ADAPTER

REGISTRY["wikipedia-parties"] = _WIKIPEDIA_PARTIES_ADAPTER

# --- PR-PC-LS2024: per-constituency parity adapters ----------------------

from .bhukyavenkatamahesh_pc import ADAPTER as _BHUKY_PC_ADAPTER

REGISTRY["bhukyavenkatamahesh-pc"] = _BHUKY_PC_ADAPTER

from .tcpd_pc import ADAPTER as _TCPD_PC_ADAPTER

REGISTRY["tcpd-pc"] = _TCPD_PC_ADAPTER

from .yen_gov_canonical_pc import ADAPTER as _YEN_GOV_CANONICAL_PC_ADAPTER

REGISTRY["yen-gov-canonical-pc"] = _YEN_GOV_CANONICAL_PC_ADAPTER


__all__ = ["ParityAdapter", "REGISTRY"]
