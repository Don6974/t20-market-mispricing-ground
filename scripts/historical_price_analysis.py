
import csv
import sqlite3
from pathlib import Path

base = Path.home() / "Downloads/betfair_project2/t20_market_history"
db_path = base / "price_analysis.sqlite"
prices_path = base / "t20_candidate_ltp.csv"
quality_path = base / "market_quality_shortlist.csv"
output_path = base / "historical_price_summary.csv"

with quality_path.open(newline="") as f:
    eligible = {
        r["market_id"]
        for r in csv.DictReader(f)
        if r["quality_status"] == "review_candidate"
    }

con = sqlite3.connect(db_path)
con.execute("DROP TABLE IF EXISTS prices")
con.execute("""
CREATE TABLE prices (
    market_id TEXT,
    runner_id TEXT,
    timestamp TEXT,
    price REAL,
    in_play INTEGER,
    market_status TEXT
)
""")

batch = []
with prices_path.open(newline="") as f:
    for r in csv.DictReader(f):
        if r["market_id"] not in eligible:
            continue
        if r["in_play"].lower() != "true":
            continue
        if r["market_status"] != "OPEN":
            continue

        batch.append((
            r["market_id"],
            r["runner_id"],
            r["publish_time_utc"],
            float(r["last_traded_price"]),
            1,
            r["market_status"]
        ))

        if len(batch) >= 10000:
            con.executemany(
                "INSERT INTO prices VALUES (?,?,?,?,?,?)", batch
            )
            batch.clear()

if batch:
    con.executemany(
        "INSERT INTO prices VALUES (?,?,?,?,?,?)", batch
    )

con.commit()

# Remove exact duplicate observations without
# discarding different prices at the same timestamp.
con.execute("""
DELETE FROM prices
WHERE rowid NOT IN (
    SELECT MIN(rowid)
    FROM prices
    GROUP BY market_id, runner_id, timestamp, price
)
""")
con.commit()

# Different prices at the same timestamp are ambiguous.
conflicts = con.execute("""
SELECT COUNT(*)
FROM (
    SELECT market_id, runner_id, timestamp
    FROM prices
    GROUP BY market_id, runner_id, timestamp
    HAVING COUNT(DISTINCT price) > 1
)
""").fetchone()[0]

query = """
SELECT market_id, runner_id, timestamp, price
FROM prices
WHERE (market_id, runner_id, timestamp) NOT IN (
    SELECT market_id, runner_id, timestamp
    FROM prices
    GROUP BY market_id, runner_id, timestamp
    HAVING COUNT(DISTINCT price) > 1
)
ORDER BY market_id, runner_id, timestamp
"""

summary = []
previous_key = None
previous_price = None
current = None

for mid, rid, timestamp, price in con.execute(query):
    key = (mid, rid)

    if key != previous_key:
        if current is not None:
            summary.append(current)

        current = {
            "market_id": mid,
            "runner_id": rid,
            "observations": 0,
            "price_changes": 0,
            "first_price": price,
            "last_price": price,
            "min_price": price,
            "max_price": price
        }
        previous_price = None

    current["observations"] += 1

    if previous_price is not None and price != previous_price:
        current["price_changes"] += 1

    current["last_price"] = price
    current["min_price"] = min(current["min_price"], price)
    current["max_price"] = max(current["max_price"], price)

    previous_key = key
    previous_price = price

if current is not None:
    summary.append(current)

fields = [
    "market_id", "runner_id", "observations",
    "price_changes", "first_price", "last_price",
    "min_price", "max_price"
]

with output_path.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(summary)

con.close()

print("\nHISTORICAL T20 PRICE ANALYSIS")
print("Eligible candidate markets:", len(eligible))
print("Runner histories analysed:", len(summary))
print("Markets represented:",
      len({r["market_id"] for r in summary}))
print("Runner histories with 10+ observations:",
      sum(r["observations"] >= 10 for r in summary))
print("Runner histories with price changes:",
      sum(r["price_changes"] > 0 for r in summary))
print("Conflicting market-runner timestamps:", conflicts)
print("Output:", output_path)
