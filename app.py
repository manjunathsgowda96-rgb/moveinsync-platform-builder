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

# First row
c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric(
    "Managed sites",
    f"{managed_sites}/{total_city_sites}"
)

c2.metric(
    "Trips",
    f"{trips:,}"
)

c3.metric(
    "No-delay rides",
    f"{no_delay_n:,}",
    f"{no_delay_n / trips:.1%}" if trips else "0.0%"
)

c4.metric(
    "Rides with delay",
    f"{any_delay_n:,}",
    f"{any_delay_n / trips:.1%}" if trips else "0.0%"
)

c5.metric(
    "Started late",
    f"{start_late_n:,}",
    f"{start_late_n / trips:.1%}" if trips else "0.0%"
)

c6.metric(
    "Avg occupancy",
    f"{occupancy:.1%}" if pd.notna(occupancy) else "—"
)

# Second row: delay metrics
b1, b2, b3, b4, b5 = st.columns(5)

b1.metric(
    "Avg start delay",
    f"{avg_start_delay:.1f} min"
)

b2.metric(
    "Avg total delay",
    f"{avg_total_delay:.1f} min"
)

b3.metric(
    "Overall delay >10 min",
    f"{int(f['Overall >10'].sum()):,}",
    f"{f['Overall >10'].mean():.1%}" if trips else "0.0%"
)

b4.metric(
    "Overall delay >20 min",
    f"{int(f['Overall >20'].sum()):,}",
    f"{f['Overall >20'].mean():.1%}" if trips else "0.0%"
)

b5.metric(
    "Overall delay >30 min",
    f"{int(f['Overall >30'].sum()):,}",
    f"{f['Overall >30'].mean():.1%}" if trips else "0.0%"
)

# Third row: start-delay severity
s1, s2, s3 = st.columns(3)

s1.metric(
    "Started >10 min late",
    f"{int(f['Start >10'].sum()):,}",
    f"{f['Start >10'].mean():.1%}" if trips else "0.0%"
)

s2.metric(
    "Started >20 min late",
    f"{int(f['Start >20'].sum()):,}",
    f"{f['Start >20'].mean():.1%}" if trips else "0.0%"
)

s3.metric(
    "Started >30 min late",
    f"{int(f['Start >30'].sum()):,}",
    f"{f['Start >30'].mean():.1%}" if trips else "0.0%"
)

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

st.subheader("Exception queue")

exceptions = f[
    (f["Start Breach"])
    | (f["End Breach"])
].copy()

# Sort for historical calculations
exceptions = exceptions.sort_values(
    [
        "Cab ID",
        "Site",
        "Direction",
        "Base Date",
        "Planned Start"
    ]
).copy()

groups = [
    "Cab ID",
    "Site",
    "Direction"
]

exceptions["Prior comparable count"] = (
    exceptions.groupby(groups).cumcount()
)

exceptions["Prior comparable late rate"] = (
    exceptions.groupby(groups)["End Breach"]
    .transform(
        lambda s:
        s.shift(1)
        .rolling(10, min_periods=3)
        .mean()
    )
)

exceptions["Route late rate"] = (
    exceptions.groupby(
        ["Site", "Direction"]
    )["End Breach"]
    .transform("mean")
)

exceptions["Shift late rate"] = (
    exceptions.groupby("Shift")["End Breach"]
    .transform("mean")
)

# Risk score
start_component = (
    exceptions["Positive Start Delay"]
    .clip(0, 30)
    / 30
    * 100
)

history_component = (
    exceptions["Prior comparable late rate"]
    .fillna(exceptions["Route late rate"])
    .fillna(0)
    * 100
)

route_component = (
    exceptions["Route late rate"]
    .fillna(0)
    * 100
)

shift_component = (
    exceptions["Shift late rate"]
    .fillna(0)
    * 100
)

exceptions["Late Risk Score"] = (
    0.40 * start_component
    + 0.30 * history_component
    + 0.20 * route_component
    + 0.10 * shift_component
).clip(0, 100).round(0)


def reason_owner(row):

    if row["Positive End Delay"] > 30:
        return "Severe trip delay", "City Ops 1"

    if row["Positive Start Delay"] > 10:
        return "Late departure", "City Ops 2"

    if (
        pd.notna(row["Prior comparable late rate"])
        and row["Prior comparable late rate"] >= 0.50
    ):
        return "Repeated cab/route risk", "City Ops 3"

    return "Route/site pattern", "City Ops 4"


reason_owner_values = exceptions.apply(
    reason_owner,
    axis=1,
    result_type="expand"
)

exceptions["Reason"] = reason_owner_values[0]
exceptions["Owner"] = reason_owner_values[1]

exceptions["Risk"] = pd.cut(
    exceptions["Late Risk Score"],
    bins=[-1, 39, 69, 100],
    labels=["Low", "Medium", "High"]
)

exceptions = exceptions.sort_values(
    [
        "Late Risk Score",
        "Positive End Delay"
    ],
    ascending=[False, False]
)

q1, q2, q3, q4 = st.columns(4)

q1.metric(
    "Start breaches",
    f"{int(f['Start Breach'].sum()):,}"
)

q2.metric(
    "End breaches",
    f"{int(f['End Breach'].sum()):,}"
)

q3.metric(
    "Any breach",
    f"{len(exceptions):,}"
)

q4.metric(
    "High-risk exceptions",
    f"{int((exceptions['Risk'] == 'High').sum()):,}"
)

qcols = [
    "Risk",
    "Late Risk Score",
    "Reason",
    "Owner",
    "Cab ID",
    "Site",
    "Vendor",
    "Direction",
    "Planned Start",
    "Start Time",
    "Start Delay Min",
    "Planned End",
    "End Time",
    "End Delay Min"
]

show = exceptions[
    [c for c in qcols if c in exceptions.columns]
].head(150).copy()

for c in [
    "Start Delay Min",
    "End Delay Min"
]:
    show[c] = show[c].round(1)

st.dataframe(
    show,
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Late Risk Score is an MVP historical proxy using recorded start delay, "
    "recent comparable cab/route history, route/site history and shift pattern. "
    "It is not a validated live probability; a live version would require "
    "current trip/ETA/GPS data."
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
