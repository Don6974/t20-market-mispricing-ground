
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime

BASE = Path.home() / "Downloads/betfair_project2"
INPUT = BASE / "t20_market_history/t20_candidate_ltp.csv"
OUTPUT = BASE / "t20_market_history/market_summary.csv"

markets = defaultdict(lambda: {
    "rows": 0,
    "inplay_rows": 0,
    "first_ts": None,
    "last_ts": None,
    "runners": set(),
    "prices": set(),
    "duplicate_rows": 0,
    "seen": set()
})

with INPUT.open(newline="") as f:
    reader = csv.DictReader(f)

    for row in reader:
        mid = row["market_id"]
        m = markets[mid]

        price = float(row["last_traded_price"])
        ts = datetime.fromisoformat(
            row["publish_time_utc"].replace("Z", "+00:00")
        )

        m["rows"] += 1
        if row["in_play"].lower() == "true":
            m["inplay_rows"] += 1

        m["first_ts"] = min(m["first_ts"], ts) if m["first_ts"] else ts
        m["last_ts"] = max(m["last_ts"], ts) if m["last_ts"] else ts

        m["runners"].add(row["runner_id"])
        m["prices"].add(price)

        key = (
            row["runner_id"],
            row["publish_time_utc"],
            row["last_traded_price"]
        )
        if key in m["seen"]:
            m["duplicate_rows"] += 1
        else:
            m["seen"].add(key)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "market_id", "rows", "inplay_rows",
        "runner_count", "unique_prices",
        "duplicate_rows", "first_ts", "last_ts"
    ])

    for mid, m in sorted(markets.items()):
        writer.writerow([
            mid,
            m["rows"],
            m["inplay_rows"],
            len(m["runners"]),
            len(m["prices"]),
            m["duplicate_rows"],
            m["first_ts"].isoformat(),
            m["last_ts"].isoformat()
        ])

print("MARKET PRICE ANALYSIS")
print("Markets analysed:", len(markets))
print("Markets with in-play prices:",
      sum(m["inplay_rows"] > 0 for m in markets.values()))
print("Markets with both runners:",
      sum(len(m["runners"]) == 2 for m in markets.values()))
print("Potential duplicate rows:",
      sum(m["duplicate_rows"] for m in markets.values()))
print("Summary saved to:", OUTPUT)
