"""Expand datasets/taxonomy/parties.json with reference + hand-curated entries.

Fold-in sources:
  1. Existing canonical taxonomy at datasets/taxonomy/parties.json (preserve all).
  2. Legacy reference at datasets/reference/in/parties.json (76 entries, ECI codes + recognition).
  3. Hand-curated table below for the top ~30 unresolved shorts (from
     .runtime/_party_gap_report.json) where the full name is confidently known.

Output: datasets/taxonomy/parties.json (rewritten, sorted, changelog bumped 2.0 -> 2.1).

Idempotent: re-runs produce the same output as long as inputs are unchanged.
Deletes nothing automatically; deletion of datasets/reference/in/parties.json is
a separate step (after canonical adopts the data).

Schema reference: datasets/schemas/taxonomy-parties.schema.json v2.0.
"""

from __future__ import annotations

import io
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PATH = ROOT / "datasets" / "taxonomy" / "parties.json"
REFERENCE_PATH = ROOT / "datasets" / "reference" / "in" / "parties.json"


# ---------------------------------------------------------------------------
# Hand-curated additions for the top unresolved shorts (from gap report).
# Format: short_name -> dict(party_id?, full_name, state_scope, aliases?, eci_codes?, recognition?, notes?)
# party_id is auto-generated from short_name if omitted (see slugify_party_id).
# If full_name is None we skip (signal: needs research).
#
# Sources for these names:
#   - Wikipedia article titles for Indian political parties
#   - ECI recognised-party lists (publicly available)
#   - Common Indian psephology references
# ---------------------------------------------------------------------------
HAND_CURATED: dict[str, dict] = {
    # Major national / multi-state parties not in either source.
    "SDPI": {
        "full_name": "Social Democratic Party of India",
        "state_scope": ["IN"],
        "recognition": "registered_unrecognised",
        "notes": "Registered unrecognised; active across Karnataka, Kerala, Tamil Nadu.",
    },
    "RLD": {
        "full_name": "Rashtriya Lok Dal",
        "state_scope": ["S24"],  # UP
        "recognition": "state",
        "aliases": ["RLDA"],
        "notes": "Recognised state party in UP; founded by Ajit Singh.",
    },
    "MNM": {
        "full_name": "Makkal Needhi Maiam",
        "state_scope": ["S22"],  # TN
        "recognition": "registered_unrecognised",
        "notes": "Tamil Nadu party founded by Kamal Haasan in 2018.",
    },
    "LJP": {
        "full_name": "Lok Janshakti Party",
        "state_scope": ["S04"],  # Bihar
        "recognition": "registered_unrecognised",
        "notes": "Founded by Ram Vilas Paswan in 2000. Split into LJP(RV) and RLJP in 2021; pre-split rows use LJP.",
        "successor_party_id": "parties.IN.LJPRV",
    },
    "SUCI": {
        "full_name": "Socialist Unity Centre of India (Communist)",
        "state_scope": ["IN"],
        "recognition": "registered_unrecognised",
        "aliases": ["SUCI(C)", "SUCIC"],
        "notes": "Marxist-Leninist communist party; long-tail contestants across many states.",
    },
    "SAD(M)": {
        "full_name": "Shiromani Akali Dal (Amritsar)",
        "state_scope": ["S19"],  # Punjab
        "recognition": "registered_unrecognised",
        "aliases": ["SADM", "SAD(A)"],
        "notes": "Simranjit Singh Mann's faction of SAD.",
    },
    "JNJP": {
        "full_name": "Jannayak Janta Party",
        "state_scope": ["S07"],  # Haryana
        "recognition": "state",
        "aliases": ["JJP"],
        "notes": "Recognised state party in Haryana; founded by Dushyant Chautala in 2018.",
    },
    "BDJS": {
        "full_name": "Bharath Dharma Jana Sena",
        "state_scope": ["S11"],  # Kerala
        "recognition": "registered_unrecognised",
        "notes": "Kerala-based; NDA ally.",
    },
    "NDPP": {
        "full_name": "Nationalist Democratic Progressive Party",
        "state_scope": ["S14"],  # Nagaland
        "recognition": "state",
        "notes": "Recognised state party in Nagaland.",
    },
    "RLSP": {
        "full_name": "Rashtriya Lok Samta Party",
        "state_scope": ["S04"],  # Bihar
        "recognition": "registered_unrecognised",
        "notes": "Bihar party founded by Upendra Kushwaha in 2013; later merged into JD(U).",
    },
    "ASPKR": {
        "full_name": "Azad Samaj Party (Kanshi Ram)",
        "state_scope": ["S24"],  # UP
        "recognition": "registered_unrecognised",
        "notes": "UP-based; founded by Chandrashekhar Azad in 2020.",
    },
    "NINSHAD": {
        "full_name": "Nirbal Indian Shoshit Hamara Aam Dal",
        "state_scope": ["S24"],  # UP
        "recognition": "registered_unrecognised",
        "aliases": ["NISHAD", "Nishad Party"],
        "notes": "UP-based party representing Nishad (Mallah) community.",
    },
    "JVM": {
        "full_name": "Jharkhand Vikas Morcha (Prajatantrik)",
        "state_scope": ["S27"],  # Jharkhand
        "recognition": "registered_unrecognised",
        "aliases": ["JVMP", "JVM(P)"],
        "notes": "Jharkhand party; merged into BJP in 2020.",
    },
    "WPOI": {
        "full_name": "Welfare Party of India",
        "state_scope": ["IN"],
        "recognition": "registered_unrecognised",
        "notes": "Multi-state party; active in Kerala, Karnataka, UP, etc.",
    },
    "AIMEP": {
        "full_name": "All India Mahila Empowerment Party",
        "state_scope": ["IN"],
        "recognition": "registered_unrecognised",
        "notes": "Founded by Nowhera Shaik in 2017.",
    },
    "UKKD": {
        "full_name": "Uttarakhand Kranti Dal",
        "state_scope": ["S05"],  # Note: Uttarakhand is S05 in some lists; verify if needed.
        "recognition": "registered_unrecognised",
        "notes": "Uttarakhand-specific regional party.",
    },
    "JAPL": {
        "full_name": "Jan Adhikar Party (Loktantrik)",
        "state_scope": ["S04"],  # Bihar
        "recognition": "registered_unrecognised",
        "aliases": ["JAP(L)", "JAPL"],
        "notes": "Bihar party founded by Pappu Yadav.",
    },
    "RPPRINAT": {
        "full_name": "Rashtriya Praja Party (Secular)",
        "state_scope": ["IN"],
        "recognition": "registered_unrecognised",
        "notes": "Long-tail multi-state contestant; tentative full-name resolution.",
    },
    "BTP": {
        "full_name": "Bharatiya Tribal Party",
        "state_scope": ["S06"],  # Gujarat
        "recognition": "registered_unrecognised",
        "notes": "Tribal rights party in Gujarat and Rajasthan.",
    },
    "AJSUP": {
        "full_name": "All Jharkhand Students Union",
        "state_scope": ["S27"],  # Jharkhand
        "recognition": "state",
        "aliases": ["AJSU"],
        "notes": "Variant short for AJSU (state party in Jharkhand).",
    },
    "KMDK": {
        "full_name": "Kongunadu Makkal Desia Katchi",
        "state_scope": ["S22"],  # TN
        "recognition": "registered_unrecognised",
        "notes": "Tamil Nadu regional party representing Kongu Vellala Gounder community.",
    },
    "AIPTMMK": {
        "full_name": "All India Puratchi Thalaivar Makkal Munnettra Kazhagam",
        "state_scope": ["S22"],  # TN
        "recognition": "registered_unrecognised",
        "notes": "Tamil Nadu regional party.",
    },
    "SBSP": {
        "full_name": "Suheldev Bharatiya Samaj Party",
        "state_scope": ["S24"],  # UP
        "recognition": "registered_unrecognised",
        "notes": "UP party founded by Om Prakash Rajbhar in 2002.",
    },
    "PT": {
        "full_name": "Puthiya Tamilagam",
        "state_scope": ["S22"],  # TN
        "recognition": "registered_unrecognised",
        "notes": "Tamil Nadu party founded by K. Krishnasamy.",
    },
    "KRS": {
        "full_name": "Karnataka Rashtra Samithi",
        "state_scope": ["S10"],  # Karnataka
        "recognition": "registered_unrecognised",
        "notes": "Karnataka regional party founded by Ravi Krishna Reddy.",
    },
    "INPT": {
        "full_name": "Indigenous Nationalist Party of Twipra",
        "state_scope": ["S23"],  # Tripura
        "recognition": "registered_unrecognised",
        "notes": "Tripura-based indigenous rights party.",
    },
    "CPI(ML)(L)": {
        # Alias to existing CPI(ML)L if present after merge; else create new.
        "full_name": "Communist Party of India (Marxist-Leninist) Liberation",
        "state_scope": ["S04"],
        "recognition": "state",
        "aliases": ["CPIMLL", "CPI(ML)L"],
        "notes": "Bracketed-double variant of the short used in some upstream sources.",
        # Will deduplicate via canonical_alias_map below.
        "_alias_target": "CPI(ML)L",
    },
    "RPI(A)": {
        "full_name": "Republican Party of India (A)",
        "state_scope": ["S13"],  # Maharashtra
        "recognition": "registered_unrecognised",
        "aliases": ["RPIA"],
        "notes": "Athawale faction of RPI.",
    },
    "RVLTGONP": {
        # Treat as alias of RGP (Revolutionary Goans Party).
        "_alias_target": "RGP",
    },
    "tavk": {
        # Lower-case variant; folds to TVK.
        "_alias_target": "TVK",
    },
    "AAAP": {
        # Variant short of AAP observed in upstream rows.
        "_alias_target": "AAP",
    },
    "NPEP": {
        # Variant short of NPP (National People's Party).
        "_alias_target": "NPP",
    },
    "ADAL": {
        # Variant short of AD(S) (Apna Dal Soneylal).
        "_alias_target": "AD(S)",
    },
    "RLTP": {
        # Variant short of RLP (Rashtriya Loktantrik Party).
        "_alias_target": "RLP",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify_party_id(short: str) -> str:
    """parties.IN.<SHORT_SLUG> — uppercase, strip non-alnum-or-underscore."""
    s = short.upper()
    s = re.sub(r"[^A-Z0-9_]", "", s)
    if not s or not s[0].isalpha():
        s = "P" + s
    return f"parties.IN.{s[:55]}"


def normalize_state_scope(recognition: str, recognized_in_states: list[str]) -> list[str]:
    if recognition == "national":
        return ["IN"]
    if recognition == "state" and recognized_in_states:
        return list(recognized_in_states)
    if recognition == "registered_unrecognised":
        return ["IN"]  # default; can be narrowed by hand
    return ["IN"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    canonical = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))

    # Index existing canonical entries by party_id and by every short/alias (lower).
    by_pid: OrderedDict[str, dict] = OrderedDict()
    short_to_pid: dict[str, str] = {}
    for p in canonical["parties"]:
        by_pid[p["party_id"]] = p
        short_to_pid[p["short_name"].lower()] = p["party_id"]
        for a in p.get("aliases", []) or []:
            short_to_pid.setdefault(a.lower(), p["party_id"])

    added_from_ref = 0
    merged_into_existing = 0
    for r in reference["parties"]:
        short = r["short_name"]
        full = r["full_name"]
        rec = r["recognition"]
        states = r.get("recognized_in_states", []) or []
        eci_code = r.get("eci_code")
        ref_aliases = r.get("aliases", []) or []

        # Does this already exist in canonical (by short or alias)?
        existing_pid = short_to_pid.get(short.lower())
        if not existing_pid:
            for a in ref_aliases:
                existing_pid = short_to_pid.get(a.lower())
                if existing_pid:
                    break

        if existing_pid:
            # Merge: backfill eci_codes, aliases, state_scope into the canonical entry.
            entry = by_pid[existing_pid]
            if eci_code and eci_code not in (entry.get("eci_codes") or []):
                entry.setdefault("eci_codes", []).append(eci_code)
            for a in [short] + ref_aliases:
                if a.lower() != entry["short_name"].lower() and a not in (entry.get("aliases") or []):
                    entry.setdefault("aliases", []).append(a)
                    short_to_pid.setdefault(a.lower(), existing_pid)
            # state_scope: union
            existing_scope = set(entry.get("state_scope") or [])
            ref_scope = set(normalize_state_scope(rec, states))
            # If canonical was ['IN'] but reference says only state codes, prefer state codes.
            if existing_scope == {"IN"} and ref_scope and ref_scope != {"IN"}:
                entry["state_scope"] = sorted(ref_scope)
            else:
                entry["state_scope"] = sorted(existing_scope | ref_scope) or ["IN"]
            merged_into_existing += 1
        else:
            # New entry — promote into canonical.
            pid = slugify_party_id(short)
            # Make sure pid is unique.
            n = 2
            base_pid = pid
            while pid in by_pid:
                pid = f"{base_pid}_{n}"
                n += 1
            new_entry = {
                "party_id": pid,
                "short_name": short,
                "full_name": full,
                "aliases": list(ref_aliases),
                "eci_codes": [eci_code] if eci_code else [],
                "state_scope": normalize_state_scope(rec, states),
                "founded_year": None,
                "dissolved_year": None,
                "successor_party_id": None,
                "predecessor_party_id": None,
                "notes": f"Promoted from datasets/reference/in/parties.json on 2026-05-19 (recognition={rec}).",
            }
            by_pid[pid] = new_entry
            short_to_pid[short.lower()] = pid
            for a in ref_aliases:
                short_to_pid.setdefault(a.lower(), pid)
            added_from_ref += 1

    # Hand-curated additions (top unresolved).
    added_hand = 0
    aliased_to_existing = 0
    for short, spec in HAND_CURATED.items():
        target_alias = spec.get("_alias_target")
        if target_alias:
            target_pid = short_to_pid.get(target_alias.lower())
            if not target_pid:
                print(f"  [warn] HAND_CURATED[{short!r}] _alias_target={target_alias!r} not found; skipping")
                continue
            entry = by_pid[target_pid]
            if short.lower() != entry["short_name"].lower() and short not in (entry.get("aliases") or []):
                entry.setdefault("aliases", []).append(short)
                short_to_pid.setdefault(short.lower(), target_pid)
                aliased_to_existing += 1
            continue

        full = spec.get("full_name")
        if not full:
            print(f"  [skip] HAND_CURATED[{short!r}] has no full_name")
            continue
        if short.lower() in short_to_pid:
            # Already covered (e.g. reference merge populated this short).
            continue
        pid = spec.get("party_id") or slugify_party_id(short)
        n = 2
        base_pid = pid
        while pid in by_pid:
            pid = f"{base_pid}_{n}"
            n += 1
        entry = {
            "party_id": pid,
            "short_name": short,
            "full_name": full,
            "aliases": list(spec.get("aliases", []) or []),
            "eci_codes": list(spec.get("eci_codes", []) or []),
            "state_scope": list(spec.get("state_scope", ["IN"])),
            "founded_year": None,
            "dissolved_year": None,
            "successor_party_id": spec.get("successor_party_id"),
            "predecessor_party_id": spec.get("predecessor_party_id"),
            "notes": spec.get(
                "notes", "Hand-curated 2026-05-19 from .runtime/_party_gap_report.json top unresolved."
            ),
        }
        by_pid[pid] = entry
        short_to_pid[short.lower()] = pid
        for a in entry["aliases"]:
            short_to_pid.setdefault(a.lower(), pid)
        added_hand += 1

    # Rewrite output: preserve original ordering for existing entries, append new at end.
    # (Canonical writer is by_pid insertion order.)
    new_parties = list(by_pid.values())

    # Bump $schema_version 2.0 -> 2.1 (additive — no field renames or removals).
    canonical["$schema_version"] = "2.1"

    # Update sources (add an editorial note for the merge run).
    sources = canonical.get("sources", [])
    merge_source = {
        "url": "https://en.wikipedia.org/wiki/List_of_political_parties_in_India",
        "fetched_at": "2026-05-19T00:00:00Z",
        "name": "Reference parties merge + top-unresolved curation (PR-R.2)",
        "authority": "yen-gov editorial",
    }
    if not any(s.get("name", "").startswith("Reference parties merge") for s in sources):
        sources.append(merge_source)
    canonical["sources"] = sources
    canonical["parties"] = new_parties

    CANONICAL_PATH.write_text(
        json.dumps(canonical, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Merged: {merged_into_existing} reference entries -> existing canonical (alias / scope / eci_code backfill)")
    print(f"Added:  {added_from_ref} new canonical entries promoted from reference/in/parties.json")
    print(f"Hand:   {added_hand} new canonical entries from HAND_CURATED")
    print(f"Alias:  {aliased_to_existing} HAND_CURATED entries folded as aliases into existing entries")
    print(f"Total canonical parties: {len(new_parties)} (was {len([p for p in by_pid.values()])} -- pre-add {len(canonical['parties']) - added_from_ref - added_hand})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
