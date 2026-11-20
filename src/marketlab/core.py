"""Time-aware, conservative binary cricket market research. No profitability claims."""
from __future__ import annotations
import numpy as np
import pandas as pd

REQUIRED = ["match_id", "decision_ts", "quote_ts", "selection", "decimal_odds", "model_probability", "outcome", "source", "data_kind"]

class DataContractError(ValueError):
    pass


def validate_quotes(frame: pd.DataFrame, *, max_age_seconds: int = 60) -> pd.DataFrame:
    """Validate timestamps and inputs. Inputs are already *joined* to match states by upstream data provider.

    Does NOT establish that a model's p was generated as-of decision_ts; that requires
    independent point-in-time feature lineage and a model trained before the event.
    """
    missing = sorted(set(REQUIRED) - set(frame.columns))
    if missing:
        raise DataContractError(f"Missing required columns: {missing}")
    if max_age_seconds < 0:
        raise DataContractError("max_age_seconds must be non-negative")
    out = frame.copy()
    if out.empty:
        raise DataContractError("No quote rows")
    for field in ["decision_ts", "quote_ts"]:
        out[field] = pd.to_datetime(out[field], utc=True, errors="coerce")
        if out[field].isna().any():
            raise DataContractError(f"Invalid or missing UTC timestamp: {field}")
    for col in ["decimal_odds", "model_probability", "outcome"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
        if not np.isfinite(out[col].to_numpy(dtype=float)).all():
            raise DataContractError(f"Nonfinite or missing values in {col}")
    if (out.decimal_odds <= 1).any():
        raise DataContractError("Decimal odds must be greater than 1")
    if (~out.model_probability.between(0, 1)).any():
        raise DataContractError("model_probability must be in [0,1]")
    if (~out.outcome.isin([0,1])).any():
        raise DataContractError("outcome must be 0 or 1")
    if out[["match_id", "selection", "source", "data_kind"]].isna().any().any():
        raise DataContractError("Missing match identifier, selection, source, or data_kind")
    if (~out.data_kind.isin(["synthetic", "historical"])).any():
        raise DataContractError("data_kind must be synthetic or historical")
    if len(set(out.data_kind)) != 1:
        raise DataContractError("Synthetic and historical rows cannot be mixed")
    if (out.quote_ts > out.decision_ts).any():
        raise DataContractError("Look-ahead detected: quote_ts exceeds decision_ts")
    out["quote_age_seconds"] = (out.decision_ts - out.quote_ts).dt.total_seconds()
    out["quote_fresh"] = out.quote_age_seconds <= max_age_seconds
    if out.duplicated(["match_id", "selection", "decision_ts", "source"]).any():
        raise DataContractError("Duplicate quote decision keys")
    # Check for inconsistent settled outcomes of the *same* selection per match.
    if (out.groupby(["match_id", "selection"]).outcome.nunique() > 1).any():
        raise DataContractError("Conflicting outcomes within a match and selection")
    return out.sort_values(["decision_ts", "match_id", "selection"]).reset_index(drop=True)


def compute_edges(frame: pd.DataFrame, *, commission: float = 0.02, odds_slippage: float = 0.0) -> pd.DataFrame:
    """Simple back-odds economics. Commission is charged on *net winning profit*.

    odds_slippage is a conservative *decimal odds* decrement, not a percentage.
    """
    if not 0 <= commission < 1:
        raise DataContractError("commission must be in [0,1)")
    if odds_slippage < 0:
        raise DataContractError("odds_slippage cannot be negative")
    out = frame.copy()
    out["effective_odds"] = out.decimal_odds - odds_slippage
    if (out.effective_odds <= 1).any():
        raise DataContractError("Slippage makes odds <= 1")
    out["implied_probability"] = 1 / out.decimal_odds
    out["break_even_probability"] = 1 / (1 + (out.effective_odds - 1) * (1 - commission))
    out["expected_roi"] = out.model_probability * (out.effective_odds - 1) * (1 - commission) - (1 - out.model_probability)
    out["edge_pp"] = 100 * (out.model_probability - out.break_even_probability)
    return out


def select_opportunities(frame: pd.DataFrame, *, min_expected_roi: float = 0.03, one_per_match: bool = True) -> pd.DataFrame:
    if min_expected_roi < 0:
        raise DataContractError("Minimum expected ROI must not be negative")
    accepted = frame[(frame.quote_fresh) & (frame.expected_roi >= min_expected_roi)].copy()
    # Choose earliest actionable moment in each match: prevents future-selection bias
    # from retrospectively picking the best price across the entire match.
    accepted = accepted.sort_values(["decision_ts", "match_id", "selection"])
    if one_per_match:
        accepted = accepted.drop_duplicates("match_id", keep="first")
    return accepted.reset_index(drop=True)


def simulate_returns(selected: pd.DataFrame, *, commission: float = 0.02, stake: float = 1.0) -> pd.DataFrame:
    if stake <= 0:
        raise DataContractError("stake must be positive")
    if not 0 <= commission < 1:
        raise DataContractError("commission must be in [0,1)")
    out = selected.sort_values(["decision_ts", "match_id"]).copy()
    out["stake"] = float(stake)
    out["pnl"] = np.where(out.outcome == 1, stake * (out.effective_odds - 1) * (1 - commission), -stake)
    out["cumulative_pnl"] = out.pnl.cumsum()
    # Returns are computed in decision-time order, not settlement-time order.
    # This is a unit-stake diagnostic, NOT a realizable bankroll path.
    return out


def summarize(universe: pd.DataFrame, trades: pd.DataFrame) -> dict:
    n = len(trades)
    pnl = float(trades.pnl.sum()) if n else 0.0
    stakes = float(trades.stake.sum()) if n else 0.0
    return {
        "data_kind": universe.data_kind.iloc[0],
        "quotes": len(universe),
        "stale_quotes": int((~universe.quote_fresh).sum()),
        "matches": int(universe.match_id.nunique()),
        "trades": n,
        "total_staked_units": stakes,
        "net_pnl_units": round(pnl, 4),
        "unit_stake_roi": round(pnl / stakes, 5) if stakes else None,
        "win_rate": round(float(trades.outcome.mean()), 5) if n else None,
        "mean_estimated_roi": round(float(trades.expected_roi.mean()), 5) if n else None,
        "note": "Synthetic returns are illustrative only. Historical quotes alone do not establish executable fill prices or causal probability inputs."
    }


def chronological_holdout(frame: pd.DataFrame, *, fraction: float = .3) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Match-disjoint holdout based on earliest decision time, not quote-row shuffling."""
    if not 0 < fraction < 1:
        raise DataContractError("fraction must be between zero and one")
    dates = frame.groupby("match_id").decision_ts.min().sort_values()
    if len(dates) < 4:
        raise DataContractError("Need >=4 matches for chronological split")
    cutoff = dates.iloc[int(len(dates) * (1 - fraction))]
    # Same timestamp belongs to one side; match ID never appears in both.
    test_ids = set(dates[dates >= cutoff].index)
    train = frame[~frame.match_id.isin(test_ids)].copy()
    test = frame[frame.match_id.isin(test_ids)].copy()
    if train.empty or test.empty:
        raise DataContractError("Cannot form nonempty chronological splits")
    return train, test


def probability_diagnostics(frame: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    """Descriptive state-level calibration; not an independent-match uncertainty interval."""
    out = frame.copy()
    out["bin"] = np.minimum((out.model_probability * bins).astype(int), bins - 1)
    return out.groupby("bin",as_index=False).agg(predicted=("model_probability","mean"),observed=("outcome","mean"),n=("outcome","size"))


def market_devig(p_a: float, p_b: float) -> tuple[float,float,float]:
    """Proportional de-vig of two *simultaneous* mutually exclusive back quotes."""
    if not (0 < p_a < 1 and 0 < p_b < 1):
        raise DataContractError("Both raw implied probabilities must be between zero and one")
    total = p_a + p_b
    return p_a / total, p_b / total, total - 1
