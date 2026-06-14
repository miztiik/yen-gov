#!/usr/bin/env python3
"""Mint Bihar 2000 parties (BJC, KSP) per TCPD resolution + update corpus."""

import csv
import hashlib

# User directive decisions: use tcpd and do it
decisions = {
    'BJC': {
        'tcpd_id': 1411,
        'tcpd_name': 'Bharatiya Jan Congress',
        'tcpd_type': 'Local Party',
        'tcpd_years': (1993, 2000),
        'new_party_id': 'parties.IN.BJC',
        'confidence': 'HIGH'
    },
    'KSP': {
        'tcpd_id': 4881,
        'tcpd_name': 'Kosal Party',
        'tcpd_type': 'Local Party',
        'tcpd_years': (1995, 2004),
        'new_party_id': 'parties.IN.KSP',
        'confidence': 'MEDIUM'
    }
}

# Step 1: Check existing parties and mint new ones
existing_parties = set()
with open('datasets/data/entities/parties.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        existing_parties.add(row['party_id'])

new_rows = []
for label, info in decisions.items():
    if info['new_party_id'] not in existing_parties:
        new_rows.append({
            'party_id': info['new_party_id'],
            'short': label,
            'full': info['tcpd_name'],
            'eci_codes': '',
            'brand_colour': '',
            'symbol_asset': '',
            'wikipedia': '',
            'aliases': label,
            'recognition_scope': 'state',
            'home_state_codes': 'IN-BR',
            'founded_year': info['tcpd_years'][0],
            'dissolved_year': info['tcpd_years'][1],
            'predecessor_party_ids': '',
            'successor_party_ids': '',
            'name_history': '',
            'claims_to_parent_name': '',
            'name_native_script': '',
            'is_sentinel': 'false'
        })

if new_rows:
    print(f"Minting {len(new_rows)} new Bihar 2000 parties...")
    with open('datasets/data/entities/parties.csv', 'a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerows(new_rows)
    print(f"  Minted: {[row['party_id'] for row in new_rows]}")

# Step 2: Update Bihar 2000 candidacies to link to new party_ids
label_to_party_id = {label: info['new_party_id'] for label, info in decisions.items()}

candidacies_file = 'datasets/elections/assembly/state=bihar/election=2000/candidacies.csv'
updated_count = 0

rows = []
with open(candidacies_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('party_id') == 'parties.IN.UNK' and row.get('party_short_raw') in label_to_party_id:
            row['party_id'] = label_to_party_id[row['party_short_raw']]
            updated_count += 1
        rows.append(row)

if updated_count > 0:
    with open(candidacies_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Updated {updated_count} candidacy rows in Bihar 2000 assembly")

# Step 3: Update summary.csv if present
summary_file = 'datasets/elections/assembly/state=bihar/election=2000/summary.csv'
try:
    updated_summary = 0
    rows = []
    with open(summary_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Check winner_party_id and runnerup_party_id
            if row.get('winner_party_id') == 'parties.IN.UNK' and row.get('winner_party_short_raw') in label_to_party_id:
                row['winner_party_id'] = label_to_party_id[row['winner_party_short_raw']]
                updated_summary += 1
            if row.get('runnerup_party_id') == 'parties.IN.UNK' and row.get('runnerup_party_short_raw') in label_to_party_id:
                row['runnerup_party_id'] = label_to_party_id[row['runnerup_party_short_raw']]
                updated_summary += 1
            rows.append(row)
    
    if updated_summary > 0:
        with open(summary_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Updated {updated_summary} summary rows in Bihar 2000 assembly")
except FileNotFoundError:
    print("Summary file not found (expected for assembly elections)")

print("\nBihar 2000 finalization complete (post-2000 UNK resolution via TCPD)")
print(f"Decisions documented in TODO/20260614-post2000-unk-finalization-decisions.md")
