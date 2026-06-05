"""One-off driver to emit datasets/data/entities/state_codes.csv from the
committed LGD parsed snapshot (datasets/reference/lgd/states.csv) + the ISO
transcription seed (datasets/reference/state-iso-seed.csv). Run from repo root.
"""
from pathlib import Path

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.state_codes_csv import FILE_CLASS, emit


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    snapshot = repo_root / "datasets" / "reference" / "lgd" / "states.csv"
    iso_seed = repo_root / "datasets" / "reference" / "state-iso-seed.csv"
    out = repo_root / "datasets" / "data" / "entities" / "state_codes.csv"
    emit(
        lgd_snapshot_states_csv=snapshot,
        state_iso_seed_csv=iso_seed,
        out_path=out,
    )
    validate_csv(path=out, file_class=FILE_CLASS, repo_root=repo_root)
    rows = out.read_text(encoding="utf-8").splitlines()
    print(f"wrote {out.relative_to(repo_root).as_posix()} ({len(rows) - 1} rows)")


if __name__ == "__main__":
    main()
