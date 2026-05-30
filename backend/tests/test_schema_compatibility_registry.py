import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from yen_gov.validate import load_schemas, tier_a, tier_b

REPO = Path(__file__).resolve().parents[2]
REGISTRY_REL = Path("datasets/schema-compatibility.json")
SCHEMA_REL = Path("datasets/schemas/schema-compatibility.schema.json")
VERSION_RE = re.compile(r"^\d+\.\d+$")


def _load_json(rel: Path) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _schema_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted((REPO / "datasets/schemas").glob("*.schema.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        out[path.name] = doc["x-version"]
    return out


def _version_tuple(version: str) -> tuple[int, int]:
    major, minor = version.split(".")
    return int(major), int(minor)


def test_schema_compatibility_registry_validates_against_its_schema():
    schema = _load_json(SCHEMA_REL)
    registry = _load_json(REGISTRY_REL)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(registry), key=lambda err: list(err.absolute_path))

    assert errors == []


def test_schema_compatibility_registry_passes_validator_tier_b_fixture(tmp_path: Path):
    schemas_dir = tmp_path / "datasets/schemas"
    schemas_dir.mkdir(parents=True)
    (schemas_dir / SCHEMA_REL.name).write_text(
        (REPO / SCHEMA_REL).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    registry_path = tmp_path / REGISTRY_REL
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        (REPO / REGISTRY_REL).read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    schemas, parse_fails = load_schemas(schemas_dir)
    assert parse_fails == []
    assert tier_a(schemas) == []
    assert tier_b(schemas, tmp_path) == []


def test_schema_compatibility_overrides_reference_existing_current_schemas():
    registry = _load_json(REGISTRY_REL)
    schema_versions = _schema_versions()

    assert registry["overrides"], "expected at least one explicit compatibility override"
    for override in registry["overrides"]:
        schema_name = override["schema"]
        accepted = override["accepted_versions"]
        current = schema_versions.get(schema_name)

        assert current is not None, f"{schema_name} is not present under datasets/schemas/"
        assert current in accepted, f"{schema_name} current version {current} missing from accepted_versions"
        assert accepted == sorted(accepted, key=_version_tuple), f"{schema_name} versions must be sorted"
        assert all(VERSION_RE.fullmatch(version) for version in accepted)


def test_schema_compatibility_forbids_old_major_overrides_without_retained_schema():
    registry = _load_json(REGISTRY_REL)
    schema_versions = _schema_versions()

    for override in registry["overrides"]:
        schema_name = override["schema"]
        current_major = _version_tuple(schema_versions[schema_name])[0]
        accepted_majors = {_version_tuple(version)[0] for version in override["accepted_versions"]}

        assert accepted_majors == {current_major}, (
            f"{schema_name} accepts old major versions without retained schemas or translators: "
            f"{sorted(override['accepted_versions'], key=_version_tuple)}"
        )
