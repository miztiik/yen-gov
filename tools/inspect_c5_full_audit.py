"""Inventory every shard in the 16-shard retire list against canonical reality.

Verifies both the 'hard drops' (no canonical replacement claimed) and the
'reader replaceable' (canonical replacement claimed in planning doc).
"""
import duckdb
import json
from pathlib import Path

con = duckdb.connect()

FACT_TABLES = [
    "datasets/energy/energy_installed_capacity.parquet",
    "datasets/energy/energy_generation.parquet",
    "datasets/energy/energy_distribution_performance.parquet",
    "datasets/energy/energy_demand_supply.parquet",
]

# Collect ALL canonical indicator_ids across all 4 fact-tables
all_canonical_ids = set()
for fact_path in FACT_TABLES:
    rows = con.execute(
        f"SELECT DISTINCT indicator_id FROM read_parquet('{fact_path}')"
    ).fetchall()
    for r in rows:
        all_canonical_ids.add(r[0])

print(f"=== {len(all_canonical_ids)} distinct canonical indicator_ids across 4 fact-tables ===")
for cid in sorted(all_canonical_ids):
    # Find which fact-table holds it
    for fact_path in FACT_TABLES:
        cnt = con.execute(
            f"SELECT count(*), count(DISTINCT entity_id), min(period_label), max(period_label) "
            f"FROM read_parquet('{fact_path}') WHERE indicator_id = ?",
            [cid],
        ).fetchone()
        if cnt[0] > 0:
            print(f"  {cid:<60} {cnt[0]:>6} rows / {cnt[1]:>2} entities / {cnt[2]}..{cnt[3]} ({Path(fact_path).stem})")
            break

# All 16 shards in plan-doc retire list (full list from §4 + §6)
RETIRE_LIST = [
    # 9 hard drops
    ("installed_mw_by_state.json", "HARD-DROP", "community-curated GeoJSON, 4 of 35 states; Holy Law #9 fail"),
    ("state_peak_electricity_demand_mw.json", "HARD-DROP", "ICED 1-year snapshot; subset of canonical"),
    ("state_electricity_peak_demand_mw.json", "HARD-DROP", "ICED 9-year tail; reconciled into canonical"),
    ("state_electricity_generation_mu.json", "HARD-DROP", "MU = GWh alias; lives as id_aliases[] on canonical row"),
    ("installed_capacity_total_mw.json", "HARD-DROP", "D33.8 aggregate; compute-on-read"),
    ("installed_capacity_thermal_mw.json", "HARD-DROP", "D33.8 aggregate; compute-on-read"),
    ("state_installed_capacity_total_mw.json", "HARD-DROP", "D33.8 aggregate; FY04-14 spliced into _allocated_mw"),
    ("state_installed_capacity_with_alloc_mw.json", "HARD-DROP", "total-row of _allocated_mw"),
    # 7 reader-replaceable
    ("installed_capacity_coal_mw.json", "REPLACEABLE", "installed-capacity-geographical-mw-coal"),
    ("installed_capacity_gas_mw.json", "REPLACEABLE", "installed-capacity-geographical-mw-gas"),
    ("installed_capacity_hydro_mw.json", "REPLACEABLE", "installed-capacity-geographical-mw-hydro"),
    ("installed_capacity_nuclear_mw.json", "REPLACEABLE", "installed-capacity-geographical-mw-nuclear"),
    ("installed_capacity_renewable_mw.json", "REPLACEABLE", "installed-capacity-geographical-mw-renewable"),
    ("state_installed_capacity_geographical_mw.json", "REPLACEABLE", "installed-capacity-geographical-mw"),
    ("state_installed_capacity_by_source_mw.json", "REPLACEABLE", "facet view of installed-capacity-geographical-mw-<fuel>"),
]

print("\n\n=== 16-shard retire list audit ===\n")
print(f"{'Shard':<55} {'Class':<14} {'Lrows':>6} {'Lentities':>10} {'Lperiods':<22} {'Status'}")
print("-" * 175)

ok_to_retire = []
needs_lift = []
needs_review = []

for shard_name, claimed_class, note in RETIRE_LIST:
    p = Path(f"datasets/indicators/in/energy/{shard_name}")
    if not p.exists():
        print(f"  MISSING-ON-DISK: {shard_name}")
        continue
    doc = json.loads(p.read_text(encoding="utf-8"))
    legacy_rows = doc.get("rows", [])
    legacy_times = sorted(set(r["time"] for r in legacy_rows if r.get("time")))
    legacy_entities = sorted(set(r["entity_id"] for r in legacy_rows))
    lcount = len(legacy_rows)
    lperiod_str = f"{legacy_times[0]}..{legacy_times[-1]}" if legacy_times else "(none)"
    lentities_str = f"{len(legacy_entities)}"

    if claimed_class == "HARD-DROP":
        # Is the source format snapshot or time series?
        if len(legacy_times) <= 2:
            verdict = f"HARD-DROP-OK (snapshot {lperiod_str})"
            ok_to_retire.append((shard_name, claimed_class, verdict))
        else:
            verdict = f"HARD-DROP-NEEDS-REVIEW (multi-period time series, may have unique data)"
            needs_review.append((shard_name, claimed_class, verdict))
    else:  # REPLACEABLE
        canonical_id = note
        if "-coal" in canonical_id or "-gas" in canonical_id or "-hydro" in canonical_id or "-nuclear" in canonical_id or "-renewable" in canonical_id or canonical_id == "installed-capacity-geographical-mw":
            target_fact = "datasets/energy/energy_installed_capacity.parquet"
        else:
            target_fact = None
        if target_fact:
            c = con.execute(
                f"SELECT count(*), count(DISTINCT entity_id), min(period_label), max(period_label) "
                f"FROM read_parquet('{target_fact}') WHERE indicator_id = ?",
                [canonical_id],
            ).fetchone()
            ccount, centities, cmin, cmax = c
            cperiod_str = f"{cmin}..{cmax}" if cmin else "(none)"
            if ccount == 0:
                verdict = f"NEEDS-LIFT (no canonical rows for '{canonical_id}')"
                needs_lift.append((shard_name, claimed_class, verdict))
            elif lcount == ccount and len(legacy_entities) == centities and lperiod_str == cperiod_str:
                verdict = f"BYTE-PARITY-LIKELY (canonical {ccount}/{centities}/{cperiod_str})"
                ok_to_retire.append((shard_name, claimed_class, verdict))
            elif len(legacy_times) == 1 and len(legacy_entities) >= 30:
                # Legacy is a 35-state snapshot; canonical is time series
                verdict = f"NEEDS-LIFT (legacy=35-entity snapshot {lperiod_str}; canonical={centities}-entity series {cperiod_str})"
                needs_lift.append((shard_name, claimed_class, verdict))
            else:
                verdict = f"PARTIAL (legacy {lcount}/{len(legacy_entities)}/{lperiod_str} vs canonical {ccount}/{centities}/{cperiod_str})"
                needs_review.append((shard_name, claimed_class, verdict))
        else:
            verdict = f"UNKNOWN target table for '{canonical_id}'"
            needs_review.append((shard_name, claimed_class, verdict))

    print(f"{shard_name:<55} {claimed_class:<14} {lcount:>6} {lentities_str:>10} {lperiod_str:<22} {verdict}")

print("\n\n=== Summary ===\n")
print(f"OK to retire ({len(ok_to_retire)}):")
for s, c, v in ok_to_retire:
    print(f"  - {s}  [{c}]  {v}")
print(f"\nNeeds canonical lift first ({len(needs_lift)}):")
for s, c, v in needs_lift:
    print(f"  - {s}  [{c}]  {v}")
print(f"\nNeeds Hans+Max review ({len(needs_review)}):")
for s, c, v in needs_review:
    print(f"  - {s}  [{c}]  {v}")
