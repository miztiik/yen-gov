"""Pre-flight ingest gate (ADR-0046).

The structural answer to "agents must enforce, not re-discover" — runs the
six mechanical checks that the human reviewer would otherwise have to apply
by hand on every new-source ingest handover-doc. Replaces the bare
``check-overlap`` invocation in the handover-doc template (PR-Z3b #363)
with a single batched gate that emits a typed report agents can cite.

Six checks (see :mod:`yen_gov.preflight.predicates`):

1. ``concept_overlap``       — proposed concept vs ``datasets/taxonomy/concepts.json``
2. ``concept_fk``            — proposal's ``concept_id`` resolves in the registry
3. ``grain_prefix``          — ``proposed_id`` carries no ``state-/district-/national-`` prefix
4. ``update_period_days``    — proposal declares a positive integer cadence
5. ``justification``         — proposal carries a >=20-char justification string
6. ``source_id_derivation``  — proposal's ``source_id`` matches ``derive_source_id`` output

Verdict ladder (exit-code mapping):

* ``mint_new`` / ``upsert`` / ``add_facet`` -> exit 0 (agent can proceed)
* same verdicts + at least one soft warning -> exit 1 (proceed with eyes open)
* ``abort`` -> exit 2 (hard fail; no override flag per CLAUDE.md Holy Law #5)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from yen_gov.canonical.concept_registry import find_overlap
from yen_gov.core.schema_registry import schema_version
from yen_gov.preflight import predicates as P

Verdict = Literal["mint_new", "upsert", "add_facet", "abort"]
CheckStatus = Literal["pass", "warn", "fail"]

_PREFLIGHT_REPORT_SCHEMA_FILE = "preflight-report.schema.json"
PREFLIGHT_REPORT_SCHEMA_VERSION = schema_version(_PREFLIGHT_REPORT_SCHEMA_FILE)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: CheckStatus
    evidence: str
    doc_link: str


@dataclass(frozen=True)
class RecommendedAction:
    kind: Verdict
    target_indicator_id: str | None
    target_parquet_path: str | None
    rationale: str


@dataclass(frozen=True)
class PreflightReport:
    schema_version: str
    verdict: Verdict
    recommended_action: RecommendedAction
    checks: list[CheckResult]
    input_echo: dict[str, Any]
    generated_at: str  # deterministic hash of input_echo, NOT wall-clock

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "verdict": self.verdict,
            "recommended_action": asdict(self.recommended_action),
            "checks": [asdict(c) for c in self.checks],
            "input_echo": self.input_echo,
            "generated_at": self.generated_at,
        }

    @property
    def exit_code(self) -> int:
        if self.verdict == "abort":
            return 2
        if any(c.status == "warn" for c in self.checks):
            return 1
        return 0


REQUIRED_PROPOSAL_FIELDS = (
    "proposed_id",
    "family",
    "concept",
    "unit",
    "normalisation",
    "entity_kind",
    "source_producer",
    "source_title",
    "source_vintage",
    "update_period_days",
    "justification",
)


def load_proposal(
    *,
    proposal_file: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hydrate a proposal dict from file (canonical) or CLI sugar.

    Per the synthesized contract: file always wins when both are
    supplied. CLI overrides are accepted only when no file is given.
    """
    if proposal_file is not None:
        return json.loads(proposal_file.read_text(encoding="utf-8"))
    if cli_overrides is None:
        raise ValueError("either proposal_file or cli_overrides must be provided")
    # Drop None entries so callers can pass partial mappings.
    return {k: v for k, v in cli_overrides.items() if v is not None}


def _deterministic_stamp(input_echo: dict[str, Any]) -> str:
    """Return ``preflight:sha256:<hex16>`` derived from input_echo.

    Replaces wall-clock ``generated_at`` per CLAUDE.md §10 anti-pattern.
    Two runs against the same input produce identical reports — safe to
    cite in handover-docs without re-shipping the file on every PR push.
    """
    canon = json.dumps(input_echo, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(canon.encode("ascii")).hexdigest()[:16]
    return f"preflight:sha256:{digest}"


def _load_concepts(root: Path) -> list[dict]:
    path = root / "datasets" / "taxonomy" / "concepts.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("concepts")
    return list(rows) if isinstance(rows, list) else []


def _missing_required(proposal: dict[str, Any]) -> list[str]:
    return [f for f in REQUIRED_PROPOSAL_FIELDS if f not in proposal or proposal[f] in (None, "")]


def build_report(proposal: dict[str, Any], *, root: Path) -> PreflightReport:
    """Run the six checks and synthesise a :class:`PreflightReport`."""
    checks: list[CheckResult] = []
    verdict: Verdict
    target_indicator_id: str | None = None
    target_parquet_path: str | None = None
    rationale: str

    input_echo = dict(proposal)

    missing = _missing_required(proposal)
    if missing:
        checks.append(
            CheckResult(
                name="input_completeness",
                status="fail",
                evidence=f"proposal missing required fields: {missing!r}",
                doc_link="docs/agents/ingest-checklist.md",
            )
        )
        return PreflightReport(
            schema_version=PREFLIGHT_REPORT_SCHEMA_VERSION,
            verdict="abort",
            recommended_action=RecommendedAction(
                kind="abort",
                target_indicator_id=None,
                target_parquet_path=None,
                rationale=f"proposal incomplete: missing {missing!r}",
            ),
            checks=checks,
            input_echo=input_echo,
            generated_at=_deterministic_stamp(input_echo),
        )

    proposed_id = str(proposal["proposed_id"])
    family = str(proposal["family"])

    # 1. concept_overlap
    concepts = _load_concepts(root)
    matches = find_overlap(
        noun=str(proposal["concept"]),
        unit=str(proposal["unit"]),
        normalisation=str(proposal["normalisation"]),
        entity_kind=str(proposal["entity_kind"]),
        concepts=concepts if concepts else [],
        top_n=5,
    )
    top_match = matches[0] if matches else None
    if top_match is None or top_match.recommended_action == "mint_new":
        checks.append(
            CheckResult(
                name="concept_overlap",
                status="pass",
                evidence="no existing concept scores >= 0.70; mint_new acceptable",
                doc_link="docs/concepts/pre-flight-ingest.md",
            )
        )
        verdict = "mint_new"
        target_parquet_path = f"datasets/{family}/{family}_<role>.parquet"
        rationale = "no concept overlap >= 0.70; proceed with mint_new"
    elif top_match.recommended_action == "upsert":
        checks.append(
            CheckResult(
                name="concept_overlap",
                status="pass",
                evidence=f"upsert into {top_match.concept_id!r} (score={top_match.match_score})",
                doc_link="docs/concepts/pre-flight-ingest.md",
            )
        )
        verdict = "upsert"
        target_indicator_id = top_match.concept_id
        target_parquet_path = f"datasets/{family}/{family}_<role>.parquet"
        rationale = (
            f"concept overlap {top_match.match_score} >= 0.85 with "
            f"{top_match.concept_id!r}; UPSERT (new vintage / publisher of same fact)"
        )
    else:  # add_facet
        checks.append(
            CheckResult(
                name="concept_overlap",
                status="pass",
                evidence=f"add facet on {top_match.concept_id!r} (score={top_match.match_score})",
                doc_link="docs/concepts/pre-flight-ingest.md",
            )
        )
        verdict = "add_facet"
        target_indicator_id = top_match.concept_id
        target_parquet_path = f"datasets/{family}/{family}_<role>.parquet"
        rationale = (
            f"concept overlap {top_match.match_score} >= 0.70 with "
            f"{top_match.concept_id!r}; add a facet axis on the existing indicator"
        )

    # 2. concept_fk -- only enforced when proposal carries an explicit
    # concept_id (registry FK). Soft-warn if proposal omits it AND
    # verdict is mint_new (a new concept row must accompany the PR).
    proposed_concept_id = proposal.get("concept_id")
    if proposed_concept_id is None:
        if verdict == "mint_new":
            checks.append(
                CheckResult(
                    name="concept_fk",
                    status="warn",
                    evidence=(
                        "proposal has no concept_id; mint_new requires a new "
                        "row in datasets/taxonomy/concepts.json in the same PR"
                    ),
                    doc_link="docs/concepts/owid-alignment.md",
                )
            )
        else:
            checks.append(
                CheckResult(
                    name="concept_fk",
                    status="pass",
                    evidence="no concept_id required (action is upsert / add_facet)",
                    doc_link="docs/concepts/owid-alignment.md",
                )
            )
    else:
        if P.concept_id_exists(str(proposed_concept_id), concepts):
            checks.append(
                CheckResult(
                    name="concept_fk",
                    status="pass",
                    evidence=f"concept_id={proposed_concept_id!r} resolves in registry",
                    doc_link="docs/concepts/owid-alignment.md",
                )
            )
        else:
            checks.append(
                CheckResult(
                    name="concept_fk",
                    status="fail",
                    evidence=(
                        f"concept_id={proposed_concept_id!r} not present in "
                        f"datasets/taxonomy/concepts.json"
                    ),
                    doc_link="docs/concepts/owid-alignment.md",
                )
            )

    # 3. grain_prefix
    prefix = P.grain_prefix_violation(proposed_id)
    if prefix is None:
        checks.append(
            CheckResult(
                name="grain_prefix",
                status="pass",
                evidence=f"proposed_id={proposed_id!r} carries no grain prefix",
                doc_link="docs/architecture/decisions/0044-grain-over-entity.md",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="grain_prefix",
                status="fail",
                evidence=(
                    f"proposed_id={proposed_id!r} encodes grain prefix "
                    f"{prefix!r}; per ADR-0044 grain lives on the observation "
                    f"row's entity_kind, not in the indicator_id"
                ),
                doc_link="docs/architecture/decisions/0044-grain-over-entity.md",
            )
        )

    # 4. update_period_days
    cadence_err = P.update_period_days_violation(proposal["update_period_days"])
    if cadence_err is None:
        checks.append(
            CheckResult(
                name="update_period_days",
                status="pass",
                evidence=f"update_period_days={proposal['update_period_days']!r} (positive int)",
                doc_link="docs/concepts/pre-flight-ingest.md",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="update_period_days",
                status="fail",
                evidence=cadence_err,
                doc_link="docs/concepts/pre-flight-ingest.md",
            )
        )

    # 5. justification
    just_err = P.justification_violation(proposal["justification"])
    if just_err is None:
        checks.append(
            CheckResult(
                name="justification",
                status="pass",
                evidence=f"justification length={len(str(proposal['justification']))}",
                doc_link="docs/concepts/pre-flight-ingest.md",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="justification",
                status="fail",
                evidence=just_err,
                doc_link="docs/concepts/pre-flight-ingest.md",
            )
        )

    # 6. source_id_derivation
    sid_err = P.source_id_derivation_violation(
        producer=str(proposal["source_producer"]),
        title=str(proposal["source_title"]),
        vintage=str(proposal["source_vintage"]),
        claimed=proposal.get("source_id"),
    )
    if sid_err is None:
        checks.append(
            CheckResult(
                name="source_id_derivation",
                status="pass",
                evidence="source_id (or absence) matches derive_source_id output",
                doc_link="docs/architecture/decisions/0032-sources-citation-ledger.md",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="source_id_derivation",
                status="fail",
                evidence=sid_err,
                doc_link="docs/architecture/decisions/0032-sources-citation-ledger.md",
            )
        )

    # Roll up to verdict. Any hard fail flips to abort.
    if any(c.status == "fail" for c in checks):
        return PreflightReport(
            schema_version=PREFLIGHT_REPORT_SCHEMA_VERSION,
            verdict="abort",
            recommended_action=RecommendedAction(
                kind="abort",
                target_indicator_id=None,
                target_parquet_path=None,
                rationale="one or more hard-fail checks; correct and re-run",
            ),
            checks=checks,
            input_echo=input_echo,
            generated_at=_deterministic_stamp(input_echo),
        )

    return PreflightReport(
        schema_version=PREFLIGHT_REPORT_SCHEMA_VERSION,
        verdict=verdict,
        recommended_action=RecommendedAction(
            kind=verdict,
            target_indicator_id=target_indicator_id,
            target_parquet_path=target_parquet_path,
            rationale=rationale,
        ),
        checks=checks,
        input_echo=input_echo,
        generated_at=_deterministic_stamp(input_echo),
    )
