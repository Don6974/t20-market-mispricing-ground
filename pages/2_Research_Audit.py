"""Local research summaries; safe info message when data isn't present on cloud."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Historical Market Research Audit', layout='wide')
st.title('Historical Market Research Audit')
st.warning('Betfair LTP is not an available back quote. Name/date links are candidates, not independently verified fixtures. No real historical ROI has been established.')
base = Path.home() / 'Downloads/betfair_project2/t20_market_history/research_outputs'
expected = [base / 'research_audit.json', base / 'annual_research.csv', base / 'market_diagnostics.csv', base / 'runner_diagnostics.csv']
if not all(p.exists() for p in expected):
    st.info('Local research outputs are not installed on this machine. Run `python scripts/final_research_pipeline.py` locally. This page does not publish or bundle licensed historical data.')
    st.stop()

with expected[0].open(encoding='utf-8') as f:
    audit = json.load(f)
annual = pd.read_csv(expected[1], dtype={'year': str})
markets = pd.read_csv(expected[2], dtype={'market_id': str})
runners = pd.read_csv(expected[3], dtype={'market_id': str, 'runner_id': str})

c1, c2, c3 = st.columns(3)
c1.metric('Markets with two runner histories', f"{audit['complete_two_runner_markets']:,}")
c2.metric('Cleaned LTP observations', f"{audit['retained_observations']:,}")
c3.metric('Independent identity verification', 'Not established')

st.subheader('Annual coverage')
st.bar_chart(annual.set_index('year')['markets'])
st.dataframe(annual, use_container_width=True, hide_index=True)
st.caption('Aggregate metrics use each market as a unit where possible. Years vary in coverage and 2026 is incomplete.')

st.subheader('Recorded price-movement magnitude')
st.write('95th-percentile absolute implied-probability movements per runner; these compare consecutive LTP records, not a fixed time interval.')
metric = 'p95_abs_probability_move_pp'
non_null = runners[metric].dropna()
if not non_null.empty:
    st.bar_chart(non_null.value_counts(bins=15).sort_index())
    st.metric('Median across runner histories (percentage points)', f'{non_null.median():.3f}')

st.subheader('Observation gaps')
gaps = runners['p95_gap_seconds'].dropna()
if not gaps.empty:
    st.metric('Median of runner-level p95 gaps (seconds)', f'{gaps.median():.1f}')
    st.caption('These are gaps between recorded last trades; NOT periods of market availability.')

st.subheader('Identity and sample-quality status')
st.dataframe(markets[['market_id', 'year', 'event_name', 'review_status', 'runner_histories', 'min_runner_observations', 'research_coverage_flag']].head(200), use_container_width=True, hide_index=True)
st.caption('First 200 local rows shown. Names may be subject to the original data provider’s licence. Do not publish these files without permission.')

st.subheader('Why a genuine trading ROI is not shown')
for value in audit['research_readiness'].values():
    st.write('- ' + value)

st.download_button('Download local audit JSON', json.dumps(audit, indent=2), file_name='local_research_audit.json', mime='application/json')
