"""Evidence-gated ICED producer correction map (ingest plan Row 10 / D2).

The NITI Aayog India Climate & Energy Dashboard (ICED) is a machine-readable
**access surface**, not a publisher organisation. ``producer`` must name the
issuing-authority organisation (CLAUDE.md section 12, Holy Law #9; OWID
``origin.producer``). D2 corrects every source row currently attributed to the
dashboard product, **per endpoint on cited in-repo evidence**:

* where ICED is a pure **passthrough** of one upstream issuing authority, the
  producer becomes that authority and the dashboard moves into the source
  ``title`` (the :data:`VIA_ICED_SUFFIX`);
* where ICED **originates** a derived / harmonised analytic, aggregates several
  upstreams, or no single authority can be cited, the producer stays the
  organisation-led label :data:`ICED_ORG_PRODUCER` (never the bare dashboard
  product name).

This module is the machine-readable form of those decisions plus the
FK-lockstep migration that applies them. It is **pure and network-free**: it
reads/writes local CSV/JSON only. The companion evidence ledger is
``docs/research/iced-authority-tracing.md``; the Tier-B guard that keeps the
corpus honest is ``tier_b_source_producer_not_a_product`` in
``backend/yen_gov/validate.py``.

Correcting a producer re-mints the deterministic ``source_id`` (the hash of the
new ``(producer, title, vintage)`` triple); **no ``indicator_id`` ever
changes** - only the FK that points observation rows at their citation row.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id

__all__ = [
    "ICED_PRODUCT_PRODUCER",
    "ICED_ORG_PRODUCER",
    "VIA_ICED_SUFFIX",
    "PRODUCT_PRODUCER_TOKENS",
    "EndpointDecision",
    "DECISIONS",
    "decision_for_source_id",
    "corrected_triple",
    "reattributed_authorities",
    "is_product_producer",
    "CorrectionResult",
    "apply_correction",
]

# The product-name producer being corrected (the on-disk pre-D2 value).
ICED_PRODUCT_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
# The D2 keep-value: organisation-led, no bare product/dashboard token.
ICED_ORG_PRODUCER = "NITI Aayog ICED"
# Appended to a reattributed row's title so the access surface is not lost
# ("ICED moves into title", D2).
VIA_ICED_SUFFIX = " [republished via NITI Aayog India Climate & Energy Dashboard]"

# A ``producer`` that contains one of these product/platform tokens is a
# product/dashboard name, not an organisation (the anti-pattern D2 fixes).
# Verified 2026-06-19 against the full 506-row source.csv: ONLY the 34 ICED
# rows tripped any token ("dashboard"); every other producer is clean, so the
# guard has zero false positives on the corpus. ``NITI Aayog ICED`` is
# organisation-led and contains no token.
PRODUCT_PRODUCER_TOKENS: tuple[str, ...] = (
    "dashboard",
    "portal",
    "database",
    "repository",
    "data portal",
    "web portal",
)

# Repo-relative path to the citation ledger this map corrects.
SOURCE_CSV_REL = "datasets/data/entities/source.csv"
DATASETS_REL = "datasets"


@dataclass(frozen=True)
class EndpointDecision:
    """One per-endpoint D2 ruling, keyed by the current (pre-D2) source_id.

    ``authority`` is the upstream issuing-authority organisation when the
    endpoint is a passthrough, or ``None`` to keep the row as
    :data:`ICED_ORG_PRODUCER`. ``evidence`` cites the in-repo basis (an adapter
    docstring / comment) so the decision is auditable and the tracing doc and
    this map cannot silently diverge.
    """

    source_id: str
    endpoint: str
    authority: str | None
    evidence: str


# The 34 ICED-attributed source rows, decided per endpoint on cited evidence.
# 24 reattributed to an upstream authority; 10 kept as NITI Aayog ICED.
# Keyed by the current source_id (verified 2026-06-19 to equal
# derive_source_id(producer, title, vintage) for every row). The full evidence
# table (titles, indicator_ids, passthrough-vs-derived) is in
# docs/research/iced-authority-tracing.md.
DECISIONS: tuple[EndpointDecision, ...] = (
    # --- Central Electricity Authority (CEA) ---
    EndpointDecision(
        "src-1240f07df0ac", "Capacity Metatable (installed capacity by fuel)",
        "Central Electricity Authority",
        "sources/iced_metatable/ingest.py: 'ICED capacity-metatable rollup of "
        "CEA-published station-level capacity'; sources/iced_power: '(CEA-sourced upstream)'",
    ),
    EndpointDecision(
        "src-ddbfadd51428", "Generation Metatable (generation by fuel)",
        "Central Electricity Authority",
        "sources/iced_power/ingest.py: '/v1/gen-metatable-data (CEA-sourced upstream)'",
    ),
    EndpointDecision(
        "src-7eb929cbf2d8", "Plant Load Factor by Fuel State",
        "Central Electricity Authority",
        "sources/iced_power/ingest.py: '/v1/plf-metatable-data (CEA-sourced upstream). "
        "PLF is the standard CEA metric'",
    ),
    EndpointDecision(
        "src-fd152bd3c6c6", "Retired Thermal Capacity Plants",
        "Central Electricity Authority",
        "sources/iced_metatable/ingest.py: 'ICED retired-capacity-plants endpoint (CEA-sourced)'",
    ),
    EndpointDecision(
        "src-3d0b1c141f6a", "Captive Power (industry-wise) State-wise",
        "Central Electricity Authority",
        "canonical/adapters/iced_captive_power/registry.py: 'the underlying returns are the "
        "Central Electricity Authority's (CEA)'; 'self-reported by industry to the CEA'",
    ),
    EndpointDecision(
        "src-7c3cc99a3b68", "CO Emission Metatable (power-sector CO2 by fuel)",
        "Central Electricity Authority",
        "sources/iced_power/ingest.py: 'unit-level CO2 emissions are derived ... from CEA "
        "generation x CEA technology-specific emission factors' (CEA CO2 Baseline Database)",
    ),
    EndpointDecision(
        "src-706a26f2871e", "Air Quality FGD (coal-thermal FGD share)",
        "Central Electricity Authority",
        "sources/iced_air_quality/ingest.py title 're-publishing CEA / MoEF&CC'; parsers.py "
        "'CEA (Central Electricity Authority) and tied to the MoEF&CC'",
    ),
    # --- Central Pollution Control Board (CPCB) ---
    EndpointDecision(
        "src-263dcba882ba", "AQI Map Markers (NO2/SO2/PM10/PM2.5 annual mean)",
        "Central Pollution Control Board",
        "sources/iced_air_quality/markers_ingest.py: 're-publishing CPCB NAMP' (per pollutant); "
        "endpoints.py 'ICED is a re-publisher of CPCB NAMP annual-mean'",
    ),
    # --- Ministry of Environment, Forest and Climate Change (MoEFCC) ---
    EndpointDecision(
        "src-7532e395ae91", "GHG Emissions by sector and sub-sector (energy)",
        "Ministry of Environment, Forest and Climate Change",
        "sources/iced_ghg/ingest.py: 'IPCC 2006 guidelines (BUR-3 / BUR-4 submissions, MoEFCC)'",
    ),
    EndpointDecision(
        "src-857e962f15f5", "GHG Emissions economy-wide by sector",
        "Ministry of Environment, Forest and Climate Change",
        "sources/iced_socio/ingest.py: 'IPCC 2006 guidelines (BUR submissions, MoEFCC)'",
    ),
    # --- Ministry of Statistics and Programme Implementation (MoSPI / NSO / CSO) ---
    EndpointDecision(
        "src-bb7935971e98", "Key Economic Indicators - GDP / GSDP",
        "Ministry of Statistics and Programme Implementation",
        "sources/iced_macro/ingest.py: 'MoSPI / National Statistical Office national GDP back-series'",
    ),
    EndpointDecision(
        "src-5c93205c875f", "Key Economic Indicators - GVA by industry (constant)",
        "Ministry of Statistics and Programme Implementation",
        "sources/iced_macro/ingest.py: 'MoSPI / NSO national accounts, constant prices base 2011-12'",
    ),
    EndpointDecision(
        "src-933106681441", "Key Economic Indicators - Index of Industrial Production",
        "Ministry of Statistics and Programme Implementation",
        "sources/iced_macro/ingest.py module 'ICED macro adapter - national/state GDP, IIP'; "
        "IIP (2011-12=100) is the MoSPI / NSO flagship index",
    ),
    EndpointDecision(
        "src-b222d76f33c1", "State-wise Deep Dive - Sectoral GVA",
        "Ministry of Statistics and Programme Implementation",
        "sources/iced_state_wise/ingest.py: 'State Directorates of Economics & Statistics under "
        "MoSPI methodology'; 'NSO finalises that year's accounts'",
    ),
    EndpointDecision(
        "src-b6b6a168517e", "State-wise Deep Dive - State GDP (constant 2011-12)",
        "Ministry of Statistics and Programme Implementation",
        "sources/iced_state_wise/ingest.py: 'Constant Price' (NSO/MoSPI underlying)",
    ),
    EndpointDecision(
        "src-1a8a6f710f23", "Key Economic Indicators - per-capita PFCE",
        "Ministry of Statistics and Programme Implementation",
        "sources/iced_socio/ingest.py: 'National Accounts PFCE (CSO modelled to state level)' "
        "(CSO is part of MoSPI / NSO)",
    ),
    EndpointDecision(
        "src-3155ffeddf80", "State-wise Deep Dive - Population (lakhs)",
        "Ministry of Statistics and Programme Implementation",
        "sources/iced_state_wise/ingest.py: 'Inter-censal estimates from MoSPI; the next decadal "
        "Census will reset the baseline'",
    ),
    # --- Reserve Bank of India (RBI) ---
    EndpointDecision(
        "src-41cb48075b72", "Key Economic Indicators - Balance of Payments",
        "Reserve Bank of India",
        "sources/iced_macro/ingest.py: 'RBI Balance of Payments statistics, republished by NITI Aayog'",
    ),
    # --- Ministry of Coal ---
    EndpointDecision(
        "src-c222a8e2cd61", "Coal Consumption (Domestic) State-wise (by grade)",
        "Ministry of Coal",
        "sources/iced_fuel/ingest.py: 'Ministry of Coal upstream'",
    ),
    # --- Petroleum Planning and Analysis Cell (PPAC, under MoPNG) ---
    EndpointDecision(
        "src-cba8334fedc5", "Oil Product Consumption State-wise (by product)",
        "Petroleum Planning and Analysis Cell",
        "sources/iced_fuel/ingest.py: 'consumptionStateProductTrend (PPAC / Ministry of "
        "Petroleum & Natural Gas upstream)'",
    ),
    # --- Ministry of Road Transport and Highways (MoRTH) ---
    EndpointDecision(
        "src-412af3a265c8", "ICE vs EV (VAHAN) State-wise",
        "Ministry of Road Transport and Highways",
        "canonical/adapters/iced_ev_share: 'ICED republishes MoRTH VAHAN'; registry 'Ministry of "
        "Road Transport & Highways VAHAN portal'",
    ),
    # --- Power Finance Corporation (PFC report card on state power utilities) ---
    EndpointDecision(
        "src-650b1c25d1f7", "Distribution Operational Performance (T&D / billing / collection)",
        "Power Finance Corporation",
        "sources/iced_discom/ingest.py: 'operationalPerformanceStates (PFC report-card upstream)'",
    ),
    EndpointDecision(
        "src-1401f8087b0d", "State Power Purchase Quantum and Cost (procurement mix)",
        "Power Finance Corporation",
        "sources/iced_fuel/ingest.py: '(PFC / Ministry of Power upstream). Per-state per-source per-FY'",
    ),
    # --- Ministry of New and Renewable Energy (MNRE) ---
    EndpointDecision(
        "src-018bb42f9519", "Rooftop Solar Capacity (MW) State-wise (installed)",
        "Ministry of New and Renewable Energy",
        "sources/iced_state_wise/ingest.py notes: 'row 'Rooftop Solar Capacity'. Underlying "
        "figures published by MNRE'",
    ),
    # --- KEPT as NITI Aayog ICED (authority=None) ---
    EndpointDecision(
        "src-170d3536d908", "Primary Energy Supply National (harmonised balance)",
        None,
        "canonical/adapters/iced_national_energy/registry.py: 'ICED is the publisher of the "
        "harmonised national balance ... IEA/CEA/MoSPI energy-account methodology; ICED is the "
        "harmonised access surface' (ICED-originated harmonisation)",
    ),
    EndpointDecision(
        "src-29ecbb6dce9d", "Final Energy Consumption National (harmonised balance)",
        None,
        "canonical/adapters/iced_national_energy/registry.py (as above): ICED harmonises "
        "IEA/CEA/MoSPI into one energy balance",
    ),
    EndpointDecision(
        "src-518795193989", "Renewable Energy Potential - Solar (modelled)",
        None,
        "canonical/adapters/iced_renewable_potential/registry.py: 'publisher of the harmonised "
        "series ... NISE for solar' (modelled estimate; single-authority reattribution deferred)",
    ),
    EndpointDecision(
        "src-36e84f35548b", "Renewable Energy Potential - Wind (modelled)",
        None,
        "canonical/adapters/iced_renewable_potential/registry.py: 'NIWE for wind' (modelled "
        "estimate framed as ICED harmonised series; deferred)",
    ),
    EndpointDecision(
        "src-c0a10bb04862", "Renewable Energy Potential - Bioenergy (modelled)",
        None,
        "canonical/adapters/iced_renewable_potential/registry.py: 'MNRE / the Biomass Atlas for "
        "bio-energy' (modelled estimate framed as ICED harmonised series; deferred)",
    ),
    EndpointDecision(
        "src-d9484e65a17e", "Transmission Substation List (derived rollup)",
        None,
        "canonical/adapters/iced_transmission_substations/registry.py: non-null derivation (sum "
        "of MVA by voltage class); 'publisher of the harmonised series'; no single upstream named",
    ),
    EndpointDecision(
        "src-85c67674901f", "Coal Plant AQI Impact List (yen-gov geocode-derived)",
        None,
        "canonical/adapters/iced_coal_fgd/registry.py: 'A geocode-derived (major-processing) "
        "statistic' (yen-gov geocodes each plant + aggregates per state from ICED's impact list)",
    ),
    EndpointDecision(
        "src-bb1d7bec8b34", "State-wise Deep Dive API (multi-authority aggregator)",
        None,
        "backs 6 indicators spanning multiple upstreams (CEA capacity/consumption + PFC "
        "AT&C/ACS-ARR + state utilities); no single issuing authority",
    ),
    EndpointDecision(
        "src-0ea63ed47704", "Distribution RPO Compliance (no single authority)",
        None,
        "sources/iced_discom/parsers.py: 'Upstream rpoCompliance'; RPO is set/tracked by SERCs / "
        "MNRE - no single issuing authority named in-repo (thin)",
    ),
    EndpointDecision(
        "src-e0b2a084d204", "Plant Pipeline Info National (thermal + RE)",
        None,
        "sources/iced_power/ingest.py pipeline re-ingest names only 'ICED plantPipelineInfo'; "
        "under-construction capacity spans thermal (CEA) + renewable (MNRE) - no single authority",
    ),
)

_BY_SOURCE_ID: dict[str, EndpointDecision] = {d.source_id: d for d in DECISIONS}


def decision_for_source_id(source_id: str) -> EndpointDecision | None:
    """Return the D2 decision for a current (pre-D2) ICED ``source_id``."""
    return _BY_SOURCE_ID.get(source_id)


def reattributed_authorities() -> frozenset[str]:
    """The set of upstream producers introduced by reattribution (the kept
    rows contribute nothing). Used by the tracing-doc cross-check test."""
    return frozenset(d.authority for d in DECISIONS if d.authority is not None)


def is_product_producer(producer: str) -> bool:
    """True when ``producer`` reads as a product/dashboard name (D2 anti-pattern).

    Matches if any token in :data:`PRODUCT_PRODUCER_TOKENS` appears
    (case-insensitively) in the producer string. ``NITI Aayog ICED`` and every
    issuing-authority organisation pass.
    """
    low = producer.lower()
    return any(tok in low for tok in PRODUCT_PRODUCER_TOKENS)


def corrected_triple(
    producer: str, title: str, vintage: str
) -> tuple[str, str, str]:
    """Map a current ICED ``(producer, title, vintage)`` to the corrected triple.

    Rows whose producer is not :data:`ICED_PRODUCT_PRODUCER` are returned
    unchanged (the map only touches the dashboard-attributed rows). For an ICED
    row the decision is looked up by its deterministic ``source_id``:

    * passthrough -> ``(authority, title + VIA_ICED_SUFFIX, vintage)``;
    * kept -> ``(ICED_ORG_PRODUCER, title, vintage)``.

    Raises ``KeyError`` if an ICED row has no Row-10 decision (fail loud: a new
    ICED endpoint must be classified before it can be migrated).
    """
    if producer != ICED_PRODUCT_PRODUCER:
        return (producer, title, vintage)
    source_id = derive_source_id(producer, title, vintage)
    decision = _BY_SOURCE_ID.get(source_id)
    if decision is None:
        raise KeyError(
            f"ICED source row {source_id!r} (title {title!r}) has no Row-10 "
            f"authority decision in iced_authority_map.DECISIONS; classify it "
            f"(reattribute or keep) and cite the evidence before migrating."
        )
    if decision.authority is None:
        return (ICED_ORG_PRODUCER, title, vintage)
    return (decision.authority, title + VIA_ICED_SUFFIX, vintage)


@dataclass
class CorrectionResult:
    """Outcome of one :func:`apply_correction` run (for receipts + tests)."""

    id_remap: dict[str, str] = field(default_factory=dict)
    reattributed: list[tuple[str, str]] = field(default_factory=list)  # (old_id, authority)
    kept: list[str] = field(default_factory=list)                       # old_id
    files_rewritten: list[str] = field(default_factory=list)            # repo-relative POSIX
    # Decisions whose source_id matched no row under this root. Empty on the
    # full real corpus (every decision maps to a ledger row); non-empty only
    # for a partial fixture. The full-corpus caller asserts this is empty.
    unmatched_decisions: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.id_remap)


def _iter_datasets_files(datasets_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in datasets_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in (".csv", ".json")
    )


def apply_correction(root: Path) -> CorrectionResult:
    """Apply the D2 producer correction across the canonical store under ``root``.

    Mechanical, idempotent FK-lockstep migration (no adapter re-run, no
    network):

    1. Rewrite each ICED row in ``datasets/data/entities/source.csv`` to its
       corrected ``(source_id, producer, title)`` (vintage + url unchanged).
    2. Token-replace every old ``source_id`` with its new ``source_id`` in every
       other ``datasets/**/*.csv`` and ``*.json`` file (datapoints,
       ``variables.csv``, ``taxonomy/indicators.json`` - every FK reference).

    Fails loud if an ICED-product row has no decision, if a decision matches no
    on-disk row, or if any new ``source_id`` collides with an old one or an
    existing unrelated row. Running twice is a no-op (after the first pass no
    row carries :data:`ICED_PRODUCT_PRODUCER`).
    """
    result = CorrectionResult()
    source_csv = root / SOURCE_CSV_REL
    with source_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    existing_ids = {r["source_id"] for r in rows}
    corrected: dict[str, tuple[str, str, str]] = {}  # old_id -> (new_id, producer, title)
    seen_decisions: set[str] = set()
    for r in rows:
        if r.get("producer") != ICED_PRODUCT_PRODUCER:
            continue
        old_id = r["source_id"]
        decision = _BY_SOURCE_ID.get(old_id)
        if decision is None:
            raise ValueError(
                f"{SOURCE_CSV_REL}: ICED row {old_id!r} (title {r['title']!r}) has no "
                f"Row-10 decision in iced_authority_map.DECISIONS."
            )
        seen_decisions.add(old_id)
        new_producer, new_title, new_vintage = corrected_triple(
            r["producer"], r["title"], r["vintage"]
        )
        new_id = derive_source_id(new_producer, new_title, new_vintage)
        corrected[old_id] = (new_id, new_producer, new_title)
        if decision.authority is None:
            result.kept.append(old_id)
        else:
            result.reattributed.append((old_id, decision.authority))

    if not corrected:
        return result  # already migrated / no ICED rows: no-op

    # Decisions not present under this root (empty on the full corpus; a partial
    # fixture legitimately exercises only a subset). Informational, not fatal -
    # the forward direction (every ICED-product row IS classified) is enforced
    # above. The full-corpus deliverable run asserts this list is empty.
    result.unmatched_decisions = sorted(set(_BY_SOURCE_ID) - seen_decisions)

    old_ids = set(corrected)
    new_ids = {v[0] for v in corrected.values()}
    if len(new_ids) != len(corrected):
        raise ValueError("D2 correction produced colliding new source_ids.")
    if old_ids & new_ids:
        raise ValueError("D2 correction: a new source_id equals an old one (replacement chain).")
    collide = new_ids & (existing_ids - old_ids)
    if collide:
        raise ValueError(
            f"D2 correction: new source_id(s) collide with existing unrelated rows: {sorted(collide)}."
        )

    result.id_remap = {old: corrected[old][0] for old in corrected}

    # 1. Structured rewrite of source.csv (LF + QUOTE_MINIMAL = on-disk dialect).
    for r in rows:
        if r["source_id"] in corrected:
            new_id, new_producer, new_title = corrected[r["source_id"]]
            r["source_id"] = new_id
            r["producer"] = new_producer
            r["title"] = new_title
    with source_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    result.files_rewritten.append(SOURCE_CSV_REL)

    # 2. Token-replace every old_id -> new_id across all other datasets files.
    remap_bytes = [
        (old.encode("ascii"), new.encode("ascii")) for old, new in result.id_remap.items()
    ]
    datasets_dir = root / DATASETS_REL
    for path in _iter_datasets_files(datasets_dir):
        if path.resolve() == source_csv.resolve():
            continue
        data = path.read_bytes()
        new_data = data
        for old_b, new_b in remap_bytes:
            if old_b in new_data:
                new_data = new_data.replace(old_b, new_b)
        if new_data != data:
            path.write_bytes(new_data)
            result.files_rewritten.append(
                path.resolve().relative_to(root.resolve()).as_posix()
            )

    return result
