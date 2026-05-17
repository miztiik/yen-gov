"""Upstream-fetch boundary protocol.

Step 6 is module-structure-only — the live HTTP wiring against ICED
endpoints lands in step 7 (per Phase 2 sequencing in
TODO/20260517-iced-bulk-ingest-and-parity-oracle.md). This file exists
so `classify.py`, `ledger.py`, and `banner.py` can be unit-tested today
without an HTTP client and so the eventual step-7 wiring slots into a
declared interface rather than mutating callers.
"""

from __future__ import annotations

from typing import Optional, Protocol

from .sample import Cell


class UpstreamFetcher(Protocol):
    """Fetch one cell's current upstream value.

    Implementations:
      - Step 7 will ship `IcedApiFetcher` (calls ICED's decrypted
        JSON envelope per endpoint catalogue and extracts the cell).
      - Tests use plain `Callable[[str, Cell], tuple[float | None, str]]`
        functions; the Protocol is structural so no inheritance is
        required.
    """

    def __call__(
        self, indicator_id: str, cell: Cell
    ) -> tuple[Optional[float], str]:
        """Return `(value_upstream_or_None, upstream_url_string)`.

        `value_upstream_or_None` is None when upstream no longer
        contains the cell (paired with the classifier's
        `missing_upstream` status). `upstream_url_string` is the exact
        URL the implementation hit, recorded on the ledger line as
        per-record provenance.
        """
        ...
