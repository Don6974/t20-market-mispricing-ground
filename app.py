from pathlib import Path
import pandas as pd
import streamlit as st
from marketlab.core import (DataContractError,validate_quotes,compute_edges,select_opportunities,
                            simulate_returns,summarize,chronological_holdout,probability_diagnostics)
from marketlab.demo import make_synthetic_quotes

st.set_page_config(page_title="T20 Market Mispricing Research Lab",layout="wide",page_icon="🏏")
st.title("T20 Market Mispricing Research Lab")
st.warning("RESEARCH DEMO — synthetic prices are NOT historical market evidence. No verified betting profitability or executable strategy is claimed.")
st.markdown("Compare *as-of* model probabilities with bookmaker/exchange quotes, reject stale/future quotes, and test hypothetical **back** positions under explicit costs.")
mode=st.radio("Data",["Synthetic demonstration","Upload timestamped quote CSV"],horizontal=True)
if mode=="Synthetic demonstration":
    raw=make_synthetic_quotes()
    st.caption("120 completely simulated matches, 360 generated quotations. Outcomes and odds are artificial.")
else:
    file=st.file_uploader("CSV with required schema (see README)",type="csv")
    if file is None:
        st.stop()
    raw=pd.read_csv(file)
    st.info("CSV content is user supplied; app cannot verify genuine provenance, timestamp synchronization, or model feature lineage.")
with st.sidebar:
    st.header("Execution assumptions")
    commission=st.slider("Commission on winning profit (%)",0.,10.,2.,.5)/100
    slippage=st.number_input("Unfavourable decimal-odds slippage",0.,1.,0.02,0.01)
    max_age=st.number_input("Max quote age (seconds)",1,3600,60)
    threshold=st.slider("Minimum model-estimated ROI (%)",0.,30.,5.,1.)/100
    only_test=st.checkbox("Evaluate only last 30% of matches",value=True)
try:
    universe=validate_quotes(raw,max_age_seconds=int(max_age))
    universe=compute_edges(universe,commission=commission,odds_slippage=slippage)
    if only_test:
        _,universe=chronological_holdout(universe)
    selected=select_opportunities(universe,min_expected_roi=threshold,one_per_match=True)
    trades=simulate_returns(selected,commission=commission)
    report=summarize(universe,trades)
except (DataContractError,ValueError,KeyError) as exc:
    st.error(f"Invalid inputs: {exc}")
    st.stop()

cols=st.columns(4)
cols[0].metric("Matches",f"{report['matches']:,}")
cols[1].metric("Candidate positions",report["trades"])
cols[2].metric("Hypothetical net P/L (units)",f"{report['net_pnl_units']:+.2f}")
cols[3].metric("Hypothetical unit-stake ROI", "N/A" if report["unit_stake_roi"] is None else f"{report['unit_stake_roi']*100:+.2f}%")
st.caption(f"Rejected stale quotes: {report['stale_quotes']}; all prices are assumed offered and filled at adjusted odds. No order-book liquidity, delays, suspensions, or settlement latency modeled.")
st.subheader("Selected decisions (earliest eligible per match)")
cols_show=["match_id","decision_ts","quote_ts","decimal_odds","effective_odds","model_probability","implied_probability","break_even_probability","expected_roi","outcome","pnl"]
st.dataframe(trades[cols_show],use_container_width=True,hide_index=True)
st.download_button("Download research trades CSV",trades.to_csv(index=False),"t20_candidate_positions.csv","text/csv")
if not trades.empty:
    st.subheader("Cumulative hypothetical units (not a bankroll curve)")
    st.line_chart(trades.set_index("decision_ts")["cumulative_pnl"])
st.subheader("Descriptive probability calibration")
cal=probability_diagnostics(universe)
st.dataframe(cal,hide_index=True)
st.caption("Rows within a match are correlated. These bins do not provide independent observations or profitability evidence.")
with st.expander("Required CSV structure"):
    st.code("match_id,decision_ts,quote_ts,selection,decimal_odds,model_probability,outcome,source,data_kind\nM001,2025-01-01T12:00:00Z,2025-01-01T11:59:50Z,chasing_team,2.10,0.55,1,exchange,historical",language="csv")
    st.write("Outcome must be the eventual 0/1 result for the named selection; model probabilities must have been generated without information from after decision_ts. Quote timestamps alone do not prove this.")
