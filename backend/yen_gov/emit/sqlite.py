"""SQLite emitter for one (event, state) slice.

Reads the validated JSON under `datasets/elections/<event>/<state>/` and writes
`results.sqlite` next to it. Per docs/architecture/backend/emit-sqlite.md the layout is documented in
`docs/reference/sqlite-schema.md` and versioned via `PRAGMA user_version`.

Determinism: the same JSON input must produce a byte-identical .sqlite output,
so PR diffs only appear when JSON changed. We achieve this by:
  - sorting all INSERTs by primary key,
  - rewriting in a temp file then atomically replacing the destination,
  - never embedding wall-clock timestamps.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path

USER_VERSION = 1

_DDL = """
CREATE TABLE parties (
  eci_code   TEXT PRIMARY KEY,
  short_name TEXT NOT NULL,
  full_name  TEXT
);

CREATE TABLE constituencies (
  eci_no       INTEGER PRIMARY KEY,
  name         TEXT NOT NULL,
  votes_polled INTEGER
);

CREATE TABLE candidates (
  constituency_eci_no INTEGER NOT NULL REFERENCES constituencies(eci_no),
  rank                INTEGER NOT NULL,
  name                TEXT NOT NULL,
  party_eci_code      TEXT REFERENCES parties(eci_code),
  party_short         TEXT NOT NULL,
  votes               INTEGER NOT NULL,
  vote_share_pct      REAL NOT NULL,
  is_winner           INTEGER NOT NULL DEFAULT 0,
  is_nota             INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (constituency_eci_no, rank)
);

CREATE INDEX idx_candidates_party  ON candidates(party_short);
CREATE INDEX idx_candidates_winner ON candidates(is_winner) WHERE is_winner = 1;

CREATE VIEW party_totals AS
  SELECT party_short,
         COUNT(*) FILTER (WHERE is_winner = 1) AS seats_won,
         SUM(votes)                            AS votes
  FROM candidates
  WHERE is_nota = 0
  GROUP BY party_short
  ORDER BY seats_won DESC, votes DESC;
"""


def emit_state_sqlite(*, state_dir: Path, output_path: Path | None = None) -> Path:
    """Build `results.sqlite` from the JSON under `state_dir`.

    `state_dir` must contain `parties.json` and `results/<n>.json` files. The
    SQLite file is written atomically: a temp file in the same directory, then
    `os.replace`. Returns the final path.
    """
    parties_doc = _load_json(state_dir / "parties.json")
    result_files = sorted(
        (state_dir / "results").glob("*.json"),
        key=lambda p: int(p.stem),
    )
    if not result_files:
        raise ValueError(f"no per-AC results found under {state_dir}/results/")

    constituencies = [_load_json(p) for p in result_files]
    output_path = output_path or (state_dir / "results.sqlite")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=".results-", suffix=".sqlite", dir=str(output_path.parent),
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        # Fresh DB each time — deterministic and avoids stale rows after edits.
        if tmp_path.exists():
            tmp_path.unlink()
        conn = sqlite3.connect(tmp_path)
        try:
            conn.executescript(_DDL)
            conn.execute(f"PRAGMA user_version = {USER_VERSION}")
            _insert_parties(conn, parties_doc)
            _insert_constituencies_and_candidates(conn, constituencies)
            conn.commit()
        finally:
            conn.close()
        os.replace(tmp_path, output_path)
        return output_path
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _insert_parties(conn: sqlite3.Connection, parties_doc: dict) -> None:
    rows = sorted(
        (
            (p["eci_code"], p["short_name"], p.get("full_name"))
            for p in parties_doc.get("parties", [])
            if p.get("eci_code")
        ),
        key=lambda r: r[0],
    )
    conn.executemany(
        "INSERT INTO parties (eci_code, short_name, full_name) VALUES (?, ?, ?)",
        rows,
    )


def _insert_constituencies_and_candidates(
    conn: sqlite3.Connection, constituencies: list[dict],
) -> None:
    constituency_rows: list[tuple] = []
    candidate_rows: list[tuple] = []
    for cr in constituencies:
        eci_no = cr["eci_no"]
        constituency_rows.append((
            eci_no,
            cr.get("constituency_name") or "",
            (cr.get("totals") or {}).get("votes_polled"),
        ))
        for cand in cr.get("candidates", []):
            candidate_rows.append((
                eci_no,
                cand["rank"],
                cand["name"],
                cand.get("party_eci_code"),
                cand["party_short"],
                cand["votes"],
                cand["vote_share_pct"],
                1 if cand.get("is_winner") else 0,
                0,
            ))
        nota = cr.get("nota") or {}
        if "votes" in nota:
            # Place NOTA at rank = (last rank + 1) so the (constituency, rank)
            # PK doesn't collide. Real candidates always have rank >= 1.
            nota_rank = max((c["rank"] for c in cr.get("candidates", [])), default=0) + 1
            candidate_rows.append((
                eci_no,
                nota_rank,
                "NOTA",
                None,
                "NOTA",
                nota["votes"],
                nota.get("vote_share_pct", 0.0),
                0,
                1,
            ))

    constituency_rows.sort(key=lambda r: r[0])
    candidate_rows.sort(key=lambda r: (r[0], r[1]))

    conn.executemany(
        "INSERT INTO constituencies (eci_no, name, votes_polled) VALUES (?, ?, ?)",
        constituency_rows,
    )
    conn.executemany(
        "INSERT INTO candidates (constituency_eci_no, rank, name, party_eci_code,"
        " party_short, votes, vote_share_pct, is_winner, is_nota)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        candidate_rows,
    )
