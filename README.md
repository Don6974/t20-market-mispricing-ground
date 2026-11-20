# T20 Market Mispricing Research Lab

**Author:** Sugandhika Dontha  
**Stage:** Research prototype. **Not a tested profitable betting strategy.**

[Project 1 — T20 chase probability model](https://github.com/Don6974/t20-cricket-win-probability-predictor)

## Why this exists

A win-probability predictor does not show whether an available market price is attractive. This second project provides an auditable, timestamp-aware research pipeline comparing model probabilities against historical quotes, applying estimated execution costs, and reporting *hypothetical* selection performance.

**Default data is 100% synthetic** (outcomes, model probabilities, odds, timestamps). Any sample ROI produced by the demo is **NOT** historical evidence. This repo does **not** yet include licensed/verified historical odds, synced ball timestamps, or evidence of profitable wagers. Uploading a CSV marked `historical` merely labels user-supplied data; it does not independently verify its origin.

## Run locally

```bash
git clone https://github.com/Don6974/t20-market-mispricing-lab.git
cd t20-market-mispricing-lab
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
python run_backtest.py
streamlit run app.py
```

For Streamlit Community Cloud: public GitHub repo, branch `main`, entry `app.py`, Python 3.12. The bundled demo requires no secret key or bookmaker account.

## Data contract for a historical quote CSV

One row per *available* price at a decision point, with columns:

| Column | Meaning |
| --- | --- |
| `match_id` | Stable match identifier, ideally mapped to Cricsheet + exchange event ID |
| `decision_ts` | UTC timestamp at which a hypothetical decision could have occurred |
| `quote_ts` | UTC timestamp when that exact quote became available |
| `selection` | Selection the wager is placed on (e.g., chasing_team) |
| `decimal_odds` | Back odds at the timestamp (not a closing price or retrospectively selected maximum) |
| `model_probability` | As-of estimated probability for the same selection |
| `outcome` | Settled selection result, 1 or 0 (used **only for evaluation**) |
| `source` | Provenance label / exchange feed name |
| `data_kind` | `synthetic` or `historical` — user's label, not independent verification |

Timestamp inequalities enforced: `quote_ts <= decision_ts`, and optionally `decision_ts - quote_ts <= max_age_seconds` for candidate selection. Stale quotes are counted and rejected. Only one earliest qualifying opportunity per match is selected by default. A later quote cannot be used to revise an earlier decision. To prevent overlap and correlated exposure, one match/one selection is the starting constraint.

### Crucial limits of CSV validation

Cricsheet records ball sequence but generally **not the actual exchange-available quote per ball**. To reconstruct genuine in-play states you need contemporaneous event timing, exact match/runner mapping, suspension windows, and odds feed timestamps. Do **not** align a ball with a quote solely by over number or assume delivery timestamps from approximate broadcast timelines. Model probability features and weights must also be available **as of decision time**. This repo checks quote chronology but cannot independently authenticate probability lineage.

## Economics

For decimal back odds `o`, downward assumed odds slippage `s`, commission fraction `c` charged on winning profits, and model probability `p`:

- Effective odds: `o_eff = o - s` (must exceed 1)
- Raw implied probability: `1/o`
- Break-even probability including costs: `1 / (1 + (o_eff - 1)*(1-c))`
- Model-estimated expected ROI: `p*(o_eff-1)*(1-c) - (1-p)`
- Unit-stake realized payoff (hypothetical): `+(o_eff-1)*(1-c)` on win, `-1` on loss

`market_devig` demonstrates proportional two-way margin removal, which is meaningful **only when the opposing selections are simultaneous**. Backtesting uses cost-adjusted break-even instead of using no-vig probability as a fill price.

## What the prototype does

- Validates quote schema, duplicate keys, future quotes, freshness, odds and probabilities.
- Makes match-disjoint chronological splits and selects the latest 30% of matches for the demo holdout.
- Calculates cost-aware EV and price-implied probabilities; takes the earliest qualifying quote once per match.
- Simulates unit stakes, win/loss payoffs, total P/L and ROI; displays descriptive calibration bins.
- Includes explicit **synthetic data** labelling and unit tests for look-ahead rejection and payout math.

## What it does *not* establish

- The model probability quality: supplied probabilities are not retrained by this project; `model_probability` must come from an independently validated, chronologically trained as-of model.
- Realistic fill probability, queue position, market liquidity, bet rejection, exchange delays, suspensions, withdrawals, matching, bankroll solvency, settlement schedule, or limits.
- Valid independent confidence intervals: states from the same match are correlated, and the UI's cumulative P/L is arranged by decision time, not actual settlement time.
- An optimal strategy: thresholds and costs can be adjusted interactively, which invalidates an untouched holdout if selected by looking at test performance. Freeze settings on earlier data before testing.

## Next research milestones (for a serious trading portfolio)

1. Obtain appropriately licensed, timestamped **cricket match-odds exchange data**, documenting archive coverage, price types and trade volumes. Betfair Historical Data is a candidate, not included here.
2. Map exchange market/runner IDs to Cricsheet matches and **genuine ball event timestamps**; measure and report alignment uncertainty, and drop ambiguous records.
3. Generate genuine probability snapshots using Project 1 or a newly trained model with historical cutoff dates, avoiding retraining on the evaluation period.
4. Compare *pre-registered* thresholds and baseline prices on a future, unseen chronological holdout. Include costs, liquidity and fill modelling.
5. Add match-block bootstrap confidence intervals, calibration by probability band and innings phase, robustness checks and repeated holdout periods.

## Data suppliers to investigate

- [Cricsheet](https://cricsheet.org/downloads/) — ball-by-ball results/events (not betting quote timestamps)
- [Betfair historical exchange portal](https://historicdata.betfair.com/) — timestamped historical market data; registration and potential paid access required
- [Betfair historical data documentation](https://support.developer.betfair.com/hc/en-us/articles/360002407732-What-data-is-provided-by-the-Historical-Data-service)
- [Decimal historical cricket and odds](https://www.decimaldatagroup.com/historical-cricket-data-and-odds) — request licensing and coverage details

## Responsibility

This project is for quantitative research and education. No real-money trading instructions, implied profit guarantees, or claims of demonstrated positive expected value are provided. Do not place bets based on the demo.
