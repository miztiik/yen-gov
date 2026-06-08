# tools/migrate/

One-shot migration scripts kept around for re-runnable, test-anchored
operator chores. Most of the grain-rip / LGD-build path_b_* + build_lgd_*
+ backfill_concept_id_fk scripts were retired in the G6 tools/ prune
(2026-06-08) once their per-family migrations had landed; the surviving
script is the one with a Tier-A pytest pin.

| Script | Tier-A pin | Scope |
| --- | --- | --- |
| [`rename_partition_keys.py`](rename_partition_keys.py) | [`backend/tests/test_rename_partition_keys.py`](../../backend/tests/test_rename_partition_keys.py) | Rename `state=in_sXX` / `state=in_uXX` partition dirs to `state=<lgd-name-slug>` per ADR-0050; ships with `--apply` gate + sample manifest. |
