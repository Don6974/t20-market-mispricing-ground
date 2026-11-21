
import csv
import sqlite3
from pathlib import Path
from collections import Counter

base = Path.home() / "Downloads/betfair_project2/t20_market_history"

quality_file = base / "market_quality_shortlist.csv"
db_file = base / "price_analysis.sqlite"
output_file = base / "market_completeness_issues.csv"

with quality_file.open(newline="") as f:
    eligible = {
        row["market_id"]
        for row in csv.DictReader(f)
        if row["quality_status"] == "review_candidate"
    }

con = sqlite3.connect(db_file)

runner_counts = dict(con.execute("""
    SELECT market_id, COUNT(DISTINCT runner_id)
    FROM prices
    GROUP BY market_id
"""))

issues = []

for market_id in sorted(eligible):
    count = runner_counts.get(market_id, 0)

    if count != 2:
        issues.append({
            "market_id": market_id,
            "observed_runners": count,
            "issue": (
                "no_eligible_price_rows"
                if count == 0
                else "incomplete_runner_coverage"
            )
        })

con.close()

with output_file.open("w", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "market_id",
            "observed_runners",
            "issue"
        ]
    )
    writer.writeheader()
    writer.writerows(issues)

print("\nMARKET COMPLETENESS AUDIT")
print("Eligible markets:", len(eligible))
print("Markets with two runner histories:",
      sum(runner_counts.get(m, 0) == 2 for m in eligible))
print("Markets requiring review:", len(issues))
print("Issue breakdown:",
      dict(Counter(r["issue"] for r in issues)))
print("Saved:", output_file)
