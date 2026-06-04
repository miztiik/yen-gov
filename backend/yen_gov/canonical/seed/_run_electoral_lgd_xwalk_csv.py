"""One-off driver to emit datasets/data/entities/electoral_lgd_xwalk.csv
from datasets/taxonomy/lgd_{states,acs,districts}.json + lgd_ac_pc_district_map.json.
Run from repo root.
"""
from pathlib import Path

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.electoral_lgd_xwalk_csv import FILE_CLASS, emit


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    states_json = repo_root / "datasets" / "taxonomy" / "lgd_states.json"
    acs_json = repo_root / "datasets" / "taxonomy" / "lgd_acs.json"
    districts_json = repo_root / "datasets" / "taxonomy" / "lgd_districts.json"
    map_json = repo_root / "datasets" / "taxonomy" / "lgd_ac_pc_district_map.json"
    out = repo_root / "datasets" / "data" / "entities" / "electoral_lgd_xwalk.csv"
    emit(
        lgd_states_json=states_json,
        lgd_acs_json=acs_json,
        lgd_districts_json=districts_json,
        ac_pc_district_map_json=map_json,
        out_path=out,
    )
    validate_csv(path=out, file_class=FILE_CLASS, repo_root=repo_root)
    rows = out.read_text(encoding="utf-8").splitlines()
    print(f"wrote {out.relative_to(repo_root).as_posix()} ({len(rows) - 1} rows)")


if __name__ == "__main__":
    main()
