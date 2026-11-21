
import csv
from pathlib import Path
from collections import Counter

base = Path.home() / "Downloads/betfair_project2"
history = base / "t20_market_history"

identity_file = (
    base / "t20_identity_review/market_identity_review.csv"
)
summary_file = history / "market_summary.csv"
output_file = history / "market_quality_shortlist.csv"

with identity_file.open(newline="") as f:
    identities = {
        row["market_id"]: row
        for row in csv.DictReader(f)
        if row["status"] == "exact_name_date_candidate"
    }

results = []
stats = Counter()
years = Counter()

with summary_file.open(newline="") as f:
    for row in csv.DictReader(f):
        market_id = row["market_id"]
        identity = identities.get(market_id)

        if identity is None:
            continue

        two_runners = int(row["runner_count"]) == 2
        has_inplay = int(row["inplay_rows"]) > 0

        if two_runners and has_inplay:
            status = "review_candidate"
            years[identity["market_time_utc"][:4]] += 1
        elif not two_runners:
            status = "runner_count_issue"
        else:
            status = "no_inplay_prices"

        stats[status] += 1

        results.append({
            **identity,
            **row,
            "quality_status": status
        })

if results:
    with output_file.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(results[0].keys())
        )
        writer.writeheader()
        writer.writerows(results)

print("\nMARKET QUALITY AUDIT")
print("Markets reviewed:", len(results))
print("Quality classifications:", dict(stats))

print("\nREVIEW CANDIDATES BY YEAR")
for year, count in sorted(years.items()):
    print(year, count)

print("\nOutput:", output_file)
