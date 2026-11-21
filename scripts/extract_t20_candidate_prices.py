#!/usr/bin/env python3
"""Stream Betfair Basic LTP rows for conservative Cricsheet-linked T20 market candidates.

Not a verified event identity, ball-aligned quote, or executable market price.
Works with outputs from match_t20_markets.py and filter_betfair_candidates.py.
Standard library only.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ELIGIBLE = 'exact_name_date_candidate'


def parse_timestamp(text):
    try:
        t = datetime.fromisoformat((text or '').replace('Z', '+00:00'))
        if t.tzinfo is None:
            return None
        return t.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def run(identity: Path, prices: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    selected = {}
    identity_counts = Counter()
    with identity.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        required = {'market_id','status','event_name','market_time_utc','cricsheet_file','cricsheet_match_date'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f'Identity CSV missing: {sorted(required-set(reader.fieldnames or []))}')
        for row in reader:
            identity_counts[row['status']] += 1
            if row['status'] != ELIGIBLE:
                continue
            mid = row['market_id'].strip()
            if not mid or not row['cricsheet_file']:
                raise ValueError(f'Invalid accepted identity for market {mid}')
            if mid in selected:
                raise ValueError(f'Duplicate accepted market_id: {mid}')
            selected[mid] = row
    if not selected:
        raise ValueError('No exact_name_date_candidate market IDs found')

    price_fields = None
    counts = Counter()
    per_year = defaultdict(Counter)
    per_market = Counter()
    market_runner_ids = defaultdict(set)
    seen_price_keys = set()  # For ~1,449 selected markets; could be large on dense datasets.

    out_prices = out/'t20_candidate_ltp.csv'
    with prices.open(newline='', encoding='utf-8-sig') as inp, out_prices.open('w', newline='', encoding='utf-8') as outf:
        reader = csv.DictReader(inp)
        price_fields = list(reader.fieldnames or [])
        needed = {'market_id','runner_id','publish_time_utc','in_play','market_status','runner_status','last_traded_price'}
        if not needed.issubset(price_fields):
            raise ValueError(f'Price CSV missing: {sorted(needed-set(price_fields))}')
        extras = ['cricsheet_file','cricsheet_match_date','identity_status','identity_market_time_utc','identity_event_name']
        writer = csv.DictWriter(outf, fieldnames=extras+price_fields, extrasaction='ignore')
        writer.writeheader()
        for row in reader:
            counts['input_rows'] += 1
            mid = row.get('market_id','')
            record = selected.get(mid)
            if record is None:
                continue
            year = record['market_time_utc'][:4]
            counts['selected_rows'] += 1
            per_year[year]['price_rows'] += 1
            per_market[mid] += 1
            market_runner_ids[mid].add(row['runner_id'])
            inplay = row.get('in_play','').strip().lower() == 'true'
            if inplay:
                counts['in_play_rows'] += 1
                per_year[year]['in_play_rows'] += 1
            if row.get('market_status','').strip().upper() == 'OPEN':
                counts['open_status_rows'] += 1
            publish = parse_timestamp(row.get('publish_time_utc'))
            if publish is None:
                counts['bad_publish_timestamp'] += 1
            odds = row.get('last_traded_price','')
            try:
                if not 1 < float(odds) < float('inf'):
                    counts['invalid_ltp'] += 1
            except (TypeError, ValueError):
                counts['invalid_ltp'] += 1
            key = (mid, row['runner_id'], row['publish_time_utc'], row.get('last_traded_price',''))
            if key in seen_price_keys:
                counts['duplicate_market_runner_time_price_rows'] += 1
            else:
                seen_price_keys.add(key)
            writer.writerow({'cricsheet_file':record['cricsheet_file'],
                             'cricsheet_match_date':record['cricsheet_match_date'],
                             'identity_status':record['status'],
                             'identity_market_time_utc':record['market_time_utc'],
                             'identity_event_name':record['event_name'], **row})

    with (out/'t20_candidate_markets.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f,fieldnames=['market_id','event_name','market_time_utc','cricsheet_file','cricsheet_teams','cricsheet_match_date','date_shift_days','num_potential_matches','price_rows','observed_distinct_runner_ids'])
        writer.writeheader()
        for mid,rec in sorted(selected.items()):
            writer.writerow({**{k:rec.get(k,'') for k in writer.fieldnames},'price_rows':per_market[mid],'observed_distinct_runner_ids':len(market_runner_ids[mid])})

    summary = {'description':'Conservative candidate identity links; NOT independently verified T20 links or executable odds',
               'identity_status_counts': dict(identity_counts),
               'candidate_market_ids':len(selected),
               'candidate_markets_with_price_rows':len(per_market),
               'candidate_markets_without_price_rows':len(selected)-len(per_market),
               'input_price_rows_checked':counts['input_rows'],
               'extracted_price_rows':counts['selected_rows'],
               'in_play_price_rows':counts['in_play_rows'],
               'open_status_rows':counts['open_status_rows'],
               'bad_publish_timestamps':counts['bad_publish_timestamp'],
               'invalid_last_traded_prices':counts['invalid_ltp'],
               'duplicate_market_runner_time_price_rows':counts['duplicate_market_runner_time_price_rows'],
               'yearly_counts':{y:dict(c) for y,c in sorted(per_year.items())},
               'notes':['No historical betting ROI is calculated.',
                        'LTP is not an executable back quote.',
                        'Match identity is based on exact names and dates and needs review.',
                        'There is no ball-to-quote time alignment.',
                        'Input observations and duplicate records are preserved.']}
    (out/'t20_candidate_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary, indent=2))
    print('OUTPUT DIRECTORY:',out)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    root=Path.home()/'Downloads/betfair_project2'
    parser.add_argument('--identity',type=Path,default=root/'t20_identity_review/market_identity_review.csv')
    parser.add_argument('--prices',type=Path,default=root/'candidates_2021_2026/candidate_ltp_2021_2026.csv')
    parser.add_argument('--out',type=Path,default=root/'t20_market_history')
    a=parser.parse_args()
    for f in (a.identity,a.prices):
        if not f.is_file(): parser.error(f'File missing: {f}')
    run(a.identity,a.prices,a.out)

if __name__=='__main__':
    main()
