"""Hive partition path + layer_id derivation for boundary geometry shards.

Shared by ``tools/boundaries/snapshot.py`` (forward-going re-fetches). The
original one-shot migrator (``migrate_to_hive_layout.py``) was retired in
the G6 tools/ prune 2026-06-08 once T.0d chunk 3 had landed; the path
derivation it shared with snapshot.py is preserved here for any future
layout changes.

T.0d section 1 admin-spine layout (locked 2026-05-22)::

    datasets/boundaries/
      boundary_layers.parquet                       # control table
      in/
        country/all.geojson                         # india-soi
        states/all.geojson                          # india-states
        districts/all.geojson                       # india-districts
        subdistricts/state=in_<lc>/all.geojson      # per-state subdistrict
        villages/state=in_<lc>/district=<lgd>/all.geojson  # per-district village shard

G10 electoral-spine layout (section 4 EL2 of
TODO/20260603-data-and-charting-platform-reset-plan.md, 2026-06-09)::

    datasets/boundaries/
      electoral/
        delim=<year>/
          ac/state=<slug>/all.geojson              # per-state AC layer
          pc/all.geojson                           # country-wide PC layer

The admin spine (``boundaries/in/...``) and the electoral spine
(``boundaries/electoral/delim=<year>/...``) sit as peers under
``datasets/boundaries/``; both are addressed via this builder.

``layer_id`` mirrors the partition path under the dot grammar required by
``boundary-layers.schema.json`` (regex
``^boundaries\\.(in|electoral)(\\.[a-z]+(=[a-z0-9_-]+)?)+$`` after schema
v1.5). The Hive key/value tokens (``state=tamil-nadu``, ``district=603``,
``delim=2008``) are embedded verbatim so callers can build either form
from the same args.
"""

from __future__ import annotations

from typing import Literal

# pipeline.json uses the plural kind name (``states``, ``districts``,
# ``subdistricts``, ``villages``); ``boundary-layers.schema.json`` uses
# the singular level (``state``, ``district``, ``subdistrict``,
# ``village``). The level is what lands in the parquet column; the kind
# is what lands in the Hive path segment. Both are referenced below.
Kind = Literal[
    "country",
    "states",
    "districts",
    "ac",
    "pc",
    "subdistricts",
    "blocks",
    "panchayats",
    "villages",
    "wards",
    "postal",
]

Level = Literal[
    "country",
    "state",
    "district",
    "ac",
    "pc",
    "subdistrict",
    "block",
    "panchayat",
    "village",
    "ward",
    "postal",
]

KIND_TO_LEVEL: dict[Kind, Level] = {
    "country": "country",
    "states": "state",
    "districts": "district",
    "ac": "ac",
    "pc": "pc",
    "subdistricts": "subdistrict",
    "blocks": "block",
    "panchayats": "panchayat",
    "villages": "village",
    "wards": "ward",
    "postal": "postal",
}


def derive_hive(
    *,
    kind: str,
    delim: str | None = None,
    state: str | None = None,
    district_lgd: str | None = None,
    ulb_lgd: str | None = None,
    ext: str = "geojson",
) -> tuple[str, str]:
    """Return ``(partition_path, layer_id)`` for a boundary shard.

    Args:
        kind: pipeline.json ``kind`` value (plural form, e.g. ``villages``).
        delim: 4-digit year of the Delimitation Commission Order this
            boundary set reflects (``"2024"``, ``"2008"``). Used by
            electoral-constituency layers (``kind in {"ac", "pc"}``) to
            disambiguate pre/post-Delim geometries; None for non-electoral
            layers. Inserted as a ``delim=<year>`` Hive segment immediately
            after the kind segment so per-state/per-district sub-partitions
            still nest below it.
        state: ECI state code (``S22``, ``U08``); lowercased + prefixed
            with ``in_`` for the Hive key (``state=tamil-nadu``).
        district_lgd: LGD district code as digit string (``603``); valid
            for nested per-district layers (``kind in {"villages", "panchayats"}``).
        ulb_lgd: LGD ULB code as digit string (``802743``); valid for
            nested per-ULB layers (``kind == "wards"``). Mutually
            exclusive with ``district_lgd`` per the C.3.a ULB-keyed
            partition rationale (a ULB can span multiple districts;
            LGD treats ULB as the primary urban entity).
        ext: file extension (``geojson`` or ``pmtiles``).

    Returns:
        ``(partition_path, layer_id)`` where:

        * ``partition_path`` is repo-relative POSIX (e.g.
          ``boundaries/in/villages/state=tamil-nadu/district=603/all.geojson``,
          ``boundaries/in/wards/state=tamil-nadu/ulb=802743/all.geojson``,
          ``boundaries/electoral/delim=2008/ac/state=tamil-nadu/all.geojson``,
          ``boundaries/electoral/delim=2024/pc/all.geojson``).
          Matches the JSON Schema ``partition_path`` regex
          (``^boundaries/(in|electoral)/``).
        * ``layer_id`` is the dot-grammar equivalent (e.g.
          ``boundaries.in.villages.state=tamil-nadu.district=603``,
          ``boundaries.in.wards.state=tamil-nadu.ulb=802743``,
          ``boundaries.electoral.delim=2008.ac.state=tamil-nadu``,
          ``boundaries.electoral.delim=2024.pc``).
          Matches ``boundary-layers.schema.json:properties.layer_id.pattern``.

    Raises:
        ValueError: ``kind`` is not in ``KIND_TO_LEVEL`` (catches
            pipeline.json typos at compile time).
    """
    if kind not in KIND_TO_LEVEL:
        msg = f"unknown kind {kind!r}; expected one of {sorted(KIND_TO_LEVEL)}"
        raise ValueError(msg)
    # G10 (section 4 EL2 of TODO/20260603-data-and-charting-platform-
    # reset-plan.md, 2026-06-09): electoral constituency layers live
    # under ``boundaries/electoral/delim=<year>/<grain>/...`` so each
    # ECI Delimitation Commission Order publishes its own coexisting
    # boundary set; the admin spine stays under ``boundaries/in/``.
    is_electoral = kind in {"ac", "pc"}
    section = "electoral" if is_electoral else "in"
    parts_path: list[str] = [f"boundaries/{section}/"]
    parts_id: list[str] = [f"boundaries.{section}"]
    if is_electoral:
        if delim is None:
            msg = (
                f"kind={kind!r} is electoral; ``delim`` is required to "
                "select the Delimitation Commission Order vintage "
                "(boundaries/electoral/delim=<year>/...)."
            )
            raise ValueError(msg)
        parts_path[-1] = f"boundaries/{section}/delim={delim}/{kind}"
        parts_id.append(f"delim={delim}")
        parts_id.append(kind)
    else:
        parts_path[-1] = f"boundaries/{section}/{kind}"
        parts_id.append(kind)
        if delim is not None:
            parts_path.append(f"delim={delim}")
            parts_id.append(f"delim={delim}")
    if state is not None:
        state_key = f"in_{state.lower()}"
        parts_path.append(f"state={state_key}")
        parts_id.append(f"state={state_key}")
    if district_lgd is not None:
        parts_path.append(f"district={district_lgd}")
        parts_id.append(f"district={district_lgd}")
    if ulb_lgd is not None:
        parts_path.append(f"ulb={ulb_lgd}")
        parts_id.append(f"ulb={ulb_lgd}")
    return f"{'/'.join(parts_path)}/all.{ext}", ".".join(parts_id)


__all__ = ["KIND_TO_LEVEL", "Kind", "Level", "derive_hive"]
