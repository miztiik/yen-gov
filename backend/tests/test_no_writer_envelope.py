"""Contract guard: the Parquet-era canonical writer + envelope are gone (Row 9).

Row 9 of the ingest rip-replace deleted ``canonical/writer.py`` +
``canonical/envelope.py`` (the ``BatchEnvelope`` -> ``write_batch`` Parquet
write seam). This test is the durable receipt for the Row 9 gate: the two
modules are unimportable, and no PRODUCTION module under ``backend/yen_gov/``
carries a live (non-string, non-comment) reference to ``write_batch`` or
``BatchEnvelope``. The legacy row DTOs the ECI electoral adapters + citation
seeds still build were relocated VERBATIM to ``canonical/row_models.py``.

Scope note: this guard covers ONLY the writer/envelope contract symbols. The
broader Parquet -> long-format-CSV migration retires the remaining
``read_parquet`` / ``FORMAT PARQUET`` producers (the ``*_seed.compile_to_parquet``
writers, the admin inventory reader, the citation reader, the pincode ingest)
under OTHER plan rows; those surviving features are intentionally out of Row 9
scope and are NOT asserted here.
"""

from __future__ import annotations

import importlib.util
import tokenize
from pathlib import Path

import pytest

_PROD_ROOT = Path(__file__).resolve().parents[1] / "yen_gov"
_FORBIDDEN_NAMES = ("write_batch", "BatchEnvelope")


@pytest.mark.parametrize("module", ["yen_gov.canonical.writer", "yen_gov.canonical.envelope"])
def test_deleted_modules_are_unimportable(module: str) -> None:
    assert importlib.util.find_spec(module) is None, f"{module} should be deleted in Row 9"


def test_row_models_exposes_relocated_dtos() -> None:
    from yen_gov.canonical import row_models

    for name in (
        "SourceRow",
        "ObservationRow",
        "PersonDimRow",
        "CandidacyRow",
        "AcDimRow",
        "PcDimRow",
        "PartyDimRow",
        "PartyAllianceDimRow",
    ):
        assert hasattr(row_models, name), f"row_models is missing {name}"


def _live_name_tokens(path: Path) -> set[str]:
    """Return the set of code NAME tokens in ``path`` (comments + strings
    excluded by the tokenizer) so the scan ignores docstrings + comment prose
    and only flags live code references."""
    names: set[str] = set()
    with path.open("rb") as fh:
        try:
            tokens = list(tokenize.tokenize(fh.readline))
        except (tokenize.TokenError, SyntaxError):
            return names
    for tok in tokens:
        if tok.type == tokenize.NAME:
            names.add(tok.string)
    return names


def test_no_live_writer_envelope_references() -> None:
    offenders: list[str] = []
    for py in _PROD_ROOT.rglob("*.py"):
        hit = sorted(_live_name_tokens(py).intersection(_FORBIDDEN_NAMES))
        if hit:
            offenders.append(f"{py.relative_to(_PROD_ROOT.parent).as_posix()}: {hit}")
    assert not offenders, (
        "Live (non-comment, non-string) write_batch/BatchEnvelope references "
        f"remain after Row 9: {offenders}"
    )
