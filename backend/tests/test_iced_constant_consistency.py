"""Consistency oracle: the 6 canonical ICED adapter constants match source.csv.

Row 10 (ingest plan) corrected ``datasets/data/entities/source.csv`` to the
real upstream issuing authorities (D2), but left each ICED adapter's
``source_producer`` / ``source_title`` constants at the old product-name value.
Row 11 reconciles those constants to the D2 authority map. This test PROVES the
reconciliation has zero drift: re-deriving ``source_id`` from each adapter's
(now-corrected) citation constants resolves to a row that exists in the on-disk
``source.csv``, and no adapter still carries a product-name producer.

Bounded (9 specs across 6 adapters); reads the citation ledger once. Not a
corpus walk (CLAUDE.md anti-pattern) -- it reads ONE committed contract file and
checks a fixed, small set of ids.

The faceted ``yen_gov.sources.iced_power`` ingest pipeline is deliberately OUT
of scope (its source_id is a pre-existing, separately-flagged deferral; ingest
plan section 6), and the cold ``yen_gov.sources.iced_*`` adapters are out of
scope too: their titles never matched source.csv (a pre-existing mismatch
unrelated to Row 10), so they carry no Row-10 decision to reconcile against.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.iced_authority_map import is_product_producer

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_CSV = _REPO_ROOT / "datasets" / "data" / "entities" / "source.csv"


def _adapter_triples() -> list[tuple[str, str, str, str]]:
    """Return ``(label, producer, title, vintage)`` for every canonical ICED spec."""
    triples: list[tuple[str, str, str, str]] = []

    from yen_gov.canonical.adapters.iced_ev_share.registry import (
        SHIPPED_SPECS as ev,
    )
    from yen_gov.canonical.adapters.iced_captive_power.registry import (
        SHIPPED_SPECS as cap,
    )
    from yen_gov.canonical.adapters.iced_coal_fgd.registry import (
        SHIPPED_SPEC as fgd,
    )
    from yen_gov.canonical.adapters.iced_renewable_potential.registry import (
        SHIPPED_SPECS as ren,
    )
    from yen_gov.canonical.adapters.iced_transmission_substations.registry import (
        SHIPPED_SPEC as tx,
    )
    from yen_gov.canonical.adapters.iced_national_energy.registry import (
        FINAL_ENERGY_SPEC,
        PRIMARY_ENERGY_SPEC,
    )

    groups: list[tuple[str, object]] = [
        ("ev_share", ev),
        ("captive_power", cap),
        ("coal_fgd", fgd),
        ("renewable_potential", ren),
        ("transmission_substations", tx),
        ("national_energy", (PRIMARY_ENERGY_SPEC, FINAL_ENERGY_SPEC)),
    ]
    for label, specs in groups:
        items = specs if isinstance(specs, tuple) else (specs,)
        for spec in items:
            triples.append(
                (
                    f"{label}:{spec.indicator_id}",
                    spec.source_producer,
                    spec.source_title,
                    spec.source_vintage,
                )
            )
    return triples


def _on_disk_source_ids() -> set[str]:
    with _SOURCE_CSV.open(encoding="utf-8", newline="") as fh:
        return {row["source_id"] for row in csv.DictReader(fh)}


_TRIPLES = _adapter_triples()


def test_ten_specs_across_six_adapters():
    # ev_share(1) + captive(2, sharing one citation triple) + coal_fgd(1) +
    # renewable(3) + transmission(1) + national_energy(2) = 10 specs.
    assert len(_TRIPLES) == 10


@pytest.mark.parametrize("label,producer,title,vintage", _TRIPLES)
def test_no_product_name_producer(label, producer, title, vintage):
    # D2 anti-pattern: a producer must be an organisation, never a product /
    # dashboard name. Every reconciled spec passes the same guard the Tier-B
    # validator enforces on the corpus.
    assert not is_product_producer(producer), (
        f"{label}: producer {producer!r} still reads as a product/dashboard name"
    )


@pytest.mark.skipif(
    not _SOURCE_CSV.is_file(), reason="source.csv not present under this root"
)
@pytest.mark.parametrize("label,producer,title,vintage", _TRIPLES)
def test_derived_source_id_is_on_disk(label, producer, title, vintage):
    # The 0-drift proof: the source_id a re-run would emit from the corrected
    # adapter constants already exists in the on-disk citation ledger.
    on_disk = _on_disk_source_ids()
    sid = derive_source_id(producer, title, vintage)
    assert sid in on_disk, (
        f"{label}: derived source_id {sid!r} from the adapter constants is NOT "
        f"in datasets/data/entities/source.csv -- the adapter would re-emit a "
        f"dangling citation FK (drift). Reconcile the constants to the Row-10 "
        f"authority map."
    )
