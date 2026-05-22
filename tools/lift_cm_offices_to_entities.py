"""G.1.a entity-lift: append 31 office_bearer rows to entities.json.

One-shot script. Reads existing state rows + the 31 cm_terms.json
directory names, generates one office_bearer entity per state CM seat,
appends them to datasets/taxonomy/entities.json (with the schema
version bumped to 1.2), and prints a summary.

Run from repo root:
    python tools/lift_cm_offices_to_entities.py

Idempotent: re-running detects existing IN-<state>-CM rows and skips.

Text-mode insertion: preserves the file's existing dense single-line
row format. Only adds 31 lines + 2 blank-line separators + 1 schema
version bump; does NOT reformat the 145 existing district rows.
"""
from __future__ import annotations

import json
from pathlib import Path

ENTITIES_JSON = Path("datasets/taxonomy/entities.json")
CM_TERMS_DIR = Path("datasets/governments/in/states")


def _format_row(row: dict) -> str:
    """One-line JSON, sorted by canonical entity row column order."""
    # Stable order matching existing rows in entities.json
    keys = [
        "entity_id",
        "entity_type",
        "entity_level",
        "entity_code",
        "display_name",
        "parent_entity_id",
        "entity_valid_from",
        "entity_valid_to",
        "iso_3166_2",
        "lgd_code",
        "notes",
    ]
    parts = []
    for k in keys:
        if k in row:
            parts.append(f"{json.dumps(k)}: {json.dumps(row[k], ensure_ascii=False)}")
    return "{ " + ", ".join(parts) + " }"


def main() -> int:
    # Parse JSON for content lookup (state metadata + idempotency)
    payload = json.loads(ENTITIES_JSON.read_text(encoding="utf-8"))
    existing_ids = {row["entity_id"] for row in payload["entities"]}
    state_lookup = {
        row["entity_code"]: row
        for row in payload["entities"]
        if row["entity_type"] in ("state", "ut")
    }

    cm_state_codes = sorted(p.name for p in CM_TERMS_DIR.iterdir() if p.is_dir())

    new_rows: list[dict] = []
    skipped: list[str] = []
    for state_code in cm_state_codes:
        if state_code not in state_lookup:
            raise SystemExit(
                f"FATAL: cm_terms has state {state_code!r} but no entity row in entities.json"
            )
        state_row = state_lookup[state_code]
        parent_entity_id = state_row["entity_id"]
        new_entity_id = f"{parent_entity_id}-CM"

        if new_entity_id in existing_ids:
            skipped.append(new_entity_id)
            continue

        office_row = {
            "entity_id": new_entity_id,
            "entity_type": "office_bearer",
            "entity_level": "fiscal_actor",
            "entity_code": "CM",
            "display_name": f"Chief Minister of {state_row['display_name']}",
            "parent_entity_id": parent_entity_id,
            "entity_valid_from": state_row["entity_valid_from"],
            "entity_valid_to": state_row.get("entity_valid_to"),
            "iso_3166_2": None,
            "lgd_code": None,
            "notes": (
                f"Office identity for the Chief Minister seat of "
                f"{state_row['display_name']}. Tenure facts "
                "(start/end/person/party/regime) live in "
                "governments/governments_office_holdings.parquet keyed on "
                "office_id = entity_id. Per Plan \u00a70e.6 (G.1)."
            ),
        }
        new_rows.append(office_row)

    if not new_rows:
        print(f"No new rows to append. Already-existing office_bearer rows: {skipped}")
        return 0

    # Text-mode insertion: find the closing ']' of the entities array
    text = ENTITIES_JSON.read_text(encoding="utf-8")

    # Bump $schema_version (1.1 -> 1.2) — text replace, preserves formatting
    text = text.replace(
        '"$schema_version": "1.1"',
        '"$schema_version": "1.2"',
        1,
    )

    # Locate the closing "  ]\n}" tail
    tail = "\n  ]\n}\n"
    if not text.endswith(tail):
        # Fallback: try without trailing newline
        alt_tail = "\n  ]\n}"
        if not text.endswith(alt_tail):
            raise SystemExit(
                "FATAL: entities.json does not end with expected '  ]\\n}\\n' tail. "
                f"Last 100 chars: {text[-100:]!r}"
            )
        text = text[:-len(alt_tail)]
        rebuilt_tail = alt_tail
    else:
        text = text[:-len(tail)]
        rebuilt_tail = tail

    # Compose appended block: blank line + section comment line + 31 new rows
    # (the file already uses a blank line between sections, e.g. before districts)
    lines = [""]  # blank separator
    lines.append("    " + _format_row(new_rows[0]))
    for row in new_rows[1:]:
        # Add comma to previous line at end? Each row line ends with the row
        # itself; comma between is added on the prior line. Easier: append
        # comma to previous already-built entry.
        pass
    # Rebuild: each row is "    { ... }" with comma between, no trailing comma
    formatted_rows = ["    " + _format_row(r) for r in new_rows]
    # The existing tail's last entity row ALREADY has no trailing comma
    # (because it was the last element). We need to inject a comma after that
    # last existing row to introduce our new block.
    # The 'text' variable now ends mid-row (we stripped only the closing
    # "  ]\n}" tail). Its last char should be '}' from the last entity row.
    if not text.rstrip().endswith("}"):
        raise SystemExit(
            f"FATAL: expected text to end with a row's '}}' after tail strip. "
            f"Last 100 chars: {text[-100:]!r}"
        )

    # Add comma + newline after the existing last row, then blank line, then new rows
    new_text = (
        text.rstrip()  # remove any trailing whitespace
        + ",\n"  # comma to terminate the prior last row
        + "\n"  # blank line separator (matches existing district section blank)
        + ",\n".join(formatted_rows)
        + "\n"
        + rebuilt_tail
    )

    ENTITIES_JSON.write_text(new_text, encoding="utf-8")

    # Verify post-write file is still valid JSON
    reparsed = json.loads(ENTITIES_JSON.read_text(encoding="utf-8"))
    print(f"Appended {len(new_rows)} office_bearer rows.")
    print(f"Skipped (already existed): {len(skipped)} rows.")
    print(f"Total entities now: {len(reparsed['entities'])}")
    print(f"$schema_version: {reparsed['$schema_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
