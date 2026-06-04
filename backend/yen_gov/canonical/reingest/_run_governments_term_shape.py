"""One-off driver for B2b.3: emit the term-shape triple
(``entities/office.csv`` + ``entities/holder.csv`` +
``datapoints/office_holdings.csv``) from the two surviving parquets under
``datasets/governments/``. Run from repo root.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.governments_term_shape import (
    FILE_CLASS_HOLDER,
    FILE_CLASS_HOLDINGS,
    FILE_CLASS_OFFICE,
    emit,
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    parquet_dir = repo_root / "datasets" / "governments"
    geo_entities_csv = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    party_entities_csv = repo_root / "datasets" / "data" / "entities" / "party.csv"
    out_data_dir = repo_root / "datasets" / "data"

    emitted = emit(
        parquet_dir=parquet_dir,
        geo_entities_csv=geo_entities_csv,
        party_entities_csv=party_entities_csv,
        out_data_dir=out_data_dir,
    )
    for file_class in (FILE_CLASS_OFFICE, FILE_CLASS_HOLDER, FILE_CLASS_HOLDINGS):
        validate_csv(
            path=emitted[file_class],
            file_class=file_class,
            repo_root=repo_root,
        )
    for file_class, path in emitted.items():
        print(f"wrote {path.relative_to(repo_root).as_posix()} [{file_class}]")


if __name__ == "__main__":
    main()
