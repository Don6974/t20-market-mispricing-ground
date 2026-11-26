#!/usr/bin/env python3
"""Project 2 research finishing pipeline. No fabricated ROI or quote availability.

Run: python scripts/final_research_pipeline.py
Optional: python scripts/final_research_pipeline.py --base /path/to/t20_market_history

Reads existing LOCAL SQLite and CSV data. Writes summaries to LOCAL research_outputs.
Does not modify or upload licensed raw data.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

DEFAULT_BASE = Path.home() / 'Downloads/betfair_project2/t20_market_history'
IDENTITY_NAME = 'market_identity_review.csv'


def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, columns):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def to_epoch(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc).timestamp()
    except (ValueError, OverflowError, TypeError):
        return None


def percentile(sorted_values, quantile):
    """Simple linear interpolation; input must be sorted."""
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * quantile
    lo, hi = math.floor(k), math.ceil(k)
    return sorted_values[lo] if lo == hi else sorted_values[lo] * (hi - k) + sorted_values[hi] * (k - lo)


def safe_round(value, digits=3):
    return None if value is None else round(float(value), digits)


def summarize_runner(market_id, runner_id, entries):
    """Entries are (timestamp string, LTP float), ordered by timestamp.

    Real last-traded events are not executable back quotes. Nonpositive gaps,
    duplicate timestamps and invalid values are tracked, not silently imputed.
    """
    first_by_timestamp = {}
    duplicates = 0
    conflicts = 0
    invalid = 0
    for ts, price in entries:
        epoch = to_epoch(ts)
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = float('nan')
        if epoch is None or not math.isfinite(price) or price <= 1:
            invalid += 1
            continue
        if ts in first_by_timestamp:
            if first_by_timestamp[ts][1] == price:
                duplicates += 1
            else:
                conflicts += 1
            continue
        first_by_timestamp[ts] = (epoch, price)
    clean = sorted(first_by_timestamp.values())
    if not clean:
        return {'market_id': market_id, 'runner_id': runner_id, 'observations': 0,
                'invalid_rows': invalid, 'exact_duplicate_rows': duplicates,
                'conflicting_timestamp_rows': conflicts}
    gaps = []
    movements = []
    for (prev_t, prev_price), (cur_t, cur_price) in zip(clean, clean[1:]):
        gap = cur_t - prev_t
        if gap > 0:
            gaps.append(gap)
            movements.append(abs(100 / cur_price - 100 / prev_price))
    gaps.sort()
    movements.sort()
    prices = [p for _, p in clean]
    return {
        'market_id': market_id, 'runner_id': runner_id,
        'observations': len(clean), 'invalid_rows': invalid,
        'exact_duplicate_rows': duplicates, 'conflicting_timestamp_rows': conflicts,
        'first_timestamp_utc': datetime.fromtimestamp(clean[0][0], tz=timezone.utc).isoformat(),
        'last_timestamp_utc': datetime.fromtimestamp(clean[-1][0], tz=timezone.utc).isoformat(),
        'price_min': safe_round(min(prices), 4), 'price_max': safe_round(max(prices), 4),
        'recorded_price_changes': sum(p1 != p2 for p1, p2 in zip(prices, prices[1:])),
        'median_gap_seconds': safe_round(percentile(gaps, 0.5)),
        'p95_gap_seconds': safe_round(percentile(gaps, 0.95)),
        'max_gap_seconds': safe_round(gaps[-1] if gaps else None),
        'median_abs_probability_move_pp': safe_round(percentile(movements, 0.5)),
        'p95_abs_probability_move_pp': safe_round(percentile(movements, 0.95)),
        'probability_range_pp': safe_round(max(100 / p for p in prices) - min(100 / p for p in prices)),
        'observed_span_hours': safe_round((clean[-1][0] - clean[0][0]) / 3600),
    }

RUNNER_COLUMNS = [
    'market_id', 'runner_id', 'observations', 'invalid_rows',
    'exact_duplicate_rows', 'conflicting_timestamp_rows',
    'first_timestamp_utc', 'last_timestamp_utc', 'price_min', 'price_max',
    'recorded_price_changes', 'median_gap_seconds', 'p95_gap_seconds',
    'max_gap_seconds', 'median_abs_probability_move_pp',
    'p95_abs_probability_move_pp', 'probability_range_pp', 'observed_span_hours'
]
MARKET_COLUMNS = [
    'market_id', 'year', 'event_name', 'cricsheet_file', 'identity_status',
    'review_status', 'runner_histories', 'observations', 'recorded_price_changes',
    'min_runner_observations', 'median_runner_gap_seconds',
    'max_runner_p95_gap_seconds', 'max_runner_p95_abs_probability_move_pp',
    'complete_two_runner_history', 'research_coverage_flag'
]
YEAR_COLUMNS = [
    'year', 'markets', 'runner_histories', 'observations',
    'price_changes', 'median_runner_gap_seconds',
    'median_runner_p95_abs_probability_move_pp', 'markets_with_sparse_history'
]


def run(base: Path, identity_path: Path | None = None):
    base = base.expanduser().resolve()
    database = base / 'price_analysis.sqlite'
    quality = base / 'market_quality_shortlist.csv'
    if not database.is_file() or not quality.is_file():
        raise FileNotFoundError(f'Expected existing files: {database} and {quality}')
    if identity_path is None:
        identity_path = base.parent / 't20_identity_review' / IDENTITY_NAME
    if not identity_path.is_file():
        raise FileNotFoundError(f'Identity review missing: {identity_path}')
    output = base / 'research_outputs'
    output.mkdir(exist_ok=True)

    identity_rows = read_csv(identity_path)
    status_counts = Counter(row.get('status', 'missing') for row in identity_rows)
    identity = {row['market_id']: row for row in identity_rows}
    if len(identity) != len(identity_rows):
        raise ValueError('Duplicate market IDs in identity file: stop and reconcile.')
    quality_rows = read_csv(quality)
    eligible = {}
    for row in quality_rows:
        if row.get('quality_status') == 'review_candidate':
            mid = str(row.get('market_id', '')).strip()
            if mid in eligible:
                raise ValueError(f'Duplicate candidate market ID: {mid}')
            if mid not in identity or identity[mid].get('status') != 'exact_name_date_candidate':
                raise ValueError(f'Candidate {mid} lacks compatible identity row')
            eligible[mid] = row

    # Manual human claims are separate from automatic name/date candidates.
    # No historical identity is called independently verified by this script.
    manual_file = output / 'manual_identity_review.csv'
    manual = {}
    if manual_file.exists():
        for row in read_csv(manual_file):
            mid = row.get('market_id', '').strip()
            if mid in manual:
                raise ValueError(f'Duplicate manual identity review for {mid}')
            if mid not in eligible:
                raise ValueError(f'Unknown manually reviewed market: {mid}')
            status = row.get('review_status', 'unreviewed').strip().lower()
            if status not in ('unreviewed', 'verified_by_reviewer', 'rejected'):
                raise ValueError(f'Invalid review status for {mid}: {status}')
            if status == 'verified_by_reviewer' and not row.get('evidence_url', '').strip():
                raise ValueError(f'Verification claim requires evidence_url: {mid}')
            manual[mid] = row
    else:
        # Template only; left unreviewed, no automatic verification claims.
        candidates = sorted(eligible.values(), key=lambda r: -int(r.get('inplay_rows') or 0))[:30]
        write_csv(manual_file, [dict(market_id=r['market_id'], event_name=r.get('event_name', ''),
                                     review_status='unreviewed', evidence_url='', reviewer_notes='') for r in candidates],
                  ['market_id', 'event_name', 'review_status', 'evidence_url', 'reviewer_notes'])

    # Read only, and use a streaming cursor rather than loading the whole price history.
    uri = database.as_uri() + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    columns = {r[1] for r in conn.execute('PRAGMA table_info(prices)')}
    needed = {'market_id', 'runner_id', 'timestamp', 'price'}
    if not needed <= columns:
        raise ValueError(f'SQLite prices table lacks: {sorted(needed - columns)}')
    runner_rows = []
    market_to_runners = defaultdict(list)
    current_key, buffer = None, []
    query = 'SELECT market_id, runner_id, timestamp, price FROM prices ORDER BY market_id, runner_id, timestamp'
    for mid, rid, ts, price in conn.execute(query):
        key = (str(mid), str(rid))
        if key != current_key and current_key is not None:
            if current_key[0] in eligible:
                r = summarize_runner(*current_key, buffer)
                runner_rows.append(r)
                market_to_runners[current_key[0]].append(r)
            buffer = []
        current_key = key
        buffer.append((ts, price))
    if current_key is not None and current_key[0] in eligible:
        r = summarize_runner(*current_key, buffer)
        runner_rows.append(r)
        market_to_runners[current_key[0]].append(r)
    conn.close()

    market_rows = []
    for mid, row in sorted(eligible.items()):
        runners = [r for r in market_to_runners.get(mid, []) if r['observations'] > 0]
        has_two = len(runners) == 2
        n = sum(r['observations'] for r in runners)
        sparse = not has_two or min((r['observations'] for r in runners), default=0) < 10
        stats = [r['median_gap_seconds'] for r in runners if r.get('median_gap_seconds') is not None]
        p95gaps = [r['p95_gap_seconds'] for r in runners if r.get('p95_gap_seconds') is not None]
        p95moves = [r['p95_abs_probability_move_pp'] for r in runners if r.get('p95_abs_probability_move_pp') is not None]
        m = {
            'market_id': mid, 'year': row.get('market_time_utc','')[:4],
            'event_name': row.get('event_name',''), 'cricsheet_file': row.get('cricsheet_file',''),
            'identity_status': identity[mid].get('status',''),
            'review_status': manual.get(mid, {}).get('review_status', 'unreviewed'),
            'runner_histories': len(runners), 'observations': n,
            'recorded_price_changes': sum(r.get('recorded_price_changes', 0) for r in runners),
            'min_runner_observations': min((r['observations'] for r in runners), default=0),
            'median_runner_gap_seconds': safe_round(median(stats)) if stats else None,
            'max_runner_p95_gap_seconds': max(p95gaps) if p95gaps else None,
            'max_runner_p95_abs_probability_move_pp': max(p95moves) if p95moves else None,
            'complete_two_runner_history': has_two,
            'research_coverage_flag': 'sparse_or_incomplete' if sparse else 'minimum_10_observations_per_runner',
        }
        market_rows.append(m)

    # Annual aggregation includes only exactly-two-runner markets, consistent with the previous shortlist.
    years = defaultdict(list)
    for m in market_rows:
        if m['complete_two_runner_history']:
            years[m['year']].append(m)
    annual = []
    for year, markets in sorted(years.items()):
        gaps = [m['median_runner_gap_seconds'] for m in markets if m['median_runner_gap_seconds'] is not None]
        moves = [m['max_runner_p95_abs_probability_move_pp'] for m in markets if m['max_runner_p95_abs_probability_move_pp'] is not None]
        annual.append({
            'year': year, 'markets': len(markets), 'runner_histories': sum(m['runner_histories'] for m in markets),
            'observations': sum(m['observations'] for m in markets),
            'price_changes': sum(m['recorded_price_changes'] for m in markets),
            'median_runner_gap_seconds': safe_round(median(gaps)) if gaps else None,
            'median_runner_p95_abs_probability_move_pp': safe_round(median(moves)) if moves else None,
            'markets_with_sparse_history': sum(m['research_coverage_flag'] == 'sparse_or_incomplete' for m in markets)
        })

    write_csv(output / 'runner_diagnostics.csv', runner_rows, RUNNER_COLUMNS)
    write_csv(output / 'market_diagnostics.csv', market_rows, MARKET_COLUMNS)
    write_csv(output / 'annual_research.csv', annual, YEAR_COLUMNS)
    reviewer_counts = Counter(m['review_status'] for m in market_rows)
    blockers = {
        'verified_fixture_and_runner_identity': 'NOT ESTABLISHED: name/date candidates only; manual reviewer evidence is not independent verification',
        'ball_event_utc_timestamps': 'MISSING: Cricsheet ball sequence alone cannot reconstruct exact live decision time',
        'historically_available_back_odds_and_volume': 'MISSING: LTP is a past trade, not an executable back quote',
        'historical_as_of_model_predictions': 'MISSING: no independently documented contemporaneous predictions',
        'historical_profit_backtest': 'BLOCKED: conditions above are necessary; intentionally no ROI is produced'
    }
    audit = {
        'scope': 'local research; candidate identity and historical LTP, not executable prices',
        'identity_status_counts': dict(status_counts),
        'quality_review_candidate_markets': len(eligible),
        'complete_two_runner_markets': sum(m['complete_two_runner_history'] for m in market_rows),
        'runner_histories': len(runner_rows),
        'retained_observations': sum(m['observations'] for m in market_rows if m['complete_two_runner_history']),
        'manual_review_counts': dict(reviewer_counts),
        'date_range_by_market_metadata': sorted(years),
        'research_readiness': blockers,
        'scope_notes': [
            'Market-year allocation uses market_time_utc, not the observation timestamp.',
            'Price movements reflect consecutive recorded LTP observations, not constant time sampling.',
            'No automatic inference of official ball time or market quote executable status.',
            'Dataset summaries may be subject to provider redistribution terms; do not upload without checking license.'
        ]
    }
    (output / 'research_audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    markdown = f'''# T20 Historical Market Research — Audit Report\n\n**Dataset:** Betfair Basic last-traded-price observations; candidate Cricsheet match links.\n\n## Selection results\n- Automatic name/date identity candidates (all statuses): {sum(status_counts.values()):,}\n- Candidate markets with two-runner and some in-play data: {len(eligible):,}\n- Markets with both runners represented in cleaned live OPEN-market database: {audit['complete_two_runner_markets']:,}\n- Retained observations within those complete markets: {audit['retained_observations']:,}\n\n## What the project can currently claim\nDescriptive historical LTP movements, timestamp gaps, market completeness and annual coverage for candidate T20 markets. These are *not* necessarily verified fixtures.\n\n## Hard blockers for any real ROI claim\n'''
    for name, reason in blockers.items():
        markdown += f'- **{name.replace("_", " ").capitalize()}:** {reason}\n'
    markdown += '''\n## Manual review instructions\nOpen `manual_identity_review.csv`. For every row, compare the fixture date, team names, event name, cricket format, and runner selection identities with trusted external records. Mark `verified_by_reviewer` **only after** recording an evidence URL; otherwise keep `unreviewed` or `rejected`. Then rerun this script. Manual claims are not independently authenticated.\n\n## Next valid experiment\nObtain real ball-event UTC timestamps, verified runner/fixture links, as-of model predictions and contemporaneous *available* quotes (not LTP), then design a pre-registered, match-disjoint chronological holdout and a fill/cost model. Until then do not calculate or advertise historical profitability.\n'''
    (output / 'RESEARCH_REPORT.md').write_text(markdown, encoding='utf-8')
    print('\nSTAGES 9–13 RESEARCH AUDIT (LOCAL)')
    print('Candidate shortlist:', len(eligible))
    print('Complete two-runner markets:', audit['complete_two_runner_markets'])
    print('Retained LTP observations:', audit['retained_observations'])
    print('Yearly report:')
    for r in annual:
        print(' ', r['year'], 'markets:', r['markets'], 'observations:', r['observations'], 'median runner gap (s):', r['median_runner_gap_seconds'])
    print('Historical ROI: BLOCKED (never inferred from LTP)')
    print('Reports saved:', output)
    return audit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, default=DEFAULT_BASE)
    p.add_argument('--identity', type=Path, default=None)
    args = p.parse_args()
    run(args.base, args.identity)


if __name__ == '__main__':
    main()
