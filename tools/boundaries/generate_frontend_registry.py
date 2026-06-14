"""Generate frontend boundary registry constants from boundary receipts.

The high-cardinality panchayat and ward inventories are derivative of
datasets/data/entities/boundary_encoding.csv. State display labels remain
hand-authored in frontend/src/lib/boundaries/sources.ts because the receipt
does not own citizen-facing copy.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


PANCHAYAT_UPSTREAM_URL = (
    "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/"
    "panchayats/LGD_Panchayats.geojsonl.7z"
)
WARD_UPSTREAM_URL = (
    "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/"
    "urban/SBM_Wards.geojsonl.7z"
)

PANCHAYAT_PATH_RE = re.compile(
    r"^datasets/boundaries/in/panchayats/state=(?P<slug>[^/]+)/district=(?P<id>\d+)/all\.geojson$"
)
PANCHAYAT_LAYER_RE = re.compile(
    r"^boundaries\.in\.panchayats\.state=in_(?P<code>[su]\d{2})\.district=(?P<id>\d+)$"
)
WARD_PATH_RE = re.compile(
    r"^datasets/boundaries/in/wards/state=(?P<slug>[^/]+)/ulb=(?P<id>\d+)/all\.geojson$"
)
WARD_LAYER_RE = re.compile(
    r"^boundaries\.in\.wards\.state=in_(?P<code>[su]\d{2})\.ulb=(?P<id>\d+)$"
)
STRING_RECORD_RE = re.compile(
    r"export const (?P<name>{name})\s*:\s*Readonly<Record<string, string>>\s*=\s*\{{(?P<body>.*?)\n\}};",
    re.DOTALL,
)
STRING_ENTRY_RE = re.compile(r"^\s*(?P<key>[SU]\d{2})\s*:\s*\"(?P<value>(?:[^\"\\]|\\.)*)\"\s*,?\s*$")


@dataclass(frozen=True)
class RegistryRow:
    state_code: str
    state_slug: str
    parent_id: int
    source_row: dict[str, str]

    @property
    def key(self) -> str:
        return f"{self.state_code}-{self.parent_id}"


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def state_sort_key(code: str) -> tuple[int, int, str]:
    prefix = 0 if code.startswith("S") else 1
    try:
        number = int(code[1:])
    except ValueError:
        number = 999
    return (prefix, number, code)


def parse_string_record(source_text: str, name: str) -> dict[str, str]:
    pattern = re.compile(STRING_RECORD_RE.pattern.format(name=re.escape(name)), re.DOTALL)
    match = pattern.search(source_text)
    if not match:
        raise ValueError(f"could not find {name} in frontend/src/lib/boundaries/sources.ts")
    out: dict[str, str] = {}
    for line in match.group("body").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        entry = STRING_ENTRY_RE.match(line)
        if not entry:
            raise ValueError(f"unsupported {name} entry line: {line!r}")
        out[entry.group("key")] = bytes(entry.group("value"), "utf-8").decode("unicode_escape")
    return out


def read_encoding_rows(path: Path) -> tuple[list[RegistryRow], list[RegistryRow]]:
    panchayat_rows: list[RegistryRow] = []
    ward_rows: list[RegistryRow] = []

    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            geojson_path = row.get("geojson_path", "")
            layer_id = row.get("layer_id", "")
            panchayat_path = PANCHAYAT_PATH_RE.match(geojson_path)
            if panchayat_path:
                layer = PANCHAYAT_LAYER_RE.match(layer_id)
                if not layer:
                    raise ValueError(f"panchayat receipt row has unexpected layer_id: {layer_id}")
                if layer.group("id") != panchayat_path.group("id"):
                    raise ValueError(f"panchayat id mismatch between path and layer_id: {geojson_path}")
                panchayat_rows.append(
                    RegistryRow(
                        state_code=layer.group("code").upper(),
                        state_slug=panchayat_path.group("slug"),
                        parent_id=int(panchayat_path.group("id")),
                        source_row=dict(row),
                    )
                )
                continue

            ward_path = WARD_PATH_RE.match(geojson_path)
            if ward_path:
                layer = WARD_LAYER_RE.match(layer_id)
                if not layer:
                    raise ValueError(f"ward receipt row has unexpected layer_id: {layer_id}")
                if layer.group("id") != ward_path.group("id"):
                    raise ValueError(f"ward id mismatch between path and layer_id: {geojson_path}")
                ward_rows.append(
                    RegistryRow(
                        state_code=layer.group("code").upper(),
                        state_slug=ward_path.group("slug"),
                        parent_id=int(ward_path.group("id")),
                        source_row=dict(row),
                    )
                )

    return panchayat_rows, ward_rows


def grouped_ids(rows: list[RegistryRow], family: str) -> dict[str, list[int]]:
    seen_keys: set[str] = set()
    slug_by_code: dict[str, str] = {}
    grouped: dict[str, list[int]] = {}
    for row in sorted(rows, key=lambda item: (state_sort_key(item.state_code), item.parent_id)):
        if row.key in seen_keys:
            raise ValueError(f"duplicate {family} registry key: {row.key}")
        seen_keys.add(row.key)
        prior_slug = slug_by_code.setdefault(row.state_code, row.state_slug)
        if prior_slug != row.state_slug:
            raise ValueError(
                f"inconsistent {family} slug for {row.state_code}: {prior_slug} vs {row.state_slug}"
            )
        grouped.setdefault(row.state_code, []).append(row.parent_id)
    return grouped


def slug_by_code(rows: list[RegistryRow]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        out.setdefault(row.state_code, row.state_slug)
    return dict(sorted(out.items(), key=lambda item: state_sort_key(item[0])))


def assert_labels(name: str, grouped: dict[str, list[int]], labels: dict[str, str]) -> None:
    missing = sorted((code for code in grouped if code not in labels), key=state_sort_key)
    extra = sorted((code for code in labels if code not in grouped), key=state_sort_key)
    if missing:
        raise ValueError(f"{name} is missing labels for generated states: {', '.join(missing)}")
    if extra:
        raise ValueError(f"{name} has labels for states absent from the generated receipt: {', '.join(extra)}")


def signature_payload(
    panchayat_rows: list[RegistryRow],
    ward_rows: list[RegistryRow],
    panchayat_labels: dict[str, str],
    ward_labels: dict[str, str],
) -> dict[str, object]:
    def rows_payload(rows: list[RegistryRow]) -> list[dict[str, str]]:
        return [
            row.source_row
            for row in sorted(rows, key=lambda item: (state_sort_key(item.state_code), item.parent_id))
        ]

    return {
        "panchayat_rows": rows_payload(panchayat_rows),
        "ward_rows": rows_payload(ward_rows),
        "panchayat_labels": dict(sorted(panchayat_labels.items(), key=lambda item: state_sort_key(item[0]))),
        "ward_labels": dict(sorted(ward_labels.items(), key=lambda item: state_sort_key(item[0]))),
    }


def compute_signature(payload: dict[str, object]) -> str:
    blob = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def ts_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def render_number_record(name: str, data: dict[str, list[int]]) -> list[str]:
    lines = [f"export const {name}: Readonly<Record<string, readonly number[]>> = {{"]
    for code, values in sorted(data.items(), key=lambda item: state_sort_key(item[0])):
        lines.append(f"  {code}: {render_number_array(values)},")
    lines.append("};")
    return lines


def render_string_record(name: str, data: dict[str, str], export: bool = False) -> list[str]:
    prefix = "export const" if export else "const"
    lines = [f"{prefix} {name}: Readonly<Record<string, string>> = {{"]
    for code, value in sorted(data.items(), key=lambda item: state_sort_key(item[0])):
        lines.append(f"  {code}: {ts_string(value)},")
    lines.append("};")
    return lines


def render_number_array(values: list[int]) -> str:
    if len(values) <= 10:
        return "[" + ", ".join(str(value) for value in values) + "]"
    chunks = []
    for idx in range(0, len(values), 10):
        chunk = values[idx : idx + 10]
        chunks.append("    " + ", ".join(str(value) for value in chunk) + ",")
    return "[\n" + "\n".join(chunks) + "\n  ]"


def render_generated_module(
    panchayat_rows: list[RegistryRow],
    ward_rows: list[RegistryRow],
    panchayat_labels: dict[str, str],
    ward_labels: dict[str, str],
) -> str:
    panchayat_groups = grouped_ids(panchayat_rows, "panchayat")
    ward_groups = grouped_ids(ward_rows, "ward")
    assert_labels("PANCHAYAT_STATE_NAMES", panchayat_groups, panchayat_labels)
    assert_labels("WARD_STATE_NAMES", ward_groups, ward_labels)

    payload = signature_payload(panchayat_rows, ward_rows, panchayat_labels, ward_labels)
    signature = compute_signature(payload)

    lines: list[str] = [
        "// Generated by tools/boundaries/generate_frontend_registry.py; do not edit by hand.",
        "// Source inputs: datasets/data/entities/boundary_encoding.csv + state labels in sources.ts.",
        f"// Input signature: sha256:{signature}",
        "",
        'import type { BoundaryEntry } from "./sources";',
        "",
        f"const PANCHAYAT_UPSTREAM_URL = {ts_string(PANCHAYAT_UPSTREAM_URL)};",
        f"const WARD_UPSTREAM_URL = {ts_string(WARD_UPSTREAM_URL)};",
        "",
    ]
    lines.extend(render_string_record("PANCHAYAT_STATE_SLUG_BY_CODE", slug_by_code(panchayat_rows)))
    lines.append("")
    lines.extend(render_string_record("PANCHAYAT_STATE_LABEL_BY_CODE", panchayat_labels))
    lines.append("")
    lines.extend(render_number_record("PANCHAYAT_DISTRICTS_BY_STATE", panchayat_groups))
    lines.extend(
        [
            "",
            "export const PANCHAYAT_BOUNDARY_BY_DISTRICT: Readonly<Record<string, BoundaryEntry>> = Object.freeze(",
            "  Object.fromEntries(",
            "    Object.entries(PANCHAYAT_DISTRICTS_BY_STATE).flatMap(([state_code, districts]) =>",
            "      districts.map((district_lgd): [string, BoundaryEntry] => {",
            "        const key = `${state_code}-${district_lgd}`;",
            "        const state_name = PANCHAYAT_STATE_LABEL_BY_CODE[state_code] ?? state_code;",
            "        return [",
            "          key,",
            "          {",
            "            id: `${key}-panchayat`,",
            "            label: `${state_name} \\u2014 District LGD ${district_lgd} (Gram Panchayats)`,",
            "            geojson_local_path: `boundaries/in/panchayats/state=${PANCHAYAT_STATE_SLUG_BY_CODE[state_code] ?? state_code.toLowerCase()}/district=${district_lgd}/all.geojson`,",
            "            geojson_url: PANCHAYAT_UPSTREAM_URL,",
            '            join_property: "gp_code",',
            "          },",
            "        ];",
            "      }),",
            "    ),",
            "  ),",
            ");",
            "",
        ]
    )
    lines.extend(render_string_record("WARD_STATE_SLUG_BY_CODE", slug_by_code(ward_rows)))
    lines.append("")
    lines.extend(render_string_record("WARD_STATE_LABEL_BY_CODE", ward_labels))
    lines.append("")
    lines.extend(render_number_record("WARDS_BY_STATE", ward_groups))
    lines.extend(
        [
            "",
            "export const WARD_BOUNDARY_BY_ULB: Readonly<Record<string, BoundaryEntry>> = Object.freeze(",
            "  Object.fromEntries(",
            "    Object.entries(WARDS_BY_STATE).flatMap(([state_code, ulbs]) =>",
            "      ulbs.map((ulb_lgd): [string, BoundaryEntry] => {",
            "        const key = `${state_code}-${ulb_lgd}`;",
            "        const state_name = WARD_STATE_LABEL_BY_CODE[state_code] ?? state_code;",
            "        return [",
            "          key,",
            "          {",
            "            id: `${key}-ward`,",
            "            label: `${state_name} \\u2014 ULB LGD ${ulb_lgd} (Wards)`,",
            "            geojson_local_path: `boundaries/in/wards/state=${WARD_STATE_SLUG_BY_CODE[state_code] ?? state_code.toLowerCase()}/ulb=${ulb_lgd}/all.geojson`,",
            "            geojson_url: WARD_UPSTREAM_URL,",
            '            join_property: "wardcode",',
            "          },",
            "        ];",
            "      }),",
            "    ),",
            "  ),",
            ");",
            "",
        ]
    )
    return "\n".join(lines)


def build_generated_text(root: Path) -> str:
    encoding_path = root / "datasets" / "data" / "entities" / "boundary_encoding.csv"
    sources_path = root / "frontend" / "src" / "lib" / "boundaries" / "sources.ts"
    source_text = sources_path.read_text(encoding="utf-8")
    panchayat_labels = parse_string_record(source_text, "PANCHAYAT_STATE_NAMES")
    ward_labels = parse_string_record(source_text, "WARD_STATE_NAMES")
    panchayat_rows, ward_rows = read_encoding_rows(encoding_path)
    if not panchayat_rows:
        raise ValueError("boundary_encoding.csv has no panchayat receipt rows")
    if not ward_rows:
        raise ValueError("boundary_encoding.csv has no ward receipt rows")
    return render_generated_module(panchayat_rows, ward_rows, panchayat_labels, ward_labels)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repo_root_from_script(), help="repo root")
    parser.add_argument("--check", action="store_true", help="fail if the generated file is stale")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    output_path = root / "frontend" / "src" / "lib" / "boundaries" / "generated-sources.ts"

    try:
        generated = build_generated_text(root)
    except Exception as exc:  # noqa: BLE001 - CLI should print a concise generator failure.
        print(f"generate_frontend_registry.py: {exc}", file=sys.stderr)
        return 1

    if args.check:
        if not output_path.exists():
            print(f"{output_path.relative_to(root).as_posix()} is missing; run generator", file=sys.stderr)
            return 1
        existing = output_path.read_text(encoding="utf-8")
        if existing != generated:
            print(f"{output_path.relative_to(root).as_posix()} is stale; run generator", file=sys.stderr)
            return 1
        print(f"{output_path.relative_to(root).as_posix()} is fresh")
        return 0

    output_path.write_text(generated, encoding="utf-8", newline="\n")
    print(f"wrote {output_path.relative_to(root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())