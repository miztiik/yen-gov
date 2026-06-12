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
        subdistricts/state=<slug>/all.geojson       # per-state subdistrict
        villages/state=<slug>/district=<lgd>/all.geojson  # per-district village shard

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

Slug-only partition contract (2026-06-09, Hans+Max+Gregor converged
verdict on Item 1 of the G10 follow-on reconciliation): the ``state=``
Hive value is an LGD-name slug verbatim (e.g. ``state=tamil-nadu``,
``state=delhi``), never the legacy ECI-derived ``in_<lc>`` form
(``state=in_s22``, ``state=in_u05``). The plan-doc round-8 decommissioned
``eci_st_code`` as "a column, join key, or partition value"; the
``state_slug`` parameter rename is the compile-time gate that forces
every caller through the type-checker. Callers that hold an ECI code
must translate via ``_eci_to_slug()`` at the call site.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal


def _resolve_raw_dir(
    cli_arg: str | None,
    env_var_name: str,
    config_default: str,
    repo_root: Path,
) -> Path:
    """Three-tier resolution: CLI flag > env-var > config default.

    Lets every boundaries tool (``snapshot.py`` + the ``lift_*.py`` family)
    point their ``.runtime/raw/boundaries/`` cache at a shared on-disk
    root so multiple git worktrees re-use one cache instead of each
    re-downloading the same multi-GB upstream bundles. The brief is at
    [TODO/20260612-shared-raw-cache-tools.md] (composes orthogonally
    with PR #956's URL-keyed dedup INSIDE the cache dir; this resolver
    only moves the ROOT of that dir).

    ``cli_arg`` and the env-var value, when set, are treated as either an
    absolute path or a path relative to the OPERATOR's cwd (so they
    can point at a shared cache directory on a different volume). The
    ``config_default`` is resolved relative to ``repo_root`` (per
    ADR-0003: intermediate artifacts under ``.runtime/`` scoped to the
    repo by default).

    Args:
        cli_arg: Value of the ``--raw-dir`` CLI flag, or ``None`` when
            the operator did not pass it.
        env_var_name: Environment-variable name to consult as the second
            tier (e.g. ``"YENGOV_BOUNDARIES_RAW_DIR"``).
        config_default: The legacy default path string, repo-relative
            (e.g. ``".runtime/raw/boundaries"``).
        repo_root: Absolute ``Path`` to the repo root; only used when
            falling back to ``config_default``.

    Returns:
        An absolute ``Path`` to the cache root the caller should use.
    """
    if cli_arg:
        return Path(cli_arg).expanduser().resolve()
    env_val = os.environ.get(env_var_name)
    if env_val:
        return Path(env_val).expanduser().resolve()
    return (repo_root / config_default).resolve()

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

# Regex matching the ECI state-code shape (S01-S29 / U01-U09). Used by
# ``derive_hive`` to reject an accidental ECI-code pass-through on the
# ``state_slug=`` parameter (callers must call ``_eci_to_slug()`` first).
_ECI_STATE_CODE_RE = re.compile(r"^[SU][0-9]{2}$")

# Repo root (parent of ``tools/``); used by ``_eci_to_slug`` as the
# default search root for ``datasets/taxonomy/lgd_states.json``.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Module-level cache for the ECI->slug map. Built lazily on first call;
# the lgd_states.json file is hand-authored canonical data so the read
# is cheap once per process.
_ECI_TO_SLUG_CACHE: dict[str, str] | None = None


def _eci_to_slug(state_eci_code: str, lgd_states_path: Path | None = None) -> str:
    """Map an ECI state code (``S22``, ``U05``, ...) to its LGD-name slug
    (``tamil-nadu``, ``delhi``, ...).

    The canonical mapping lives in ``datasets/taxonomy/lgd_states.json``
    (same source ``backend/yen_gov/canonical/writer.py::_eci_to_lgd_slug_case_sql``
    reads from per ADR-0050). This helper exists so caller-side
    translation at the ``derive_hive`` boundary stays a one-liner;
    every caller that still holds an ECI code (the ``lift_*.py`` family
    + ``snapshot.py`` driving from ``pipeline.json``) wraps its ``eci``
    variable in ``_eci_to_slug(eci)`` before passing it to
    ``derive_hive(state_slug=...)``.

    BRIEF CORRECTION (2026-06-09): the orchestrator brief named
    ``datasets/data/entities/state_iso_seed.csv`` as the source file.
    That CSV is keyed on ``lgd_state_code`` (the LGD numeric id, 1-38)
    and does NOT carry ``eci_st_code`` at all, so it can't satisfy this
    helper's signature. ``datasets/taxonomy/lgd_states.json`` is the
    canonical (ECI -> slug) source already used by
    ``writer.py::_eci_to_lgd_slug_case_sql`` per ADR-0050. The brief's
    INTENT - read the slug from a canonical store, never hardcode -
    is preserved verbatim; only the source file name moves from a CSV
    that doesn't carry the join key to the JSON that does.

    Args:
        state_eci_code: ECI st_code in canonical form (``S01``..``S29``,
            ``U01``..``U09``).
        lgd_states_path: Override for the lgd_states.json path. Defaults
            to ``<repo_root>/datasets/taxonomy/lgd_states.json``. Tests
            pass a fixture path; production callers leave it as None.

    Returns:
        The matching slug verbatim from lgd_states.json (e.g.
        ``"tamil-nadu"``, ``"delhi"``).

    Raises:
        ValueError: ``state_eci_code`` is not in the lgd_states.json
            map (catches typos + future ECI codes that haven't been
            seeded yet).
    """
    global _ECI_TO_SLUG_CACHE
    if lgd_states_path is not None:
        # Test path: bypass cache, read the override, return without
        # mutating module state.
        doc = json.loads(lgd_states_path.read_text(encoding="utf-8"))
        built = {str(s["eci_st_code"]): str(s["slug"]) for s in doc["states"]}
        slug = built.get(state_eci_code)
        if slug is None:
            msg = (
                f"unknown ECI state code {state_eci_code!r}; not in "
                f"{lgd_states_path}"
            )
            raise ValueError(msg)
        return slug
    if _ECI_TO_SLUG_CACHE is None:
        default_path = (
            _REPO_ROOT / "datasets" / "taxonomy" / "lgd_states.json"
        )
        doc = json.loads(default_path.read_text(encoding="utf-8"))
        _ECI_TO_SLUG_CACHE = {
            str(s["eci_st_code"]): str(s["slug"]) for s in doc["states"]
        }
    slug = _ECI_TO_SLUG_CACHE.get(state_eci_code)
    if slug is None:
        msg = (
            f"unknown ECI state code {state_eci_code!r}; not in "
            "datasets/taxonomy/lgd_states.json"
        )
        raise ValueError(msg)
    return slug


def derive_hive(
    *,
    kind: str,
    delim: str | None = None,
    state_slug: str | None = None,
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
        state_slug: LGD-name slug for the state shard (e.g.
            ``"tamil-nadu"``, ``"delhi"``). Embedded verbatim in the
            ``state=<value>`` Hive segment. The ``state`` parameter was
            renamed to ``state_slug`` 2026-06-09 (Hans+Max+Gregor
            converged verdict, Item 1 of the G10 follow-on
            reconciliation) so an accidental ECI-code pass becomes a
            compile-time + runtime error. Callers that still hold an
            ECI code must translate via ``_eci_to_slug()`` first.
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
            pipeline.json typos at compile time); ``state_slug`` matches
            the ECI state-code shape (``^[SU][0-9]{2}$``) - catches an
            accidental ECI-code pass-through that pre-2026-06-09 silently
            became the legacy ``state=in_<lc>`` partition value;
            electoral layer is missing the required ``delim`` argument.
    """
    if kind not in KIND_TO_LEVEL:
        msg = f"unknown kind {kind!r}; expected one of {sorted(KIND_TO_LEVEL)}"
        raise ValueError(msg)
    if state_slug is not None and _ECI_STATE_CODE_RE.match(state_slug):
        msg = (
            f"state_slug={state_slug!r} matches the ECI state-code shape "
            "[SU][0-9]{2}; partition values must be LGD-name slugs "
            "(e.g. 'tamil-nadu', 'delhi'). Call _eci_to_slug() at the "
            "call site to translate ECI codes before passing to "
            "derive_hive."
        )
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
    if state_slug is not None:
        parts_path.append(f"state={state_slug}")
        parts_id.append(f"state={state_slug}")
    if district_lgd is not None:
        parts_path.append(f"district={district_lgd}")
        parts_id.append(f"district={district_lgd}")
    if ulb_lgd is not None:
        parts_path.append(f"ulb={ulb_lgd}")
        parts_id.append(f"ulb={ulb_lgd}")
    return f"{'/'.join(parts_path)}/all.{ext}", ".".join(parts_id)


__all__ = ["KIND_TO_LEVEL", "Kind", "Level", "_eci_to_slug", "derive_hive"]
