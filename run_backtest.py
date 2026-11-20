"""CLI: python run_backtest.py [--csv path] [--out path]."""
import argparse
import json
from pathlib import Path
import pandas as pd
from marketlab.demo import make_synthetic_quotes
from marketlab.core import validate_quotes,compute_edges,select_opportunities,simulate_returns,summarize,chronological_holdout

p=argparse.ArgumentParser()
p.add_argument("--csv",type=Path,help="Real, aligned quote CSV; otherwise fully synthetic demonstration")
p.add_argument("--out",type=Path,default=Path("outputs"))
p.add_argument("--commission",type=float,default=.02)
p.add_argument("--slippage",type=float,default=.02)
p.add_argument("--threshold",type=float,default=.05)
p.add_argument("--max-age-seconds",type=int,default=60)
a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=True)
raw=pd.read_csv(a.csv) if a.csv else make_synthetic_quotes()
frame=compute_edges(validate_quotes(raw,max_age_seconds=a.max_age_seconds),commission=a.commission,odds_slippage=a.slippage)
_,holdout=chronological_holdout(frame)
trades=simulate_returns(select_opportunities(holdout,min_expected_roi=a.threshold),commission=a.commission)
report=summarize(holdout,trades)
(a.out/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
trades.to_csv(a.out/"selected_decisions.csv",index=False)
print(json.dumps(report,indent=2))
