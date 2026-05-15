"""Per-indicator documentation page generator (CLAUDE.md Holy Law #4).

Phase 1 of ``TODO/PER-INDICATOR-DOCS-PLAN.md``. Walks every artifact under
``datasets/indicators/in/**/*.json`` and emits one Markdown page per
indicator at ``docs/reference/indicators/<topic>/<basename>.md``, derived
~95% from the artifact itself. Optional sections (``methodology_vintage``,
``series_breaks``, etc.) are omitted when their data is missing rather
than rendered as empty headings.

Wiring: ``python -m yen_gov indicator-pages`` regenerates the tree;
``python -m yen_gov coverage`` invokes it after rendering the inventory.

Schema-1.5-only fields (revision_tier_by_period, denominator, excludes,
policy_context, related) are NOT rendered yet — they land in Phase 3 once
the schema bumps and the sidecar arrives. This generator targets the
v1.4 surface only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator
from urllib.parse import urlparse

INDICATORS_REL = "datasets/indicators/in"
INDICATOR_DOCS_REL = "docs/reference/indicators"
TOPIC_CATALOGUE_REL = "datasets/reference/in/topic-catalogue.json"
SCHEMA_REL = "datasets/schemas/indicator.schema.json"


@dataclass(frozen=True)
class IndicatorArtifact:
    """A loaded artifact + its on-disk path (relative to repo root, POSIX)."""

    path_rel: str  # POSIX, e.g. "datasets/indicators/in/energy/state_coal_consumption_mt.json"
    topic: str  # first dir under indicators/in (e.g. "energy")
    basename: str  # filename without .json (e.g. "state_coal_consumption_mt")
    doc: dict


def iter_indicator_artifacts(root: Path) -> Iterator[IndicatorArtifact]:
    """Yield every indicator artifact under ``datasets/indicators/in/**``.

    Skips ``*.notes.json`` sidecars (Phase 4 surface) and files that fail
    to parse as JSON (logged silently — the validator catches them).
    """
    base = root / INDICATORS_REL
    if not base.exists():
        return
    for path in sorted(base.rglob("*.json")):
        if path.name.endswith(".notes.json"):
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rel = path.relative_to(base)
        parts = rel.parts
        if len(parts) < 2:
            # Artifacts must live under a topic directory.
            continue
        topic = parts[0]
        basename = path.stem
        path_rel = path.relative_to(root).as_posix()
        yield IndicatorArtifact(
            path_rel=path_rel, topic=topic, basename=basename, doc=doc
        )


def _load_wired_ids(root: Path) -> set[str] | None:
    """Mirror ``coverage._load_wired_indicator_ids`` so the index agrees.

    Returns the set of indicator ids that appear anywhere in
    ``topic-catalogue.json`` (regardless of ``featured``). ``None`` when
    the catalogue file is absent — the index then prints "n.a.".
    """
    p = root / TOPIC_CATALOGUE_REL
    if not p.exists():
        return None
    try:
        cat = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    out: set[str] = set()
    for topic in cat.get("topics", []) or []:
        for art in topic.get("artifacts", []) or []:
            if art.get("kind") == "indicator" and art.get("id"):
                out.add(art["id"])
    return out


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    # Naive first-sentence: split on ". " keeping abbreviations intact enough
    # for citizen-facing prose; the artifact descriptions are well-formed.
    for sep in (". ", ".\n"):
        if sep in text:
            return text.split(sep, 1)[0].rstrip(".") + "."
    return text


def _coverage_lines(doc: dict) -> list[str]:
    """Derive temporal span, period count, entity count from the artifact."""
    cov = doc.get("coverage") or {}
    rows = doc.get("rows") or []
    span = cov.get("temporal") or "-"
    spatial = cov.get("spatial") or "-"
    n_periods = len({str(r.get("time")) for r in rows if r.get("time")})
    n_entities = len({r["entity_id"] for r in rows if "entity_id" in r})
    n_rows = len(rows)
    out = [
        f"- **Temporal**: {span} ({n_periods} period{'s' if n_periods != 1 else ''})",
        f"- **Spatial**: {spatial} ({n_entities} entit{'ies' if n_entities != 1 else 'y'})",
        f"- **Rows on disk**: {n_rows:,}",
    ]
    return out


_SIGNATURE_FIELDS: tuple[tuple[str, str], ...] = (
    ("entity_kind", "Entity kind"),
    ("time_grain", "Time grain"),
    ("value_kind", "Value kind"),
    ("unit", "Unit"),
    ("direction", "Direction"),
    ("comparability", "Comparability"),
    ("attribution_geography", "Attribution geography"),
    ("implementing_authority", "Implementing authority"),
    ("scale_hint", "Scale hint"),
    ("chart_type", "Chart type"),
    ("default_mode", "Default mode"),
)


def _signature_table(ind: dict) -> list[str]:
    rows = [(label, ind[key]) for key, label in _SIGNATURE_FIELDS if ind.get(key)]
    if not rows:
        return []
    out = ["| Field | Value |", "| --- | --- |"]
    for label, val in rows:
        out.append(f"| {label} | `{val}` |")
    return out


def _series_breaks_table(breaks: list[dict]) -> list[str]:
    if not breaks:
        return []
    out = ["| at_time | kind | note |", "| --- | --- | --- |"]
    for b in breaks:
        at = b.get("at_time", "-")
        kind = b.get("kind", "-")
        note = (b.get("note") or "").replace("|", "\\|").replace("\n", " ")
        out.append(f"| `{at}` | `{kind}` | {note} |")
    return out


def _revision_tier_table(tiers: list[dict]) -> list[str]:
    """Schema 1.5: indicator.revision_tier_by_period[]."""
    if not tiers:
        return []
    out = ["| from | tier | note |", "| --- | --- | --- |"]
    for t in tiers:
        frm = t.get("from", "-")
        tier = t.get("tier", "-")
        note = (t.get("note") or "").replace("|", "\\|").replace("\n", " ")
        out.append(f"| `{frm}` | `{tier}` | {note} |")
    return out


def _denominator_block(denom) -> list[str]:
    """Schema 1.5: indicator.denominator may be string | object | null."""
    if not denom:
        return []
    if isinstance(denom, str):
        return [f"Indicator id: `{denom}`."]
    if isinstance(denom, dict):
        rows = ["| field | value |", "| --- | --- |"]
        for k in ("what", "price_basis", "base_year", "source_artifact", "note"):
            v = denom.get(k)
            if v:
                rows.append(f"| {k} | `{v}` |")
        return rows if len(rows) > 2 else []
    return []


def _excludes_bullets(excludes: list[str]) -> list[str]:
    """Schema 1.5: indicator.excludes[] (citizen-facing what's-NOT-counted)."""
    return [f"- {e}" for e in (excludes or []) if e]


def _renderer_rules_block(rules: list[str]) -> list[str]:
    """Schema 1.5: indicator.renderer_rules[] (controlled-vocab slugs)."""
    return [f"- `{r}`" for r in (rules or []) if r]


def _sources_bullets(sources: list[dict]) -> list[str]:
    out: list[str] = []
    for s in sources or []:
        url = s.get("url", "-")
        fetched = s.get("fetched_at", "-")
        host = ""
        try:
            host = urlparse(url).netloc
        except ValueError:
            pass
        host_tag = f" — {host}" if host else ""
        out.append(f"- <{url}>{host_tag} (fetched {fetched})")
    return out


def _license_block(lic: dict | str | None) -> list[str]:
    if not lic:
        return []
    if isinstance(lic, str):
        return [lic]
    name = lic.get("name") or lic.get("id") or "-"
    url = lic.get("url")
    redist = lic.get("redistributable")
    parts = [f"**{name}**"]
    if url:
        parts.append(f"([link]({url}))")
    if redist is True:
        parts.append("· redistributable")
    elif redist is False:
        parts.append("· **not** redistributable")
    return [" ".join(parts)]


def _citation(doc: dict, schema_version: str) -> str:
    ind = doc.get("indicator") or {}
    sources = doc.get("sources") or []
    producer = ""
    if sources:
        try:
            producer = urlparse(sources[0].get("url", "")).netloc
        except ValueError:
            producer = ""
    fetched = sources[0].get("fetched_at", "")[:10] if sources else ""
    title = ind.get("title") or ind.get("id") or "-"
    return (
        f"> {producer or 'Upstream'}, *{title}*. Re-published by yen-gov as "
        f"`{ind.get('id', '-')}`, schema v{schema_version}. Retrieved "
        f"{fetched or 'unknown date'}."
    )


def render_page(artifact: IndicatorArtifact) -> str:
    """Render the Markdown body for one indicator. Pure function."""
    doc = artifact.doc
    ind = doc.get("indicator") or {}
    ind_id = ind.get("id") or f"{artifact.topic}/{artifact.basename}"
    schema_version = doc.get("$schema_version", "1.5")

    lines: list[str] = []
    lines.append(f"# `{ind_id}`")
    lines.append("")
    lines.append(f"<!-- AUTO-GENERATED by `python -m yen_gov indicator-pages`. Do not hand-edit. -->")
    lines.append("")
    lines.append(f"**Title**: {ind.get('title', '-')}  ")
    one_line = _first_sentence(ind.get("description", ""))
    if one_line:
        lines.append(f"**One-line**: {one_line}  ")
    lines.append(f"**Last Updated**: {_utc_now()} (auto-generated)  ")
    lines.append(f"**Source artifact**: [`{artifact.path_rel}`](../../../../{artifact.path_rel})")
    lines.append("")

    desc = (ind.get("description") or "").strip()
    if desc:
        lines.append("## Definition")
        lines.append("")
        lines.append(desc)
        lines.append("")

    sig = _signature_table(ind)
    if sig:
        lines.append("## Signature")
        lines.append("")
        lines.extend(sig)
        lines.append("")

    cov_lines = _coverage_lines(doc)
    if cov_lines:
        lines.append("## Coverage")
        lines.append("")
        lines.extend(cov_lines)
        lines.append("")

    vintage = (ind.get("methodology_vintage") or "").strip()
    if vintage:
        lines.append("## Methodology vintage")
        lines.append("")
        lines.append(vintage)
        lines.append("")

    breaks_tbl = _series_breaks_table(doc.get("series_breaks") or [])
    if breaks_tbl:
        lines.append("## Series breaks")
        lines.append("")
        lines.extend(breaks_tbl)
        lines.append("")
        lines.append(
            "> Renderer guard: growth rates spanning a `definition_change` "
            "or `rebase` break MUST NOT be computed without a splice note."
        )
        lines.append("")

    rev_tbl = _revision_tier_table(ind.get("revision_tier_by_period") or [])
    if rev_tbl:
        lines.append("## Revision tier (by period)")
        lines.append("")
        lines.extend(rev_tbl)
        lines.append("")

    denom_block = _denominator_block(ind.get("denominator"))
    if denom_block:
        lines.append("## Denominator")
        lines.append("")
        lines.extend(denom_block)
        lines.append("")

    excl = _excludes_bullets(ind.get("excludes") or [])
    if excl:
        lines.append("## What's NOT counted")
        lines.append("")
        lines.extend(excl)
        lines.append("")

    rrules = _renderer_rules_block(ind.get("renderer_rules") or [])
    if rrules:
        lines.append("## Renderer rules")
        lines.append("")
        lines.extend(rrules)
        lines.append("")

    notes = (ind.get("notes") or "").strip()
    if notes:
        lines.append("## Notes")
        lines.append("")
        lines.append(notes)
        lines.append("")

    src = _sources_bullets(doc.get("sources") or [])
    if src:
        lines.append("## Sources")
        lines.append("")
        lines.extend(src)
        lines.append("")

    lic = _license_block(doc.get("license"))
    if lic:
        lines.append("## License")
        lines.append("")
        lines.extend(lic)
        lines.append("")

    lines.append("## Citation")
    lines.append("")
    lines.append(_citation(doc, schema_version))
    lines.append("")

    lines.append("## Schema")
    lines.append("")
    lines.append(
        f"`indicator.schema.json` v{schema_version} · artifact: "
        f"[`{artifact.path_rel}`](../../../../{artifact.path_rel})"
    )
    lines.append("")
    return "\n".join(lines)


def _index_page(artifacts: list[IndicatorArtifact], wired: set[str] | None) -> str:
    lines: list[str] = []
    lines.append("# Indicator pages")
    lines.append("")
    lines.append(
        "<!-- AUTO-GENERATED by `python -m yen_gov indicator-pages`. Do not hand-edit. -->"
    )
    lines.append("")
    lines.append(f"**Last Updated**: {_utc_now()} (auto-generated)")
    lines.append("")
    lines.append(
        f"{len(artifacts)} indicator artifact(s) under "
        f"[`{INDICATORS_REL}/`](../../../{INDICATORS_REL}/). One page per "
        "artifact, derived ~95% from the artifact itself. Inventory breadth "
        "view: [`docs/reference/data-inventory.md`](../data-inventory.md). "
        "Plan: [`TODO/PER-INDICATOR-DOCS-PLAN.md`](../../../TODO/PER-INDICATOR-DOCS-PLAN.md)."
    )
    lines.append("")
    by_topic: dict[str, list[IndicatorArtifact]] = {}
    for a in artifacts:
        by_topic.setdefault(a.topic, []).append(a)
    for topic in sorted(by_topic):
        lines.append(f"## {topic}")
        lines.append("")
        lines.append("| id | one-line | span | wired? |")
        lines.append("| --- | --- | --- | :---: |")
        for a in sorted(by_topic[topic], key=lambda x: x.basename):
            ind = a.doc.get("indicator") or {}
            ind_id = ind.get("id") or f"{a.topic}/{a.basename}"
            one_line = _first_sentence(ind.get("description", "")) or "-"
            # Truncate one-line for the table to keep rows scannable.
            if len(one_line) > 140:
                one_line = one_line[:137].rstrip() + "…"
            one_line = one_line.replace("|", "\\|").replace("\n", " ")
            span = ((a.doc.get("coverage") or {}).get("temporal")) or "-"
            if wired is None:
                wired_cell = "n.a."
            elif ind_id in wired:
                wired_cell = "●"
            else:
                wired_cell = "○"
            link = f"{topic}/{a.basename}.md"
            lines.append(f"| [`{ind_id}`]({link}) | {one_line} | {span} | {wired_cell} |")
        lines.append("")
    return "\n".join(lines)


def write_pages(root: Path) -> list[Path]:
    """Materialise the per-indicator tree under ``docs/reference/indicators/``.

    Returns the list of files written (pages + index), POSIX-relative paths
    in the returned list — but the actual ``Path`` objects are platform.
    """
    artifacts = list(iter_indicator_artifacts(root))
    wired = _load_wired_ids(root)
    out_root = root / INDICATOR_DOCS_REL
    out_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # Wipe any stale pages whose source artifact no longer exists, but keep
    # the index.md and topic dirs (they get re-emitted below). We only
    # delete .md files we would have generated.
    expected: set[Path] = {out_root / "index.md"}
    for a in artifacts:
        expected.add(out_root / a.topic / f"{a.basename}.md")
    for existing in out_root.rglob("*.md"):
        if existing not in expected:
            try:
                existing.unlink()
            except OSError:
                pass

    for a in artifacts:
        topic_dir = out_root / a.topic
        topic_dir.mkdir(parents=True, exist_ok=True)
        target = topic_dir / f"{a.basename}.md"
        target.write_text(render_page(a), encoding="utf-8")
        written.append(target)

    index_target = out_root / "index.md"
    index_target.write_text(_index_page(artifacts, wired), encoding="utf-8")
    written.append(index_target)
    return written
