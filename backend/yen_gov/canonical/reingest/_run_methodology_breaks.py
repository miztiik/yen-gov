"""One-off driver for B2b.4.1: emit ``datasets/data/methodology_breaks.csv``
from the surviving ``datasets/taxonomy/methodology_breaks.parquet``. Run
from repo root.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.methodology_breaks import FILE_CLASS, emit


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    parquet_path = (
        repo_root / "datasets" / "taxonomy" / "methodology_breaks.parquet"
    )
    out_path = repo_root / "datasets" / "data" / "methodology_breaks.csv"

    emitted = emit(parquet_path=parquet_path, out_path=out_path)
    validate_csv(path=emitted, file_class=FILE_CLASS, repo_root=repo_root)
    print(f"wrote {emitted.relative_to(repo_root).as_posix()}")


if __name__ == "__main__":
    main()
