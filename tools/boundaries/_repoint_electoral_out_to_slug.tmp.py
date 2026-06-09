"""One-shot repoint: rewrite the ``out`` field on every electoral AC entry
in ``tools/boundaries/pipeline.json`` so its ``state=`` Hive value is the
LGD-name slug (``state=tamil-nadu``) instead of the legacy ECI-derived
``state=in_<lc>`` form (``state=in_s22``).

Kept (not deleted) as the receipt of HOW the Item 1 bulk-edit was
performed. Per CLAUDE.md section 10, structural fixes only - no monkey
patches.

Context: PR #847 moved the 32 electoral ``out`` fields from the legacy
``ac/<S##>-ac.<ext>`` / ``pc/<delim>/all.<ext>`` admin-spine paths to
the new ``../electoral/delim=<year>/<grain>/state=in_<lc>/all.<ext>``
relative-up form. The Hans+Max+Gregor converged verdict (2026-06-09,
Item 1 of the G10 follow-on) decommissions the legacy ``state=in_<lc>``
Hive value in favour of LGD-name slug shape (``state=tamil-nadu``,
``state=delhi``). This script flips the 31 AC entries (the 1 PC entry
already has no ``state=`` segment - PC is national-wide).

Doctrinal anchors:
  * Plan-doc round-8 (CLAUDE.md + TODO/20260603-data-and-charting-
    platform-reset-plan.md) decommissioned ``eci_st_code`` as
    "a column, join key, or partition value".
  * Plan section 4 EL2 mandates
    ``boundaries/electoral/delim=<year>/state=<slug>/...`` verbatim.
  * OWID precedent (Max): data-lake URIs use human-readable namespaces;
    entity join key is the editorial NAME, never opaque publisher codes.
  * boundary-layers.schema.json v1.5 already widened the partition
    regex to ``[a-z0-9_-]+`` (accepts hyphenated slugs); no schema bump.

The replaced derive_hive call passes ``state_slug=_eci_to_slug(eci)`` so
the script exercises the new contract end-to-end. The PC entry (no state)
is untouched.

Idempotent: re-running on an already-repointed file is a no-op (entries
whose ``out`` already carries ``state=<slug>`` are skipped).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _paths import _eci_to_slug, derive_hive  # noqa: E402

PIPELINE_PATH = HERE / "pipeline.json"

ELECTORAL_KINDS = frozenset({"ac", "pc"})


def _extension_of(out_value: str) -> str:
    """Return the extension (without leading dot) of an existing ``out``
    field. Preserves the operator's choice of pmtiles vs geojson per entry.
    """
    suffix = Path(out_value).suffix
    if not suffix.startswith("."):
        msg = f"out={out_value!r} has no extension; cannot preserve format"
        raise ValueError(msg)
    return suffix[1:]


def _new_out_for(entry: dict[str, object]) -> str:
    """Compute the new ``out`` field for one electoral entry.

    Strategy: call ``derive_hive`` with the entry's
    ``(kind, state_slug, delim, ext)`` to get the canonical Hive path
    under ``boundaries/electoral/...``; then express it relative to
    ``outputs_dir=datasets/boundaries/in`` by prefixing ``../`` and
    stripping the ``boundaries/`` prefix. ECI codes in the
    ``state`` field translate via ``_eci_to_slug()`` at the boundary.
    """
    kind = entry.get("kind")
    state = entry.get("state")
    delim = entry.get("delimitation_vintage")
    out_value = entry.get("out")
    if not isinstance(out_value, str):
        msg = f"entry kind={kind!r} state={state!r} has no string ``out``"
        raise ValueError(msg)
    ext = _extension_of(out_value)
    # ``state`` may be None for PC (country-wide layer). derive_hive
    # accepts that and omits the ``state=`` segment. When present,
    # translate the ECI st_code to the LGD-name slug at the call site
    # (Hans+Max+Gregor verdict, 2026-06-09).
    state_slug = _eci_to_slug(str(state)) if state is not None else None
    partition_path, _layer_id = derive_hive(
        kind=str(kind),
        delim=str(delim) if delim is not None else None,
        state_slug=state_slug,
        ext=ext,
    )
    # derive_hive returns paths rooted at ``boundaries/...`` (e.g.
    # ``boundaries/electoral/delim=2008/ac/state=tamil-nadu/all.pmtiles``).
    # ``outputs_dir`` is ``datasets/boundaries/in``, so to land at
    # ``datasets/boundaries/electoral/...`` the relative-up form is
    # ``../electoral/...``.
    if not partition_path.startswith("boundaries/electoral/"):
        msg = (
            f"derive_hive returned unexpected non-electoral path "
            f"{partition_path!r} for entry kind={kind!r} state={state!r}"
        )
        raise ValueError(msg)
    return "../" + partition_path[len("boundaries/") :]


def repoint(path: Path = PIPELINE_PATH) -> tuple[int, int, int]:
    """Repoint the file in-place.

    Returns ``(ac_rewritten, pc_rewritten, skipped_idempotent)``.

    Skip rule (idempotent): an entry is left untouched when its existing
    ``out`` does NOT contain ``state=in_`` and (for AC) already starts
    with ``../electoral/delim=`` - meaning a previous run already
    flipped it to slug form.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    inputs = payload.get("inputs", [])
    ac_rewritten = 0
    pc_rewritten = 0
    skipped = 0
    for entry in inputs:
        kind = entry.get("kind")
        if kind not in ELECTORAL_KINDS:
            continue
        out_value = entry.get("out")
        # PC has no state= partition; if it already lands under
        # ``../electoral/`` it's a no-op.
        if kind == "pc":
            if isinstance(out_value, str) and out_value.startswith("../electoral/"):
                skipped += 1
                continue
        # AC: skip only when both (a) already under ../electoral/ AND
        # (b) carries no legacy state=in_ substring (slug shape).
        if kind == "ac":
            if (
                isinstance(out_value, str)
                and out_value.startswith("../electoral/")
                and "state=in_" not in out_value
            ):
                skipped += 1
                continue
        entry["out"] = _new_out_for(entry)
        if kind == "ac":
            ac_rewritten += 1
        elif kind == "pc":
            pc_rewritten += 1
    payload["inputs"] = inputs
    # Match the existing file style: 2-space indent + trailing newline,
    # LF line endings via write_bytes (Python's write_text on Windows
    # would translate to CRLF without ``newline=""``).
    serialised = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(serialised.encode("utf-8"))
    return ac_rewritten, pc_rewritten, skipped


if __name__ == "__main__":
    ac, pc, skipped = repoint()
    print(f"ac_rewritten={ac} pc_rewritten={pc} skipped_idempotent={skipped}")
