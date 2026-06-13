#!/usr/bin/env python3
"""
Compute vote-share threshold buckets for UNK party resolution.

Usage:
  python -m tools.compute_vote_share_buckets [--threshold 90|95] [--write-ledger]

Outputs:
  - datasets/_ops/vote-share-threshold-{threshold}-{date}.csv
    (per-event report: event, n_parties_inside_threshold, cumsum%, UNK_label_count_inside, outside)
  - datasets/_ops/post2000-critical-events-{date}.csv
    (7 post-2000 events with UNK winners, ranked by resolution urgency)
"""

import csv
import glob
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

def discover_candidate_files():
    """Find all candidacies.csv files."""
    paths = glob.glob('datasets/elections/assembly/**/candidacies.csv', recursive=True)
    paths += glob.glob('datasets/elections/parliament/**/candidacies.csv', recursive=True)
    return sorted(paths)

def load_events(era_max_year=None):
    """Load all events, optionally filtered by year."""
    # event -> {party_short_raw: total_votes}
    event_votes = defaultdict(lambda: defaultdict(int))
    # event -> {party_short_raw: [is_winner, winner_votes]}
    event_winners = defaultdict(lambda: defaultdict(list))
    
    for fpath in discover_candidate_files():
        with open(fpath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                year = int(row['election_year'])
                if era_max_year is not None and year > era_max_year:
                    continue
                
                state = row['state']
                party_label = (row.get('party_short_raw') or '').strip() or 'UNK'
                votes = int(row.get('votes') or 0)
                is_winner = row.get('result', '').lower() == 'won'
                
                key = (state, year)
                event_votes[key][party_label] += votes
                event_winners[key][party_label].append(is_winner)
    
    return dict(event_votes), dict(event_winners)

def compute_threshold_per_event(event_votes, threshold_pct=95):
    """For each event, compute which parties are in top-N (cumsum >= threshold%)."""
    result = {}
    
    for (state, year), votes_by_party in event_votes.items():
        total_votes = sum(votes_by_party.values())
        if total_votes == 0:
            continue
        
        # Rank by votes descending
        ranked = sorted(votes_by_party.items(), key=lambda kv: -kv[1])
        
        # Find N where cumsum >= threshold%
        cumsum = 0
        n = 0
        threshold_reached = False
        for i, (party, votes) in enumerate(ranked):
            cumsum += votes
            pct = 100 * cumsum / total_votes
            if pct >= threshold_pct:
                n = i + 1
                threshold_reached = True
                break
        
        if not threshold_reached:
            n = len(ranked)  # All parties
        
        # Identify which parties are inside vs outside
        inside_parties = {p for p, v in ranked[:n]}
        outside_parties = {p for p, v in ranked[n:]}
        
        result[(state, year)] = {
            'total_votes': total_votes,
            'n_parties_inside': n,
            'cumsum_pct': 100 * sum(v for p, v in ranked[:n]) / total_votes,
            'inside_parties': inside_parties,
            'outside_parties': outside_parties,
            'outside_votes': sum(v for p, v in ranked[n:]),
            'ranked': ranked,
        }
    
    return result

def emit_threshold_report(event_votes, threshold_pct=95, era_max_year=None):
    """Emit per-event threshold report."""
    thresholds = compute_threshold_per_event(event_votes, threshold_pct)
    
    fname_suffix = f"{threshold_pct}-{datetime.now().strftime('%Y-%m-%d')}.csv"
    fpath = Path('datasets/_ops') / f"vote-share-threshold-{fname_suffix}"
    
    rows = []
    outside_unk_labels = set()
    outside_unk_rows_count = 0
    
    for (state, year), thresh_info in sorted(thresholds.items()):
        if era_max_year is not None and year > era_max_year:
            continue
        
        outside = thresh_info['outside_parties']
        unk_outside = 1 if 'UNK' in outside else 0
        
        rows.append({
            'state': state,
            'year': year,
            'total_votes': thresh_info['total_votes'],
            'n_parties_inside_threshold': thresh_info['n_parties_inside'],
            'cumsum_pct': f"{thresh_info['cumsum_pct']:.1f}",
            'n_outside_threshold': len(outside),
            'outside_vote_pct': f"{100 * thresh_info['outside_votes'] / thresh_info['total_votes']:.1f}",
            'unk_outside_threshold': unk_outside,
            'outside_labels': ' | '.join(sorted(outside)),
        })
        
        if unk_outside:
            outside_unk_labels.update(l for l in outside if l == 'UNK' or l != 'UNK')
            # Count rows
            for fpath in discover_candidate_files():
                with open(fpath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if int(row['election_year']) == year and row['state'] == state:
                            if row.get('party_id') == 'parties.IN.UNK':
                                outside_unk_rows_count += 1
    
    # Write
    fpath.parent.mkdir(parents=True, exist_ok=True)
    with open(fpath, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Wrote {len(rows)} events to {fpath}")
    return fpath

def find_post2000_critical_events():
    """Identify post-2000 events with UNK winners (resolution mandatory)."""
    event_votes, event_winners = load_events(era_max_year=2026)
    
    critical = []
    
    for (state, year), votes_by_party in event_votes.items():
        if year < 2000:
            continue
        
        # Check if UNK has a winner
        if 'UNK' in event_winners[(state, year)]:
            has_winner = any(event_winners[(state, year)]['UNK'])
            if has_winner:
                total_votes = sum(votes_by_party.values())
                unk_votes = votes_by_party.get('UNK', 0)
                unk_pct = 100 * unk_votes / total_votes if total_votes > 0 else 0
                
                critical.append({
                    'state': state,
                    'year': year,
                    'unk_votes': unk_votes,
                    'unk_vote_pct': unk_pct,
                    'total_votes': total_votes,
                    'urgency': 'HIGH' if unk_pct > 1 else 'MEDIUM',
                })
    
    # Sort by urgency + vote count
    critical.sort(key=lambda r: (-r['urgency'] == 'HIGH', -r['unk_votes']))
    
    fpath = Path('datasets/_ops') / f"post2000-critical-events-{datetime.now().strftime('%Y-%m-%d')}.csv"
    fpath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(fpath, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['state', 'year', 'unk_votes', 'unk_vote_pct', 'total_votes', 'urgency'])
        writer.writeheader()
        for row in critical:
            f.write(f"{row['state']},{row['year']},{row['unk_votes']},{row['unk_vote_pct']:.1f},{row['total_votes']},{row['urgency']}\n")
    
    print(f"Wrote {len(critical)} critical events to {fpath}")
    print(f"Critical post-2000 events: {critical}")
    return critical, fpath

if __name__ == '__main__':
    import sys
    
    threshold = 95
    if '--threshold' in sys.argv:
        idx = sys.argv.index('--threshold')
        threshold = int(sys.argv[idx + 1])
    
    # Old data (threshold rule applies)
    old_votes, _ = load_events(era_max_year=1999)
    emit_threshold_report(old_votes, threshold_pct=threshold, era_max_year=1999)
    
    # Post-2000 critical events
    critical, crit_path = find_post2000_critical_events()
    
    print(f"\nSummary:")
    print(f"  Old events analyzed: {len(old_votes)}")
    print(f"  Post-2000 critical events (UNK winner): {len(critical)}")
