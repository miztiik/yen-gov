"""Hand-author Q7 split mints + 6 known 2024 recognition flips on parties.csv (PR-W-2).

Idempotent one-shot script for the 2 mints + 1 enrich-already-present
edit (NCP_SP) + 6 known 2024 recognition_scope / claims_to_parent_name
flips that ECI's Apr 2024 publication ratified and that the
mechanical adapter cannot apply (its enrich leg is fill-empty-only,
per CLAUDE.md section 10 "auto-correct BANNED on publisher disagreement").

These edits implement plan section 3 (PR-W-2 brief) steps 5 + 6, with
each edit citing the relevant ECI order + Hans section 9 + Q7
option-c verdict (signed off 2026-06-10).

Q7 split mints (option c hybrid; ECI-favoured side keeps the parent id):

  - **parties.IN.AIADMK** keeps id; ``claims_to_parent_name=true`` set.
    EPS-led faction per ECI 1 Apr 2022 ruling.
  - **parties.IN.AIADMK_OPS** MINTED — OPS-led faction
    (post-2022, unrecognised_registered). predecessor_party_ids = AIADMK.
  - **parties.IN.SHS** keeps id; ``claims_to_parent_name=true`` set.
    Shinde-led faction per ECI 17 Feb 2023 ruling.
  - **parties.IN.SHS_UBT** MINTED — Uddhav Thackeray-led faction
    (state-recognised in MH). predecessor_party_ids = SHS.
  - **parties.IN.NCP** keeps id; ``claims_to_parent_name=true`` set.
    Ajit Pawar-led faction per ECI 6 Feb 2024 ruling.
  - **parties.IN.NCP_SP** ALREADY in canonical (pre-existing row with
    full name + brand_colour + symbol_asset + wikipedia URL); ENRICHED
    with predecessor_party_ids + recognition_scope + home_state_codes
    + founded_year.

6 known 2024 recognition flips (per Hans section 9 + ECI Apr 2024
publication):

  1. **AAP → national** (gained 2024). canonical: recognition_scope
     empty → set to national.
  2. **CPI → state** (lost national 2024). canonical: already state per
     PR-W-1 TCPD enrichment; this script confirms + adds home_state_codes
     IN-KL|IN-TN|IN-WB if missing.
  3. **AITC (TMC) → national** (re-gained 2024 after 2023 downgrade).
     canonical: currently state → FLIP to national. Justification per
     Wave 0 / Hans section 9 (TMC re-gained national status in 2024
     ECI review).
  4. **BRS → state + IN-TG** (recognition flicker post Oct-2022 rename
     from TRS; lost national 2023, state-only in Telangana). canonical:
     both recognition_scope + home_state_codes empty → fill.
  5. **NCP / NCP_SP** per Q7 (handled in mints above).
  6. **SHS / SHS_UBT** per Q7 (handled in mints above).

Run from the repo root (dry-run by default; --apply writes):

    python -m tools.recon_curate_eci_registered.hans_mints --apply

Run AFTER ``python -m tools.recon_curate_eci_registered --apply`` so the
ECI source_id citation row is already in source.csv.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PARTIES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: (row.get(k) or "") for k in fieldnames})
    path.write_text(buf.getvalue(), encoding="utf-8")


#: Lineage / flip edits the ECI adapter cannot mechanically apply.
#: Applied overwrite-when-different: these are first-class identity
#: contracts and the Q7 + Hans-section-9 authoritative call overrides
#: any prior cell content (unlike the fill-empty-only enrich leg in
#: the parity curator).
_HANS_EDITS: list[tuple[str, dict[str, str]]] = [
    # ----- Q7 ECI-favoured side: parent keeps id + claims_to_parent_name=true.
    (
        "parties.IN.AIADMK",
        {
            "claims_to_parent_name": "true",
            "home_state_codes": "IN-TN|IN-PY",
        },
    ),
    (
        "parties.IN.SHS",
        {
            "claims_to_parent_name": "true",
            "full": "Shiv Sena",
            "recognition_scope": "state",
            "home_state_codes": "IN-MH",
            "founded_year": "1966",
            "wikipedia": "https://en.wikipedia.org/wiki/Shiv_Sena",
        },
    ),
    (
        "parties.IN.NCP",
        {
            "claims_to_parent_name": "true",
            "home_state_codes": "IN-MH|IN-NL",
            "wikipedia": "https://en.wikipedia.org/wiki/Nationalist_Congress_Party",
        },
    ),
    # ----- Q7 breakaway already in canonical: enrich missing fields.
    (
        "parties.IN.NCP_SP",
        {
            "recognition_scope": "state",
            "home_state_codes": "IN-MH",
            "founded_year": "2024",
            "predecessor_party_ids": "parties.IN.NCP",
        },
    ),
    # ----- Q7 SHS-UBT breakaway: canonical row pre-exists at slug
    # parties.IN.SS_UBT (NOT parties.IN.SHS_UBT). Per the brief's
    # explicit fallback ("if a row exists with the correct identity but
    # missing the Q7 marker, just update it; if absent, mint"), update
    # the existing SS_UBT row with the Q7 lineage. The brief's
    # preferred slug naming (SHS_UBT) is deferred to a future slug-
    # rename PR (out of scope for PR-W-2 because the on-disk
    # candidacies.csv corpus uses SS_UBT as the FK target and
    # auto-correcting that is BANNED per CLAUDE.md section 10).
    # Note: claims_to_parent_name + is_sentinel left empty (CSV-null)
    # per the test_parties_csv_v11 convention that non-sentinel rows
    # leave is_sentinel empty; explicit 'false' is reserved for cases
    # where the empty/false distinction carries semantic weight
    # (currently none for breakaway rows).
    (
        "parties.IN.SS_UBT",
        {
            "recognition_scope": "state",
            "home_state_codes": "IN-MH",
            "founded_year": "2023",
            "predecessor_party_ids": "parties.IN.SHS",
            "aliases": "SHS_UBT|SHS-UBT|SS-UBT|SSUBT|SHIV SENA UBT",
        },
    ),
    # ----- 6 known 2024 recognition flips (per Hans section 9).
    # AAP gained national 2024.
    (
        "parties.IN.AAP",
        {
            "recognition_scope": "national",
            "founded_year": "2012",
        },
    ),
    # CPI lost national 2024 → state in KL+TN+WB. canonical is already
    # state per PR-W-1 TCPD enrich; this confirms + fills home_state_codes.
    (
        "parties.IN.CPI",
        {
            "recognition_scope": "state",
            "home_state_codes": "IN-KL|IN-TN|IN-WB",
        },
    ),
    # AITC re-gained national 2024 (was state since 2023 downgrade).
    (
        "parties.IN.AITC",
        {
            "recognition_scope": "national",
            "home_state_codes": "",  # clear: national has no home_state_codes
        },
    ),
    # BRS: state in Telangana post Oct-2022 rename from TRS + 2023
    # national-downgrade. canonical: both fields empty → fill.
    # Note: BRS is a RENAME of TRS (same entity), not a successor — per
    # Hans rule "rebrandings keep SAME id with a name_history[] blob".
    # parties.IN.TRS does NOT exist in canonical and is NOT minted here;
    # the name_history JSON-blob for the TRS->BRS rebrand is deferred
    # to PR-W-3 (Wikipedia per-party infobox parse). founded_year=2001
    # is TRS's original founding (the same legal entity).
    (
        "parties.IN.BRS",
        {
            "recognition_scope": "state",
            "home_state_codes": "IN-TG",
            "founded_year": "2001",
        },
    ),
    # JSP: ECI publishes "Jana Sena Party" (two words); canonical row
    # at parties.IN.JSP carries full="Janasena Party" (one word). Same
    # entity (Pawan Kalyan's party), differs only in orthography. The
    # parity adapter's shared-significant-words guard flagged this as
    # a conflict (no 4-char content overlap between "JANASENA" and
    # {"JANA","SENA"}) — false conflict. Resolution: add the ECI
    # orthography to aliases so future resolver lookups hit, plus the
    # state+home+founded fields ECI publishes.
    (
        "parties.IN.JSP",
        {
            "aliases": "JANA SENA|JANA SENA PARTY",
            "recognition_scope": "state",
            "home_state_codes": "IN-AP",
            "founded_year": "2014",
        },
    ),
]


#: Q7 mints: NEW rows added to parties.csv. Skipped (idempotent) if
#: party_id already exists. The breakaway-faction row carries
#: predecessor_party_ids pointing at the parent (ECI-favoured side).
#: Full identity metadata for the mint (Q1 fact-class table:
#: full/short/aliases from TCPD; eci_codes/recognition_scope/
#: home_state_codes from ECI; brand_colour/symbol_asset/wikipedia URL
#: from Wikipedia per PR-W-3 lane — those columns left empty here for
#: PR-W-3 to fill).
#:
#: PR-W-2 ships ONE mint: AIADMK_OPS (no pre-existing canonical row
#: covers the OPS faction; AMMK is the 2018 Sasikala wing, ANNA_DRAVIDAR_
#: KAZHAGAM is a separate 2021 Sasikala party, distinct identities).
#: SHS_UBT and NCP_SP already exist in canonical (as SS_UBT + NCP_SP
#: respectively); those Q7 markers are applied via _HANS_EDITS above.
_HANS_MINTS: list[dict[str, str]] = [
    {
        "party_id": "parties.IN.AIADMK_OPS",
        "short": "AIADMK_OPS",
        "full": "All India Anna Dravida Munnetra Kazhagam (OPS)",
        "eci_codes": "",  # ECI did not publish a separate code for OPS faction
        "brand_colour": "",
        "symbol_asset": "",
        "wikipedia": "https://en.wikipedia.org/wiki/All_India_Anna_Dravida_Munnetra_Kazhagam",
        "aliases": "AIADMK(OPS)|AIADMKOPS|AIADMK-OPS",
        "recognition_scope": "unrecognised_registered",
        "home_state_codes": "IN-TN",
        "founded_year": "2022",
        "dissolved_year": "",
        "predecessor_party_ids": "parties.IN.AIADMK",
        "successor_party_ids": "",
        "name_history": "",
        # claims_to_parent_name + is_sentinel left empty (CSV-null) per
        # test_parties_csv_v11 convention: non-sentinel rows MUST leave
        # is_sentinel empty. Boolean columns default to null when the
        # value carries no semantic weight beyond the default (false).
        "claims_to_parent_name": "",
        "name_native_script": "",
        "is_sentinel": "",
    },
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to parties.csv. Default is dry-run.",
    )
    args = ap.parse_args()

    fieldnames, rows = _read_csv(PARTIES_CSV)
    by_pid: dict[str, dict[str, str]] = {
        (r.get("party_id") or "").strip(): r for r in rows if r.get("party_id")
    }

    edits_applied: list[tuple[str, list[str]]] = []
    mints_applied: list[str] = []
    mints_skipped: list[str] = []
    edits_skipped_no_canonical: list[str] = []

    # Apply edits (overwrite-when-different).
    for pid, payload in _HANS_EDITS:
        row = by_pid.get(pid)
        if row is None:
            edits_skipped_no_canonical.append(pid)
            continue
        log: list[str] = []
        for k, v in payload.items():
            current = (row.get(k) or "").strip()
            if current == v:
                continue
            row[k] = v
            log.append(f"{k}={v!r} (was {current!r})")
        if log:
            edits_applied.append((pid, log))

    # Apply mints (idempotent: skip if id already present).
    for mint in _HANS_MINTS:
        pid = mint["party_id"]
        if pid in by_pid:
            mints_skipped.append(pid)
            continue
        rows.append(mint)
        mints_applied.append(pid)

    # Re-sort parties.csv by party_id to keep deterministic order
    # (matches the writer-chain convention).
    if mints_applied:
        rows.sort(key=lambda r: (r.get("party_id") or "").strip())

    if args.apply and (edits_applied or mints_applied):
        _write_csv(PARTIES_CSV, fieldnames, rows)

    print(f"[hans-mints-eci] parties.csv = {PARTIES_CSV.as_posix()}")
    print(f"  apply mode:                {args.apply}")
    print(f"  edits applied:             {len(edits_applied)}")
    for pid, log in edits_applied:
        print(f"    {pid}:")
        for entry in log:
            print(f"      - {entry}")
    if edits_skipped_no_canonical:
        print(f"  edits skipped (no canonical):  {len(edits_skipped_no_canonical)}")
        for pid in edits_skipped_no_canonical:
            print(f"    {pid}")
    print(f"  mints applied:             {len(mints_applied)}")
    for pid in mints_applied:
        print(f"    {pid}")
    if mints_skipped:
        print(f"  mints skipped (already present): {len(mints_skipped)}")
        for pid in mints_skipped:
            print(f"    {pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
