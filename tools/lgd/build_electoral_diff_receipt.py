"""B2b.5.0c diff-receipt: evidence the clean-start electoral override.

Compares the freshly-regenerated electoral.csv (from the LGD snapshot, B2b.5.0a)
against the prior taxonomy-derived electoral.csv that this 0c-2 PR replaces, and
writes a receipt under ``datasets/_ops/`` per sub-plan section 0c.3 (the diff
receipt MUST be committed BEFORE 0d-del deletes any old artifact).

The receipt reports, per the section-0c.3 schedule: (1) row counts + delta;
(2) id-scheme overlap by ``(kind, state-slug, lgd_code)``; (3) name-mismatch
buckets; (4) orphans both directions; (5) per-state AC/PC cardinality. The final
verdict line classifies the override (the word "corrupted" may not precede the
evidence).

Run AFTER the new electoral.csv has been emitted; pass the path to the
git-tracked OLD electoral.csv (read from the merge-base) via ``--old``.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _key(r: dict[str, str]) -> tuple[str, str, str]:
    # entity_id IN-AC-2008-<state-slug>-<lgd_code>; the lgd_code is the last dash-seg.
    return (r["entity_kind"], r["state"], r["entity_id"].rsplit("-", 1)[-1])


def build_receipt(old_csv: Path, new_csv: Path) -> dict[str, Any]:
    old = _read(old_csv)
    new = _read(new_csv)
    old_by_key = {_key(r): r for r in old}
    new_by_key = {_key(r): r for r in new}
    old_keys = set(old_by_key)
    new_keys = set(new_by_key)

    common = old_keys & new_keys
    name_mismatch: list[dict[str, str]] = []
    for k in sorted(common):
        on = old_by_key[k]["name"]
        nn = new_by_key[k]["name"]
        if on != nn:
            bucket = "case" if on.lower() == nn.lower() else "divergent"
            name_mismatch.append({"key": "/".join(k), "old": on, "new": nn, "bucket": bucket})

    def _card(rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
        out: dict[str, Counter] = defaultdict(Counter)
        for r in rows:
            out[r["state"]][r["entity_kind"]] += 1
        return {s: dict(c) for s, c in sorted(out.items())}

    overlap_ratio = (len(common) / len(new_keys)) if new_keys else 0.0
    name_buckets = Counter(m["bucket"] for m in name_mismatch)

    if overlap_ratio >= 0.95 and not (new_keys - old_keys) and not (old_keys - new_keys):
        verdict = "stale-names-ids-intact"
    elif overlap_ratio >= 0.90:
        verdict = "name-divergent-only" if name_mismatch else "minor-membership-shift"
    else:
        verdict = "clean-rip-justified"

    return {
        "old_csv": old_csv.as_posix(),
        "new_csv": new_csv.as_posix(),
        "row_counts": {"old": len(old), "new": len(new), "delta": len(new) - len(old)},
        "id_overlap": {
            "common": len(common),
            "old_only": len(old_keys - new_keys),
            "new_only": len(new_keys - old_keys),
            "overlap_ratio_vs_new": round(overlap_ratio, 4),
        },
        "name_mismatch_buckets": dict(name_buckets),
        "name_mismatch_sample": name_mismatch[:25],
        "orphans": {
            "old_only_sample": ["/".join(k) for k in sorted(old_keys - new_keys)[:25]],
            "new_only_sample": ["/".join(k) for k in sorted(new_keys - old_keys)[:25]],
        },
        "cardinality_old": _card(old),
        "cardinality_new": _card(new),
        "verdict": verdict,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--old", type=Path, required=True, help="OLD electoral.csv (pre-0c).")
    p.add_argument("--new", type=Path, required=True, help="NEW electoral.csv (post-0c).")
    p.add_argument("--out", type=Path, required=True, help="Receipt markdown output path.")
    args = p.parse_args(argv)
    receipt = build_receipt(args.old, args.new)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Operational receipts are committed as markdown (NOT schema-governed dataset
    # JSON) so the corpus validator does not demand a $schema. The structured
    # body rides a fenced JSON block.
    body = json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True)
    md = (
        "# Electoral clean-start diff receipt (B2b.5.0c-2)\n\n"
        "Evidence for the LGD-snapshot override of the prior taxonomy-derived\n"
        "`electoral.csv`, committed BEFORE 0d-del deletes any old artifact\n"
        "(sub-plan section 0c.3). The verdict line classifies the override; the\n"
        "word \"corrupted\" is never used without this evidence.\n\n"
        f"- Verdict: **{receipt['verdict']}**\n"
        f"- Row delta: {receipt['row_counts']['delta']} "
        f"(old {receipt['row_counts']['old']} -> new {receipt['row_counts']['new']})\n"
        f"- Id overlap vs new: {receipt['id_overlap']['overlap_ratio_vs_new']} "
        f"(old-only {receipt['id_overlap']['old_only']}, "
        f"new-only {receipt['id_overlap']['new_only']})\n\n"
        "```json\n" + body + "\n```\n"
    )
    args.out.write_text(md, encoding="utf-8", newline="")
    print(f"wrote {args.out} (verdict: {receipt['verdict']}, "
          f"delta {receipt['row_counts']['delta']}, "
          f"overlap {receipt['id_overlap']['overlap_ratio_vs_new']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
