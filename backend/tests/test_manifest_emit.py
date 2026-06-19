"""Contract tests for the no-scan manifest emitter (``canonical/manifest.py``).

Row 7 (manifest replace): :func:`emit_manifest` replaces the dead
Parquet-scanning regen body that lived in ``canonical/writer.py``
(``_regenerate_manifest``). These tests pin:

- byte-identity of ``datasets/manifest.json`` modulo the ``generated_at``
  wall-clock stamp (the gate);
- the ``deprecations`` ledger is preserved verbatim;
- ``tables`` is always ``[]`` and the emitter NEVER scans the on-disk tree
  (the no-scan oracle: stray Parquet files are not enumerated);
- determinism modulo ``generated_at``;
- ``dry_run`` writes nothing;
- the emitter module carries no DuckDB / directory-walk scan code.
"""

from __future__ import annotations

import json
from pathlib import Path

from yen_gov.canonical import manifest as manifest_mod
from yen_gov.canonical.manifest import _DEPRECATIONS, emit_manifest
from yen_gov.core.schema_registry import schema_version

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_MANIFEST = REPO_ROOT / "datasets" / "manifest.json"


def _blank_generated_at(text: str) -> list[str]:
    """Split ``text`` into lines with the ``generated_at`` value neutralised,
    so two manifests differing only by their wall-clock stamp compare equal."""
    out: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith('"generated_at":'):
            out.append('  "generated_at": "<STAMP>",')
        else:
            out.append(line)
    return out


def test_emit_manifest_byte_identical_to_committed_modulo_generated_at(
    tmp_path: Path,
) -> None:
    """The gate: regenerating ``manifest.json`` changes only ``generated_at``."""
    datasets = tmp_path / "datasets"
    datasets.mkdir()

    out = emit_manifest(datasets)
    assert out == datasets / "manifest.json"

    emitted = out.read_text(encoding="utf-8")
    committed = COMMITTED_MANIFEST.read_text(encoding="utf-8")
    assert _blank_generated_at(emitted) == _blank_generated_at(committed)


def test_emit_manifest_tables_always_empty_no_scan(tmp_path: Path) -> None:
    """No-scan oracle: stray Parquet files under the tree are NOT enumerated.

    The retired ``_regenerate_manifest`` globbed ``*.parquet`` /
    ``*/dim_*.parquet`` / ``taxonomy/*.parquet`` and would have produced a
    non-empty ``tables``. The replacement is a pure stamp.
    """
    datasets = tmp_path / "datasets"
    (datasets / "elections").mkdir(parents=True)
    (datasets / "elections" / "election_results.parquet").write_bytes(b"PAR1stub")
    (datasets / "elections" / "dim_party_alliances.parquet").write_bytes(b"PAR1stub")
    (datasets / "taxonomy").mkdir()
    (datasets / "taxonomy" / "entities.parquet").write_bytes(b"PAR1stub")

    emit_manifest(datasets)
    payload = json.loads((datasets / "manifest.json").read_text(encoding="utf-8"))
    assert payload["tables"] == []


def test_emit_manifest_deprecations_preserved_verbatim(tmp_path: Path) -> None:
    datasets = tmp_path / "datasets"
    datasets.mkdir()

    emit_manifest(datasets)
    payload = json.loads((datasets / "manifest.json").read_text(encoding="utf-8"))

    assert payload["deprecations"] == _DEPRECATIONS
    committed = json.loads(COMMITTED_MANIFEST.read_text(encoding="utf-8"))
    assert payload["deprecations"] == committed["deprecations"]


def test_emit_manifest_stamps_schema_and_version(tmp_path: Path) -> None:
    datasets = tmp_path / "datasets"
    datasets.mkdir()

    emit_manifest(datasets)
    payload = json.loads((datasets / "manifest.json").read_text(encoding="utf-8"))

    assert payload["$schema"] == "./schemas/manifest.schema.json"
    assert payload["$schema_version"] == schema_version("manifest.schema.json")
    assert payload["manifest_version"] == "1.0"


def test_emit_manifest_deterministic_modulo_generated_at(tmp_path: Path) -> None:
    d1 = tmp_path / "a"
    d1.mkdir()
    d2 = tmp_path / "b"
    d2.mkdir()

    emit_manifest(d1)
    emit_manifest(d2)

    t1 = (d1 / "manifest.json").read_text(encoding="utf-8")
    t2 = (d2 / "manifest.json").read_text(encoding="utf-8")
    assert _blank_generated_at(t1) == _blank_generated_at(t2)


def test_emit_manifest_dry_run_writes_nothing(tmp_path: Path) -> None:
    datasets = tmp_path / "datasets"
    datasets.mkdir()

    out = emit_manifest(datasets, dry_run=True)
    assert out == datasets / "manifest.json"
    assert not (datasets / "manifest.json").exists()
    # No leftover tempfile either.
    assert list(datasets.iterdir()) == []


def test_manifest_module_carries_no_scan_code() -> None:
    """Grep oracle: the emitter has no DuckDB import and no directory walk."""
    src = Path(manifest_mod.__file__).read_text(encoding="utf-8")
    assert "import duckdb" not in src
    assert ".glob(" not in src
    assert ".iterdir(" not in src
