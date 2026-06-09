"""One-shot repoint: rewrite the ``out`` field on every electoral entry in
``tools/boundaries/pipeline.json`` so it lands under the G10 electoral
subtree (``datasets/boundaries/electoral/delim=<year>/<kind>/...``)
instead of the legacy admin-spine path
(``datasets/boundaries/in/{ac,pc}/...``) that G10 vacated.

Kept (not deleted) as the receipt of HOW the G10 follow-on bulk-edit was
performed. Per CLAUDE.md sect 10, structural fixes only — no monkey patches.

Context: G10 (PR #838) moved the 31 AC and 1 PC geometry files from
``datasets/boundaries/in/{ac,pc}/...`` to
``datasets/boundaries/electoral/delim=<year>/<kind>/...``. PR #842
backfilled ``delimitation_vintage`` on the 31 + 1 electoral entries in
pipeline.json so future calls to ``derive_hive(...)`` don't raise. The
remaining gap was the ``out`` field on each electoral entry — still
encoded the legacy admin-spine path. Any future ``python
tools/boundaries/snapshot.py --kind ac`` would have written geometry to
the legacy path G10 deliberately vacated.

Doctrinal choice: ``outputs_dir`` stays at ``datasets/boundaries/in``
(non-electoral kinds ``country``, ``states``, ``districts``, ...
legitimately use the admin-spine root); only the 32 electoral entries
get the relative-up form ``../electoral/...``. Updating ``outputs_dir``
itself would cascade to every non-electoral entry — out of scope for
this PR.

The new ``out`` for each electoral entry is derived from
``tools/boundaries/_paths.py::derive_hive(kind=, state=, delim=, ext=)``
so the canonical Hive contract is the single source of truth. The
``ext`` is preserved verbatim from the current ``out`` (``.pmtiles`` for
AC tippecanoe outputs, ``.geojson`` for the PC raw passthrough). The
basename becomes ``all.<ext>`` (derive_hive's convention) — the state
distinction now lives in the ``state=<key>/`` path segment instead of
being duplicated in the legacy ``<S##>-ac.<ext>`` basename. The PC
basename was already ``all.geojson``, so no semantic change there.

Idempotent: re-running on an already-repointed file is a no-op (entries
whose ``out`` already starts with ``../electoral/`` are skipped).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _paths import derive_hive  # noqa: E402

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

    Strategy: call ``derive_hive`` with the entry's (kind, state, delim,
    ext) to get the canonical Hive path under ``boundaries/electoral/...``;
    then express it relative to ``outputs_dir=datasets/boundaries/in`` by
    prefixing ``../`` and stripping the ``boundaries/`` prefix.
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
    # accepts that and omits the ``state=`` segment.
    partition_path, _layer_id = derive_hive(
        kind=str(kind),
        delim=str(delim) if delim is not None else None,
        state=str(state) if state is not None else None,
        ext=ext,
    )
    # derive_hive returns paths rooted at ``boundaries/...`` (e.g.
    # ``boundaries/electoral/delim=2008/ac/state=in_s22/all.pmtiles``).
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
        if isinstance(out_value, str) and out_value.startswith("../electoral/"):
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
