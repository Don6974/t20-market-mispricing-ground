
import csv
import sqlite3
from pathlib import Path
from collections import defaultdict

BASE = Path.home() / "Downloads/betfair_project2/t20_market_history"

DB = BASE / "price_analysis.sqlite"
QUALITY = BASE / "market_quality_shortlist.csv"
OUTPUT = BASE / "annual_market_statistics.csv"

# Only include structurally complete markets.
with QUALITY.open(newline="") as f:
    rows = list(csv.DictReader(f))

eligible = {
    r["market_id"]: r["market_time_utc"][:4]
    for r in rows
    if r["quality_status"] == "review_candidate"
}

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

counts = dict(con.execute("""
    SELECT market_id, COUNT(DISTINCT runner_id)
    FROM prices
    GROUP BY market_id
"""))

eligible = {
    market_id: year
    for market_id, year in eligible.items()
    if counts.get(market_id) == 2
}

stats = defaultdict(lambda: {
    "markets": set(),
    "runner_histories": 0,
    "observations": 0,
    "price_changes": 0
})

for mid, rid, n, price_changes in con.execute("""
    WITH dedup AS (
        SELECT DISTINCT
            market_id, runner_id, timestamp, price
        FROM prices
    ),
    movements AS (
        SELECT
            market_id,
            runner_id,
            price,
            LAG(price) OVER (
                PARTITION BY market_id, runner_id
                ORDER BY timestamp
            ) AS previous_price
        FROM dedup
    )
    SELECT
        market_id,
        runner_id,
        COUNT(*) AS observations,
        SUM(
            CASE
                WHEN previous_price IS NOT NULL
                     AND price != previous_price
                THEN 1 ELSE 0
            END
        ) AS price_changes
    FROM movements
    GROUP BY market_id, runner_id
"""):
    if mid not in eligible:
        continue

    year = eligible[mid]
    s = stats[year]
    s["markets"].add(mid)
    s["runner_histories"] += 1
    s["observations"] += n
    s["price_changes"] += price_changes or 0

con.close()

with OUTPUT.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "year", "markets", "runner_histories",
        "observations", "price_changes"
    ])

    for year, s in sorted(stats.items()):
        writer.writerow([
            year,
            len(s["markets"]),
            s["runner_histories"],
            s["observations"],
            s["price_changes"]
        ])

print("\nANNUAL HISTORICAL MARKET STATISTICS")

for year, s in sorted(stats.items()):
    print(
        year,
        "Markets:", len(s["markets"]),
        "Observations:", s["observations"],
        "Price changes:", s["price_changes"]
    )

print("\nSaved:", OUTPUT)
