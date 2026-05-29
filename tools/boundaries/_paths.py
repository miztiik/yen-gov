"""Hive partition path + layer_id derivation for boundary geometry shards.

Shared by ``tools/boundaries/snapshot.py`` (forward-going re-fetches) and
``tools/boundaries/migrate_to_hive_layout.py`` (one-shot initial migration
in T.0d chunk 3) so the on-disk layout is decided in exactly one place.

T.0d §1 admin-spine layout (locked 2026-05-22)::

    datasets/boundaries/
      boundary_layers.parquet                       # control table
      in/
        country/all.geojson                         # india-soi
        states/all.geojson                          # india-states
        districts/all.geojson                       # india-districts
        ac/state=in_<lc>/all.geojson                # per-state AC layer
        subdistricts/state=in_<lc>/all.geojson      # per-state subdistrict
        villages/state=in_<lc>/district=<lgd>/all.geojson  # per-district village shard

``layer_id`` mirrors the partition path under the dot grammar required by
``boundary-layers.schema.json`` (regex ``^boundaries\\.in\\.[a-z]+(\\.[a-z]+=[a-z0-9_]+)*$``).
The Hive key/value tokens (``state=in_s22``, ``district=603``) are
embedded verbatim so callers can build either form from the same args.
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
    "villages",
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
    "village",
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
    "villages": "village",
    "postal": "postal",
}


def derive_hive(
    *,
    kind: str,
    delim: str | None = None,
    state: str | None = None,
    district_lgd: str | None = None,
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
            with ``in_`` for the Hive key (``state=in_s22``).
        district_lgd: LGD district code as digit string (``603``); only
            valid when ``kind == "villages"`` today.
        ext: file extension (``geojson`` or ``pmtiles``).

    Returns:
        ``(partition_path, layer_id)`` where:

        * ``partition_path`` is repo-relative POSIX (e.g.
          ``boundaries/in/villages/state=in_s22/district=603/all.geojson``,
          ``boundaries/in/pc/delim=2024/all.geojson``).
          Matches the JSON Schema ``partition_path`` regex
          (``^boundaries/in/``).
        * ``layer_id`` is the dot-grammar equivalent (e.g.
          ``boundaries.in.villages.state=in_s22.district=603``,
          ``boundaries.in.pc.delim=2024``).
          Matches ``boundary-layers.schema.json:properties.layer_id.pattern``.

    Raises:
        ValueError: ``kind`` is not in ``KIND_TO_LEVEL`` (catches
            pipeline.json typos at compile time).
    """
    if kind not in KIND_TO_LEVEL:
        msg = f"unknown kind {kind!r}; expected one of {sorted(KIND_TO_LEVEL)}"
        raise ValueError(msg)
    parts_path: list[str] = [f"boundaries/in/{kind}"]
    parts_id: list[str] = [f"boundaries.in.{kind}"]
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
    return f"{'/'.join(parts_path)}/all.{ext}", ".".join(parts_id)


__all__ = ["KIND_TO_LEVEL", "Kind", "Level", "derive_hive"]
