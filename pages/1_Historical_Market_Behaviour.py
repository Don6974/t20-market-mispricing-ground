
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

BASE = (
    Path.home()
    / "Downloads/betfair_project2/t20_market_history"
)
DB = BASE / "price_analysis.sqlite"
QUALITY = BASE / "market_quality_shortlist.csv"
HISTORIES = BASE / "historical_price_summary.csv"

st.set_page_config(
    page_title="Historical T20 Market Behaviour",
    layout="wide"
)
st.title("Historical T20 Market Behaviour")
st.caption("Betfair historical last-traded prices | 2021–2026")
st.warning(
    "Research only. Match identities remain candidate links. "
    "Last-traded prices are not guaranteed executable odds."
)

missing = [
    str(p) for p in (DB, QUALITY, HISTORIES)
    if not p.is_file()
]
if missing:
    st.info("Local licensed research data are not installed on this machine. "        "The public app contains a synthetic demo; historical research is local-only. "        "Missing paths: " + ", ".join(missing))
    st.stop()


@st.cache_data
def load_catalogue():
    q = pd.read_csv(QUALITY, dtype={"market_id": str})
    h = pd.read_csv(HISTORIES, dtype={
        "market_id": str,
        "runner_id": str
    })

    # Both runners must have histories in the
    # cleaned, in-play, OPEN-market database.
    complete = (
        h.groupby("market_id")["runner_id"]
        .nunique()
    )
    ids = set(complete[complete == 2].index)

    q = q[
        (q["quality_status"] == "review_candidate")
        & q["market_id"].isin(ids)
    ].copy()

    q["year"] = q["market_time_utc"].str[:4]
    return q.sort_values("market_time_utc")


@st.cache_data(show_spinner="Reading historical prices...")
def load_prices(market_id):
    with sqlite3.connect(
        f"file:{DB}?mode=ro",
        uri=True
    ) as con:
        df = pd.read_sql_query(
            """
            SELECT runner_id, timestamp, price
            FROM prices
            WHERE market_id = ?
            """,
            con,
            params=(market_id,)
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"], utc=True
    )
    df = df.sort_values("timestamp")
    df["implied_probability"] = 1 / df["price"]
    return df


catalogue = load_catalogue()

st.subheader("Historical dataset")

c1, c2, c3 = st.columns(3)
c1.metric("Markets with two runner histories", len(catalogue))
c2.metric("Historical years", catalogue["year"].nunique())
c3.metric("Data source", "Betfair Basic LTP")

st.bar_chart(
    catalogue.groupby("year").size().rename("Markets")
)

st.subheader("Explore a historical match")

selected_id = st.selectbox(
    "Select market",
    catalogue["market_id"].tolist(),
    format_func=lambda mid: (
        f"{catalogue.loc[catalogue.market_id == mid, 'event_name'].iloc[0]}"
        f" ({mid})"
    )
)

prices = load_prices(selected_id)
info = catalogue[
    catalogue.market_id == selected_id
].iloc[0]

st.write("**Event:**", info["event_name"])
st.write("**Recorded start:**", info["market_time_utc"])
st.write("**Observations:**", f"{len(prices):,}")

if prices.empty:
    st.info("No eligible price observations.")
    st.stop()

st.subheader("Historical last-traded odds")

odds = prices.pivot_table(
    index="timestamp",
    columns="runner_id",
    values="price",
    aggfunc="last"
)
st.line_chart(odds)

st.subheader("Raw implied probability (%)")

probabilities = (1 / odds) * 100
st.line_chart(probabilities)

st.caption(
    "A missing observation is not a quoted price. "
    "The chart does not forward-fill runner prices."
)

st.subheader("Runner statistics")

stats = prices.groupby("runner_id").agg(
    observations=("price", "size"),
    first_price=("price", "first"),
    last_price=("price", "last"),
    min_price=("price", "min"),
    max_price=("price", "max")
)

st.dataframe(stats, use_container_width=True)

with st.expander("Historical records"):
    st.dataframe(
        prices.tail(100),
        use_container_width=True
    )

st.download_button(
    "Download selected market observations",
    prices.to_csv(index=False),
    file_name=f"market_{selected_id}.csv",
    mime="text/csv"
)

# Historical market movement diagnostics
st.divider()
st.subheader("Market Movement & Data Quality")

diagnostics = []

for runner_id, group in prices.groupby("runner_id"):
    group = group.sort_values("timestamp").copy()

    original_rows = len(group)

    # Remove identical repeated observations.
    group = group.drop_duplicates(
        subset=["timestamp", "price"]
    )

    # One runner must not have conflicting prices
    # at the same publish timestamp.
    conflicts = group.groupby("timestamp")["price"].nunique()
    conflicting_times = int((conflicts > 1).sum())

    group = group[
        ~group["timestamp"].isin(
            conflicts[conflicts > 1].index
        )
    ].copy()

    if group.empty:
        continue

    group = group.sort_values("timestamp")
    group["implied_p"] = 100 / group["price"]
    group["gap_seconds"] = (
        group["timestamp"].diff().dt.total_seconds()
    )

    changes = group["price"].diff().ne(0)
    changes.iloc[0] = False

    gaps = group["gap_seconds"].dropna()

    diagnostics.append({
        "runner_id": str(runner_id),
        "valid_observations": len(group),
        "exact_duplicates_removed": (
            original_rows
            - len(group)
        ),
        "conflicting_timestamps": conflicting_times,
        "recorded_price_changes": int(changes.sum()),
        "median_gap_seconds": (
            round(float(gaps.median()), 1)
            if not gaps.empty else None
        ),
        "p95_gap_seconds": (
            round(float(gaps.quantile(0.95)), 1)
            if not gaps.empty else None
        ),
        "max_gap_seconds": (
            round(float(gaps.max()), 1)
            if not gaps.empty else None
        ),
        "implied_probability_range_pp": round(
            float(
                group["implied_p"].max()
                - group["implied_p"].min()
            ), 2
        )
    })

diagnostics_df = pd.DataFrame(diagnostics)

st.dataframe(
    diagnostics_df,
    use_container_width=True,
    hide_index=True
)

if not diagnostics_df.empty:
    st.caption(
        "Probability range is descriptive, not a "
        "trading edge. Timestamp gaps measure gaps "
        "between recorded LTP updates, not periods "
        "when a market was continuously available."
    )

st.divider()
st.subheader("2021–2026 Historical Market Analysis")

annual_file = (
    BASE / "annual_market_statistics.csv"
)

if annual_file.exists():
    annual = pd.read_csv(annual_file)
    annual["year"] = annual["year"].astype(str)

    col1, col2 = st.columns(2)

    with col1:
        st.write("Markets by year")
        st.bar_chart(
            annual.set_index("year")["markets"]
        )

    with col2:
        st.write("Recorded LTP observations by year")
        st.bar_chart(
            annual.set_index("year")["observations"]
        )

    st.dataframe(
        annual,
        hide_index=True,
        use_container_width=True
    )

    st.caption(
        "Coverage reflects available historical "
        "data and candidate market selection, "
        "not actual betting activity or profit."
    )
else:
    st.info("Annual statistics CSV not found.")
