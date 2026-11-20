"""Deterministic simulated matches. NEVER call these real odds or empirical betting results."""
import numpy as np
import pandas as pd


def make_synthetic_quotes(matches: int = 120, seed: int = 2026) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows=[]
    start=pd.Timestamp("2024-01-01",tz="UTC")
    for i in range(matches):
        # Artificial outcome, artificial model and artificial quoted odds.
        true_p=float(rng.beta(2.5,2.5))
        won=int(rng.random()<true_p)
        model_p=float(np.clip(true_p+rng.normal(0,.10),.02,.98))
        ts=start+pd.Timedelta(days=i)
        for step in (0,1,2):
            dec=ts+pd.Timedelta(minutes=step*8)
            q=dec-pd.Timedelta(seconds=int(rng.choice([8,12,35,90])))
            quoted_p=float(np.clip(true_p+rng.normal(0,.10),.08,.92))
            # Fake quote spread is intentionally noisy, not a sportsbook feed.
            odds=round(1/quoted_p,2)
            rows.append({"match_id":f"SIM-{i:04d}","decision_ts":dec.isoformat(),"quote_ts":q.isoformat(),
                         "selection":"chasing_team","decimal_odds":odds,"model_probability":model_p,
                         "outcome":won,"source":"generated_demo_only","data_kind":"synthetic"})
    return pd.DataFrame(rows)
