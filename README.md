# T20 Market Mispricing Research Lab

**Sugandhika Dontha | Cricket Analytics Project**

[Live App](https://dontha-t20-market-mispricing-ground.streamlit.app/) | [Project 1 – T20 Win Probability Predictor](https://github.com/Don6974/t20-cricket-win-probability-predictor)

## About this project

I built this project to study how betting market prices change during T20 cricket matches and explore whether a win-probability model could help identify differences between predicted probabilities and market prices.

In my first project, I developed a model that estimates a team's chances of winning a T20 match based on the match situation.

For this second project, I wanted to understand the betting market side of cricket. I started by collecting historical Betfair data, checking its quality and analysing how prices moved during matches.

The project includes historical market analysis and a separate trading demonstration that uses simulated data.

## Data collection and filtering

I downloaded historical Betfair cricket market data covering 2021 to 2026. I also used Cricsheet's ball-by-ball T20 records to identify possible matches.

The original data contained different types of cricket betting markets, so I filtered it in stages.

1. **Match odds:** I selected markets related to the match winner rather than individual player performances or innings totals.
2. **Two-team markets:** I looked for markets with two selections that could represent the competing teams.
3. **T20 matching:** I compared team names and match dates with Cricsheet's T20 records.
4. **Historical prices:** I checked whether the selected markets had recorded prices, particularly during live play.
5. **Data cleaning:** I removed identical repeated price observations and checked for conflicting timestamps.
6. **Market completeness:** I kept markets where both selections had usable price histories in the cleaned in-play data.

The name-and-date matching process identified **1,449 possible T20 markets**.

After checking price availability and runner coverage, **1,391 candidate markets** remained in the main analysis.

These are candidate matches. The matching process does not independently confirm that every Betfair market belongs to the correct Cricsheet fixture.

## Historical market analysis

The annual analysis covers **338,395 recorded last-traded price observations** from 2021 to 2026.

| Year | Markets | Price observations |
|---|---:|---:|
| 2021 | 105 | 30,631 |
| 2022 | 160 | 46,538 |
| 2023 | 137 | 34,632 |
| 2024 | 370 | 92,117 |
| 2025 | 285 | 67,647 |
| 2026 | 334 | 66,830 |
| **Total** | **1,391** | **338,395** |

These figures describe the selected dataset, not the entire T20 betting market.

I analysed how recorded prices changed over time, how frequently updates occurred, and how market coverage varied across years.

I also looked at the size of movements in implied probability, gaps between observations and markets with limited price history.

One thing I learned was that simply counting price changes is not enough. A move from 2.00 to 1.99 is very different from a move from 2.00 to 1.40, even though both count as one price change.

The analysis therefore looks at the size of probability movements as well as their frequency.

## Historical dashboard

I built an interactive Streamlit dashboard to explore the historical data.

The local dashboard allows me to select a market and view:

- Historical last-traded prices for both selections.
- Implied probabilities calculated from decimal odds.
- Price movements and gaps between recorded updates.
- Runner-level statistics and data-quality checks.
- Annual market coverage and research summaries.

I also built a Research Audit page to show which parts of the historical data are usable and which still require verification.

The historical price files are stored locally and are not included in this public GitHub repository.

## Trading research demonstration

The public app includes a separate demonstration of how model probabilities can be compared with betting odds.

It calculates implied probabilities, estimates potential value after commission and assumed price slippage, and shows hypothetical betting results.

It also checks quote timestamps and rejects quotes that are too old or come from after the supposed decision time.

The demonstration uses **simulated data**, not the historical Betfair observations analysed in the local dashboard.

Its profit and loss results are examples used to test the calculations. They are not evidence of a profitable betting strategy.

[Open the Streamlit App](https://dontha-t20-market-mispricing-ground.streamlit.app/)

## Tools used

| Tool | How I used it |
|---|---|
| Python | Extracting, cleaning and analysing historical data |
| Pandas | Data filtering, calculations and summaries |
| SQLite and SQL | Storing and querying historical price records |
| Streamlit | Building the dashboards |
| Pytest | Testing parts of the analysis code |
| Git and GitHub | Version control and sharing the project |

## Running the project

Clone the repository and set up a Python environment.

```bash
git clone https://github.com/Don6974/t20-market-mispricing-ground.git
cd t20-market-mispricing-ground

python3 -m venv .venv
source .venv/bin/activate

python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m streamlit run app.py
```

The main app runs using simulated data and does not require the historical Betfair files.

To run the historical analysis, the original data and locally generated CSV and SQLite files are also required.

The research pipeline can then be run using:

```bash
python scripts/final_research_pipeline.py
```

By default, the script reads the local historical data under `~/Downloads/betfair_project2/t20_market_history` and saves its reports in the `research_outputs` folder.

### Historical quote input format

The trading demonstration can also accept a CSV containing probability estimates and betting quotes.

The required columns are:

| Column | Description |
| `match_id` | Match identifier |
| `decision_ts` | Time of the proposed decision |
| `quote_ts` | Time the quote was recorded |
| `selection` | Team or outcome being considered |
| `decimal_odds` | Available back odds supplied in the input |
| `model_probability` | Model's estimated chance of winning |
| `outcome` | Final result, used for evaluation |
| `source` | Source of the quote |
| `data_kind` | Synthetic or historical data label |

The app checks the input format and timing, but it cannot independently confirm that uploaded historical prices were actually available to bet on or that the model probabilities were generated without future information.

## Limitations and what I learned

The biggest challenge was making sure the historical data could support a fair comparison between cricket predictions and betting prices.

A few important limitations remain.

**Last-traded prices are not necessarily available betting odds.** They show the prices at which past trades occurred, but not whether I could have placed a new bet at those prices.

**Match identities still need verification.** Matching teams and dates helps identify possible fixtures, but it does not guarantee that every market has been linked correctly.

**Cricket events and market prices need accurate timing.** I cannot safely compare a model prediction after a wicket with a market price recorded before that wicket.

**A proper historical trading backtest has not yet been completed.** The project does not establish that a betting strategy would have made money.

These limitations helped me understand why data quality, timestamps and realistic execution assumptions matter just as much as the prediction model itself.

## Improvements needed

The next step would be to verify more of the market-to-match links and obtain reliable ball-event timestamps and historical back/lay quotes.

With that information, I could compare predictions from my first project against the market at the correct times.

I would then test a fixed strategy on matches kept separate from the data used to develop it, including commission and realistic execution assumptions.

For now, this project demonstrates **historical cricket market analysis, data processing, SQL, Python and research methodology**, rather than a proven profitable trading system.

## Data sources

- [Cricsheet](https://cricsheet.org/) — T20 match and ball-by-ball data
- [Betfair Historical Data](https://historicdata.betfair.com/) — Historical betting exchange market data

The original historical exchange data is not distributed with this repository.

**Author: Sugandhika Dontha**
