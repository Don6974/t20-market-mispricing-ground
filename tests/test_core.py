import pytest
import pandas as pd
from marketlab.core import (validate_quotes,compute_edges,select_opportunities,
                            simulate_returns,chronological_holdout,DataContractError,market_devig)
from marketlab.demo import make_synthetic_quotes

@pytest.fixture
def sample():
    return make_synthetic_quotes(20)

def test_future_quote_rejected(sample):
    sample.loc[0,"quote_ts"]="2027-01-01T00:00:00Z"
    with pytest.raises(DataContractError,match="Look-ahead"):
        validate_quotes(sample)

def test_missing_columns_rejected(sample):
    with pytest.raises(DataContractError,match="Missing required"):
        validate_quotes(sample.drop(columns=["outcome"]))

def test_stale_quote_flag(sample):
    result=validate_quotes(sample,max_age_seconds=60)
    assert (~result.quote_fresh).any() and result.quote_fresh.any()

def test_no_repeated_match_bets(sample):
    d=compute_edges(validate_quotes(sample),commission=0,odds_slippage=0)
    trades=select_opportunities(d,min_expected_roi=0)
    assert not trades.match_id.duplicated().any()

def test_unit_stake_win_and_loss():
    df=pd.DataFrame({"decision_ts":pd.to_datetime(["2025-01-01","2025-01-02"],utc=True),"match_id":["a","b"],"outcome":[1,0],"effective_odds":[3.,2.]})
    result=simulate_returns(df,commission=.05)
    assert result.pnl.tolist()==pytest.approx([1.90,-1.])

def test_edge_math():
    df=pd.DataFrame({"decimal_odds":[2.],"model_probability":[.6]})
    result=compute_edges(df,commission=0,odds_slippage=0)
    assert result.expected_roi.iloc[0]==pytest.approx(.2)
    assert result.break_even_probability.iloc[0]==pytest.approx(.5)

def test_chronological_split_disjoint(sample):
    t,v=chronological_holdout(validate_quotes(sample),fraction=.3)
    assert set(t.match_id).isdisjoint(set(v.match_id))
    assert t.decision_ts.max()<v.decision_ts.min()

def test_conflicting_outcomes_rejected(sample):
    sample.loc[1,"outcome"]=1-int(sample.loc[0,"outcome"])
    with pytest.raises(DataContractError,match="Conflicting outcomes"):
        validate_quotes(sample)

def test_devig():
    a,b,margin=market_devig(1/1.8,1/1.9)
    assert a+b==pytest.approx(1)
    assert margin>0

def test_synthetic_flag(sample):
    assert set(validate_quotes(sample).data_kind)=={"synthetic"}
