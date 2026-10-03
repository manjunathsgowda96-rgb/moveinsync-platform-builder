import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="MoveInSync Operations Control Tower",
    page_icon="🚦",
    layout="wide"
)

st.markdown("""
<style>
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}
[data-testid="stMetricValue"] {
    font-size: 1.8rem;
}
.small {
    font-size: 0.85rem;
    color: #666;
}
</style>
""", unsafe_allow_html=True)

st.title("MoveInSync Operations Control Tower")
st.caption("MVP • Managed fleet (Site Type = O) • Historical operational view")

uploaded = st.file_uploader(
    "Upload Fleet-CaseStudy-Data.xlsx",
    type=["xlsx"]
)

if uploaded is None:
    st.info(
        "Upload the case-study Excel file to load the control tower. "
        "The file is processed in the app session and is not included in the application code."
    )
    st.stop()


@st.cache_data
def load_data(file):
    d = pd.read_excel(file)

    # Date/time fields
    for c in [
        "Start Time",
        "End Time",
        "Planned Start",
        "Planned End",
        "Base Date"
    ]:
        if c in d.columns:
            d[c] = pd.to_datetime(d[c], errors="coerce")

    # Delay calculations
    d["Start Delay Min"] = (
        d["Start Time"] - d["Planned Start"]
    ).dt.total_seconds() / 60

    d["End Delay Min"] = (
        d["End Time"] - d["Planned End"]
    ).dt.total_seconds() / 60

    d["Positive Start Delay"] = d["Start Delay Min"].clip(lower=0)
    d["Positive End Delay"] = d["End Delay Min"].clip(lower=0)

    # SLA / delay flags
    d["Start Breach"] = d["Start Delay Min"] > 10
    d["End Breach"] = d["End Delay Min"] > 10

    d["Any Delay"] = (
        (d["Start Delay Min"] > 0)
        | (d["End Delay Min"] > 0)
    )

    d["No Delay"] = ~d["Any Delay"]

    # Start-delay severity
    d["Start >10"] = d["Start Delay Min"] > 10
    d["Start >20"] = d["Start Delay Min"] > 20
    d["Start >30"] = d["Start Delay Min"] > 30

    # Overall/end-delay severity
    d["Overall >10"] = d["Positive End Delay"] > 10
    d["Overall >20"] = d["Positive End Delay"] > 20
    d["Overall >30"] = d["Positive End Delay"] > 30

    # Identify site from landmark
    residential_start = (
        d["Event Start Landmark"]
        .astype(str)
        .str.startswith("Residential Cluster")
    )

    d["Site"] = np.where(
        residential_start,
        d["Event End Landmark"],
        d["Event Start Landmark"]
    )

    d["Site"] = d["Site"].where(
        ~d["Site"].astype(str).str.startswith("Residential Cluster"),
        np.nan
    )

    d["Direction"] = np.where(
        residential_start,
        "Home → Site",
        "Site → Home"
    )

    d["Route Key"] = (
        d["Site"].astype(str)
        + " | "
        + d["Direction"].astype(str)
    )

    # Occupancy
    d["Occupancy %"] = np.where(
        d["Cab Capacity"] > 0,
        d["Employee Count"] / d["Cab Capacity"],
        np.nan
    )

    return d


df = load_data(uploaded)

# --------------------------------------------------
# Scope: MoveInSync-operated fleet only
# --------------------------------------------------

scope = df[df["Site Type"].eq("O")].copy()

# MVP thresholds
START_THRESHOLD = 10
END_THRESHOLD = 10
WATCH_THRESHOLD = 20
ATTENTION_THRESHOLD = 30


# ==================================================
# GLOBAL FILTERS
# ==================================================

st.sidebar.header("Control tower filters")

min_date = scope["Base Date"].min().date()
max_date = scope["Base Date"].max().date()

selected_dates = st.sidebar.slider(
    "Date range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    format="DD MMM YYYY"
)

sites = sorted(scope["Site"].dropna().unique())

selected_sites = st.sidebar.multiselect(
    "Site",
    sites
)

vendors = sorted(scope["Vendor"].dropna().unique())

selected_vendors = st.sidebar.multiselect(
    "Vendor",
    vendors
)

# Apply global filters
f = scope[
    (scope["Base Date"].dt.date >= selected_dates[0])
    & (scope["Base Date"].dt.date <= selected_dates[1])
].copy()

if selected_sites:
    f = f[f["Site"].isin(selected_sites)]

if selected_vendors:
    f = f[f["Vendor"].isin(selected_vendors)]


# ==================================================
# CITY HEALTH
# ==================================================

st.subheader("City health")

total_city_sites = df["Site"].nunique()
managed_sites = scope["Site"].nunique()

trips = len(f)

no_delay_n = int(f["No Delay"].sum()) if trips else 0
any_delay_n = int(f["Any Delay"].sum()) if trips else 0
start_late_n = int(f["Start Delay Min"].gt(0).sum()) if trips else 0

avg_start_delay = (
    f["Positive Start Delay"].mean()
    if trips else 0
)

avg_total_delay = (
    f["Positive End Delay"].mean()
    if trips else 0
)

occupancy = (
    f["Occupancy %"].mean()
    if trips else 0
)


# --------------------------------------------------
# ROW 1 — Overall Operations
# --------------------------------------------------

r1 = st.columns(6)

r1[0].metric(
    "Managed sites",
    f"{managed_sites}/{total_city_sites}"
)

r1[1].metric(
    "Trips",
    f"{trips:,}"
)

r1[2].metric(
    "No-delay rides",
    f"{no_delay_n:,}"
)
r1[2].caption(f"{no_delay_n / trips:.1%} of rides" if trips else "—")

r1[3].metric(
    "Rides with delay",
    f"{any_delay_n:,}"
)
r1[3].caption(f"{any_delay_n / trips:.1%} of rides" if trips else "—")

r1[4].metric(
    "Started late",
    f"{start_late_n:,}"
)
r1[4].caption(f"{start_late_n / trips:.1%} of rides" if trips else "—")

r1[5].metric(
    "Avg occupancy",
    f"{occupancy:.1%}" if pd.notna(occupancy) else "—"
)


# --------------------------------------------------
# ROW 2 — Overall Delay
# --------------------------------------------------

st.markdown("##### Overall delay")

r2 = st.columns(4)

r2[0].metric(
    "Avg total delay",
    f"{avg_total_delay:.1f} min"
)

r2[1].metric(
    "Overall delay >10 min",
    f"{int(f['Overall >10'].sum()):,}"
)
r2[1].caption(f"{f['Overall >10'].mean():.1%} of rides" if trips else "—")

r2[2].metric(
    "Overall delay >20 min",
    f"{int(f['Overall >20'].sum()):,}"
)
r2[2].caption(f"{f['Overall >20'].mean():.1%} of rides" if trips else "—")

r2[3].metric(
    "Overall delay >30 min",
    f"{int(f['Overall >30'].sum()):,}"
)
r2[3].caption(f"{f['Overall >30'].mean():.1%} of rides" if trips else "—")


# --------------------------------------------------
# ROW 3 — Start Delay
# --------------------------------------------------

st.markdown("##### Start delay")

r3 = st.columns(4)

r3[0].metric(
    "Avg start delay",
    f"{avg_start_delay:.1f} min"
)

r3[1].metric(
    "Start delay >10 min",
    f"{int(f['Start >10'].sum()):,}"
)
r3[1].caption(f"{f['Start >10'].mean():.1%} of rides" if trips else "—")

r3[2].metric(
    "Start delay >20 min",
    f"{int(f['Start >20'].sum()):,}"
)
r3[2].caption(f"{f['Start >20'].mean():.1%} of rides" if trips else "—")

r3[3].metric(
    "Start delay >30 min",
    f"{int(f['Start >30'].sum()):,}"
)
r3[3].caption(f"{f['Start >30'].mean():.1%} of rides" if trips else "—")

st.caption(
    f"Coverage: {selected_dates[0].strftime('%d %b %Y')} – "
    f"{selected_dates[1].strftime('%d %b %Y')} • "
    f"Scope: managed fleet (Site Type = O)"
)

st.divider()

# ==================================================
# SITE HEALTH
# ==================================================

st.subheader("Site health")

site = (
    f.groupby("Site", dropna=True)
    .agg(
        Trips=("Cab ID", "size"),
        Cabs=("Cab ID", "nunique"),
        Vendors=("Vendor", "nunique"),
        Start_Breach=("Start Breach", "mean"),
        End_Breach=("End Breach", "mean"),
        Avg_Start_Delay=("Positive Start Delay", "mean"),
        Avg_Trip_Delay=("Positive End Delay", "mean"),
        Occupancy=("Occupancy %", "mean"),
        Start_10=("Start >10", "mean"),
        Start_20=("Start >20", "mean"),
        Start_30=("Start >30", "mean"),
        Overall_10=("Overall >10", "mean"),
        Overall_20=("Overall >20", "mean"),
        Overall_30=("Overall >30", "mean"),
    )
    .reset_index()
)

# Site status
site["Status"] = np.select(
    [
        site["End_Breach"] > ATTENTION_THRESHOLD / 100,
        site["End_Breach"] > WATCH_THRESHOLD / 100
    ],
    [
        "🔴 Attention",
        "🟠 Watch"
    ],
    default="🟢 Healthy"
)

site = site.sort_values(
    ["End_Breach", "Trips"],
    ascending=[False, False]
)

display = site.rename(
    columns={
        "Start_Breach": "Start SLA breach",
        "End_Breach": "End SLA breach",
        "Avg_Start_Delay": "Avg start delay (min)",
        "Avg_Trip_Delay": "Avg total delay (min)",
        "Occupancy": "Occupancy %",
        "Start_10": "Start >10 min",
        "Start_20": "Start >20 min",
        "Start_30": "Start >30 min",
        "Overall_10": "Overall >10 min",
        "Overall_20": "Overall >20 min",
        "Overall_30": "Overall >30 min",
    }
).copy()

percentage_columns = [
    "Start SLA breach",
    "End SLA breach",
    "Occupancy %",
    "Start >10 min",
    "Start >20 min",
    "Start >30 min",
    "Overall >10 min",
    "Overall >20 min",
    "Overall >30 min",
]

for c in percentage_columns:
    display[c] = display[c].map(
        lambda x: f"{x:.1%}"
    )

for c in [
    "Avg start delay (min)",
    "Avg total delay (min)"
]:
    display[c] = display[c].round(1)

st.dataframe(
    display[
        [
            "Status",
            "Site",
            "Trips",
            "Cabs",
            "Vendors",
            "Occupancy %",
            "Start SLA breach",
            "End SLA breach",
            "Avg start delay (min)",
            "Avg total delay (min)",
            "Start >10 min",
            "Start >20 min",
            "Start >30 min",
            "Overall >10 min",
            "Overall >20 min",
            "Overall >30 min",
        ]
    ],
    use_container_width=True,
    hide_index=True
)

st.caption(
    f"Site status uses End SLA breach rate: "
    f"🟢 Healthy ≤ {WATCH_THRESHOLD}% • "
    f"🟠 Watch > {WATCH_THRESHOLD}% to {ATTENTION_THRESHOLD}% • "
    f"🔴 Attention > {ATTENTION_THRESHOLD}%. "
    f"10-minute SLA breach is an MVP assumption."
)

st.divider()


# ==================================================
# EXCEPTION QUEUE + LATE RISK
# ==================================================

st.subheader("Exception Queue")

# Build historical risk signals on ALL filtered rides first.
# Then show only delayed rides in the exception queue.
history_df = f.copy()

if len(history_df) == 0:
    st.info("No rides match the selected filters.")
else:

    # --------------------------------------------------
    # TIME BUCKET
    # --------------------------------------------------

    def get_time_bucket(dt):
        if pd.isna(dt):
            return "Unknown"

        hour = dt.hour

        if 5 <= hour < 12:
            return "Morning"
        elif 12 <= hour < 17:
            return "Afternoon"
        elif 17 <= hour < 21:
            return "Evening"
        else:
            return "Night"

    history_df["Time Bucket"] = (
        history_df["Planned Start"].apply(get_time_bucket)
    )

    # --------------------------------------------------
    # SORT CHRONOLOGICALLY
    # --------------------------------------------------

    history_df = history_df.sort_values("Start Time").copy()

    # --------------------------------------------------
    # CAB + SITE + DIRECTION HISTORY
    # Previous 10 comparable rides
    # --------------------------------------------------

    history_df["Cab Route Late Rate"] = (
        history_df
        .groupby(["Cab ID", "Site", "Direction"])["End Breach"]
        .transform(
            lambda x: x.shift(1).rolling(
                10,
                min_periods=3
            ).mean()
        )
    )

    # --------------------------------------------------
    # SITE + DIRECTION HISTORY
    # Previous 10 comparable rides
    # --------------------------------------------------

    history_df["Site Late Rate"] = (
        history_df
        .groupby(["Site", "Direction"])["End Breach"]
        .transform(
            lambda x: x.shift(1).rolling(
                10,
                min_periods=3
            ).mean()
        )
    )

    # --------------------------------------------------
    # TIME-OF-DAY HISTORY
    # Previous 20 rides in same time bucket
    # --------------------------------------------------

    history_df["Time Bucket Late Rate"] = (
        history_df
        .groupby("Time Bucket")["End Breach"]
        .transform(
            lambda x: x.shift(1).rolling(
                20,
                min_periods=5
            ).mean()
        )
    )

    # No historical evidence = neutral score
    history_df["Cab Route Late Rate"] = (
        history_df["Cab Route Late Rate"].fillna(0)
    )

    history_df["Site Late Rate"] = (
        history_df["Site Late Rate"].fillna(0)
    )

    history_df["Time Bucket Late Rate"] = (
        history_df["Time Bucket Late Rate"].fillna(0)
    )

    # --------------------------------------------------
    # CURRENT START DELAY COMPONENT
    # 0 min = 0 score; 30+ min = 100 score
    # --------------------------------------------------

    history_df["Start Delay Component"] = (
        history_df["Positive Start Delay"]
        .clip(0, 30)
        / 30
        * 100
    )

    # --------------------------------------------------
    # HISTORICAL COMPONENTS
    # --------------------------------------------------

    history_df["History Component"] = (
        history_df["Cab Route Late Rate"] * 100
    )

    history_df["Route Component"] = (
        history_df["Site Late Rate"] * 100
    )

    history_df["Time Component"] = (
        history_df["Time Bucket Late Rate"] * 100
    )

    # --------------------------------------------------
    # FINAL LATE RISK SCORE
    #
    # 40% current start delay
    # 30% cab + route history
    # 20% site + direction history
    # 10% time-of-day history
    # --------------------------------------------------

    history_df["Late Risk Score"] = (
        0.40 * history_df["Start Delay Component"]
        + 0.30 * history_df["History Component"]
        + 0.20 * history_df["Route Component"]
        + 0.10 * history_df["Time Component"]
    ).clip(0, 100).round(0)

    # --------------------------------------------------
    # RISK LEVEL
    # --------------------------------------------------

    history_df["Risk"] = np.select(
        [
            history_df["Late Risk Score"] >= 70,
            history_df["Late Risk Score"] >= 40
        ],
        [
            "High",
            "Medium"
        ],
        default="Low"
    )

    # --------------------------------------------------
    # ONLY DELAYED RIDES ENTER THE EXCEPTION QUEUE
    # --------------------------------------------------

    exceptions = history_df[
        history_df["Any Delay"]
    ].copy()

    if len(exceptions) == 0:
        st.success("No delayed rides in the selected period.")

    else:

        # --------------------------------------------------
        # REASON FOR EXCEPTION
        # --------------------------------------------------

        def get_reason(row):

            if row["Positive Start Delay"] > 10:
                return "Started late"

            if row["Cab Route Late Rate"] >= 0.5:
                return "Cab frequently late on this route"

            if row["Site Late Rate"] >= 0.5:
                return "Site / route has frequent delays"

            if row["Time Bucket Late Rate"] >= 0.5:
                return "High-delay time period"

            return "Late trip"

        exceptions["Reason"] = exceptions.apply(
            get_reason,
            axis=1
        )

        # --------------------------------------------------
        # OWNER
        # --------------------------------------------------

        exceptions["Owner"] = "City Ops"

        # --------------------------------------------------
        # ACTION
        # --------------------------------------------------

        def get_action(row):

            if row["Positive Start Delay"] > 10:
                return "Contact driver / dispatch"

            if row["Cab Route Late Rate"] >= 0.5:
                return "Investigate cab / vendor"

            if row["Site Late Rate"] >= 0.5:
                return "Review site-route issue"

            if row["Time Bucket Late Rate"] >= 0.5:
                return "Monitor upcoming trips"

            return "Review trip"

        exceptions["Action"] = exceptions.apply(
            get_action,
            axis=1
        )

        # --------------------------------------------------
        # SORT BY RISK
        # --------------------------------------------------

        exceptions = exceptions.sort_values(
            ["Late Risk Score", "Positive End Delay"],
            ascending=[False, False]
        )

        # --------------------------------------------------
        # EXCEPTION FILTERS
        # --------------------------------------------------

        st.markdown("##### Filter exceptions")

        filter_col1, filter_col2, filter_col3 = st.columns(3)

        with filter_col1:
            risk_filter = st.selectbox(
                "Risk",
                ["All", "High", "Medium", "Low"],
                key="exception_risk_filter"
            )

        with filter_col2:
            reason_options = [
                "All",
                "Started late",
                "Cab frequently late on this route",
                "Site / route has frequent delays",
                "High-delay time period",
                "Late trip"
            ]

            reason_filter = st.selectbox(
                "Reason",
                reason_options,
                key="exception_reason_filter"
            )

        with filter_col3:
            owner_filter = st.selectbox(
                "Owner",
                ["All"] + sorted(
                    exceptions["Owner"].dropna().unique().tolist()
                ),
                key="exception_owner_filter"
            )

        if risk_filter != "All":
            exceptions = exceptions[
                exceptions["Risk"] == risk_filter
            ]

        if reason_filter != "All":
            exceptions = exceptions[
                exceptions["Reason"] == reason_filter
            ]

        if owner_filter != "All":
            exceptions = exceptions[
                exceptions["Owner"] == owner_filter
            ]

        st.caption(
            "Prioritize High-risk trips first. Each exception includes an "
            "owner and recommended next action."
        )

        # --------------------------------------------------
        # DISPLAY TABLE
        # --------------------------------------------------

        exception_display = exceptions[
            [
                "Site",
                "Cab ID",
                "Vendor",
                "Duty Num",
                "Direction",
                "Start Time",
                "Planned Start",
                "End Time",
                "Planned End",
                "Positive Start Delay",
                "Positive End Delay",
                "Late Risk Score",
                "Risk",
                "Reason",
                "Owner",
                "Action"
            ]
        ].copy()

        exception_display = exception_display.rename(
            columns={
                "Cab ID": "Cab",
                "Duty Num": "Duty",
                "Positive Start Delay": "Start Delay (min)",
                "Positive End Delay": "End Delay (min)",
                "Late Risk Score": "Risk Score"
            }
        )

        st.dataframe(
            exception_display,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "Late Risk Score is an MVP heuristic, not a validated probability. "
            "Historical signals use only rides occurring before the current ride."
        )

st.divider()

# ==================================================
# MVP SCOPE & DATA GAPS
# ==================================================

with st.expander("MVP scope & data gaps"):
    st.markdown(
        """
        **MVP scope:** Managed fleet only (`Site Type = O`).

        **Not evaluated in this MVP because the supplied dataset does not
        contain the required fields:** vehicle-document compliance,
        live vehicle availability / offline status, and operator economics
        such as earning, revenue or contract terms.

        **Late Risk Score:** Historical heuristic using current start delay,
        prior cab-route performance, prior site-direction performance and
        time-of-day performance. It is not a validated probability model.
        """
    )

st.divider()


# ==================================================
# VENDOR SERVICE PERFORMANCE
# ==================================================

st.subheader("Vendor service performance")

vf = f.copy()

v = (
    vf.groupby("Vendor")
    .agg(
        Trips=("Cab ID", "size"),
        Cabs=("Cab ID", "nunique"),
        Occupancy=("Occupancy %", "mean"),
        Start_Breach=("Start Breach", "mean"),
        End_Breach=("End Breach", "mean"),
        Avg_Start_Delay=("Positive Start Delay", "mean"),
        Avg_End_Delay=("Positive End Delay", "mean"),
        Start_10=("Start >10", "mean"),
        Start_20=("Start >20", "mean"),
        Start_30=("Start >30", "mean"),
        Overall_10=("Overall >10", "mean"),
        Overall_20=("Overall >20", "mean"),
        Overall_30=("Overall >30", "mean"),
    )
    .reset_index()
)

v["Status"] = np.select(
    [
        v["End_Breach"] > ATTENTION_THRESHOLD / 100,
        v["End_Breach"] > WATCH_THRESHOLD / 100
    ],
    [
        "🔴 Attention",
        "🟠 Watch"
    ],
    default="🟢 Healthy"
)

v = v.sort_values(
    "End_Breach",
    ascending=False
)

v["Start SLA breach"] = v["Start_Breach"].map(
    lambda x: f"{x:.1%}"
)

v["End SLA breach"] = v["End_Breach"].map(
    lambda x: f"{x:.1%}"
)

v["Occupancy %"] = v["Occupancy"].map(
    lambda x: f"{x:.1%}"
)

v["Start >10 min"] = v["Start_10"].map(
    lambda x: f"{x:.1%}"
)

v["Start >20 min"] = v["Start_20"].map(
    lambda x: f"{x:.1%}"
)

v["Start >30 min"] = v["Start_30"].map(
    lambda x: f"{x:.1%}"
)

v["Overall >10 min"] = v["Overall_10"].map(
    lambda x: f"{x:.1%}"
)

v["Overall >20 min"] = v["Overall_20"].map(
    lambda x: f"{x:.1%}"
)

v["Overall >30 min"] = v["Overall_30"].map(
    lambda x: f"{x:.1%}"
)

v["Avg start delay (min)"] = (
    v["Avg_Start_Delay"].round(1)
)

v["Avg total delay (min)"] = (
    v["Avg_End_Delay"].round(1)
)

st.dataframe(
    v[
        [
            "Status",
            "Vendor",
            "Trips",
            "Cabs",
            "Occupancy %",
            "Start SLA breach",
            "End SLA breach",
            "Avg start delay (min)",
            "Avg total delay (min)",
            "Start >10 min",
            "Start >20 min",
            "Start >30 min",
            "Overall >10 min",
            "Overall >20 min",
            "Overall >30 min",
        ]
    ],
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Assumptions: managed fleet = Site Type O. "
    "Occupancy = Employee Count / Cab Capacity, averaged at trip level. "
    "Total delay = positive delay at planned trip end. "
    "No-delay ride = both actual start and actual end are on/before plan. "
    "Status thresholds are MVP assumptions, not contractual SLAs."
)
