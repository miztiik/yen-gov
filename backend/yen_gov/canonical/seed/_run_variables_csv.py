"""One-off driver to emit datasets/data/variables.csv from
datasets/taxonomy/indicators.json. Run from repo root.
"""
from pathlib import Path

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.variables_csv import FILE_CLASS, emit


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    indicators_json = repo_root / "datasets" / "taxonomy" / "indicators.json"
    out = repo_root / "datasets" / "data" / "variables.csv"
    emit(indicators_json=indicators_json, out_path=out)
    validate_csv(path=out, file_class=FILE_CLASS, repo_root=repo_root)
    rows = out.read_text(encoding="utf-8").splitlines()
    print(f"wrote {out.relative_to(repo_root).as_posix()} ({len(rows) - 1} rows)")


if __name__ == "__main__":
    main()
