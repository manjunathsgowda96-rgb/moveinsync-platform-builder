import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title='MoveInSync Operations Control Tower', page_icon='🚦', layout='wide')

st.markdown('''<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
[data-testid="stMetricValue"] {font-size: 1.8rem;}
.small {font-size: 0.85rem; color: #666;}
</style>''', unsafe_allow_html=True)

st.title('MoveInSync Operations Control Tower')
st.caption('MVP • Managed fleet (Site Type = O) • Historical operational view')

uploaded = st.file_uploader('Upload Fleet-CaseStudy-Data.xlsx', type=['xlsx'])
if uploaded is None:
    st.info('Upload the case-study Excel file to load the control tower. The file is processed in the app session and is not included in the application code.')
    st.stop()

@st.cache_data
def load_data(file):
    d = pd.read_excel(file)
    for c in ['Start Time','End Time','Planned Start','Planned End','Base Date']:
        if c in d.columns:
            d[c] = pd.to_datetime(d[c], errors='coerce')

    d['Start Delay Min'] = (d['Start Time'] - d['Planned Start']).dt.total_seconds() / 60
    d['End Delay Min'] = (d['End Time'] - d['Planned End']).dt.total_seconds() / 60
    d['Positive Start Delay'] = d['Start Delay Min'].clip(lower=0)
    d['Positive End Delay'] = d['End Delay Min'].clip(lower=0)
    d['Start Breach'] = d['Start Delay Min'] > 10
    d['End Breach'] = d['End Delay Min'] > 10
    d['Any Delay'] = (d['Start Delay Min'] > 0) | (d['End Delay Min'] > 0)
    d['No Delay'] = ~d['Any Delay']
    d['Start >10'] = d['Start Delay Min'] > 10
    d['Start >20'] = d['Start Delay Min'] > 20
    d['Start >30'] = d['Start Delay Min'] > 30

    residential_start = d['Event Start Landmark'].astype(str).str.startswith('Residential Cluster')
    d['Site'] = np.where(residential_start, d['Event End Landmark'], d['Event Start Landmark'])
    d['Site'] = d['Site'].where(~d['Site'].astype(str).str.startswith('Residential Cluster'), np.nan)
    d['Direction'] = np.where(residential_start, 'Home → Site', 'Site → Home')
    d['Route Key'] = d['Site'].astype(str) + ' | ' + d['Direction'].astype(str)
    d['Occupancy %'] = np.where(d['Cab Capacity'] > 0, d['Employee Count'] / d['Cab Capacity'], np.nan)
    return d

df = load_data(uploaded)
scope = df[df['Site Type'].eq('O')].copy()

# Explicit MVP assumptions; not claimed contractual SLAs.
START_THRESHOLD = 10
END_THRESHOLD = 10
WATCH_THRESHOLD = 20
ATTENTION_THRESHOLD = 30

# -----------------------------
# Global filters
# -----------------------------
st.sidebar.header('Control tower filters')
min_date = scope['Base Date'].min().date()
max_date = scope['Base Date'].max().date()
selected_dates = st.sidebar.slider('Date range', min_value=min_date, max_value=max_date, value=(min_date, max_date), format='DD MMM YYYY')

sites = sorted(scope['Site'].dropna().unique())
selected_sites = st.sidebar.multiselect('Site', sites)

shifts = sorted(scope['Shift'].dropna().astype(str).unique())
selected_shifts = st.sidebar.multiselect('Shift', shifts)

f = scope[(scope['Base Date'].dt.date >= selected_dates[0]) & (scope['Base Date'].dt.date <= selected_dates[1])].copy()
if selected_sites:
    f = f[f['Site'].isin(selected_sites)]
if selected_shifts:
    f = f[f['Shift'].isin(selected_shifts)]

# -----------------------------
# City health
# -----------------------------
st.subheader('City health')

total_city_sites = df['Site'].nunique()
managed_sites = scope['Site'].nunique()

trips = len(f)
no_delay_n = int(f['No Delay'].sum()) if trips else 0
any_delay_n = int(f['Any Delay'].sum()) if trips else 0
start_late_n = int(f['Start Delay Min'].gt(0).sum()) if trips else 0
occupancy = f['Occupancy %'].mean() if trips else 0

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric('Managed sites', f'{managed_sites}/{total_city_sites}')
c2.metric('Trips', f'{trips:,}')
c3.metric('No-delay rides', f'{no_delay_n:,}', f'{no_delay_n/trips:.1%}' if trips else '0.0%')
c4.metric('Rides with delay', f'{any_delay_n:,}', f'{any_delay_n/trips:.1%}' if trips else '0.0%')
c5.metric('Started late', f'{start_late_n:,}', f'{start_late_n/trips:.1%}' if trips else '0.0%')
c6.metric('Avg occupancy', f'{occupancy:.1%}' if pd.notna(occupancy) else '—')

b1,b2,b3 = st.columns(3)
b1.metric('Start >10 min', f'{int(f["Start >10"].sum()):,}', f'{f["Start >10"].mean():.1%}' if trips else '0.0%')
b2.metric('Start >20 min', f'{int(f["Start >20"].sum()):,}', f'{f["Start >20"].mean():.1%}' if trips else '0.0%')
b3.metric('Start >30 min', f'{int(f["Start >30"].sum()):,}', f'{f["Start >30"].mean():.1%}' if trips else '0.0%')

st.caption(f'Coverage: {selected_dates[0].strftime("%d %b %Y")} – {selected_dates[1].strftime("%d %b %Y")} • Scope: managed fleet (O)')
st.divider()

# -----------------------------
# Site health
# -----------------------------
st.subheader('Site health')

site = (f.groupby('Site', dropna=True)
          .agg(Trips=('Cab ID','size'), Cabs=('Cab ID','nunique'), Vendors=('Vendor','nunique'),
               Start_Breach=('Start Breach','mean'), End_Breach=('End Breach','mean'),
               Avg_Start_Delay=('Positive Start Delay','mean'), Avg_Trip_Delay=('Positive End Delay','mean'),
               Occupancy=('Occupancy %','mean'),
               Start_10=('Start >10','mean'), Start_20=('Start >20','mean'), Start_30=('Start >30','mean'))
          .reset_index())

site['Status'] = np.select(
    [site['End_Breach'] > ATTENTION_THRESHOLD/100,
     site['End_Breach'] > WATCH_THRESHOLD/100],
    ['🔴 Attention','🟠 Watch'], default='🟢 Healthy')
site = site.sort_values(['End_Breach','Trips'], ascending=[False,False])

display = site.rename(columns={
    'Start_Breach':'Start SLA breach', 'End_Breach':'End SLA breach',
    'Avg_Start_Delay':'Avg start delay (min)', 'Avg_Trip_Delay':'Avg total delay (min)',
    'Occupancy':'Occupancy %', 'Start_10':'Start >10 min', 'Start_20':'Start >20 min', 'Start_30':'Start >30 min'
}).copy()
for c in ['Start SLA breach','End SLA breach','Occupancy %','Start >10 min','Start >20 min','Start >30 min']:
    display[c] = display[c].map(lambda x: f'{x:.1%}')
for c in ['Avg start delay (min)','Avg total delay (min)']:
    display[c] = display[c].round(1)

st.dataframe(display[['Status','Site','Trips','Cabs','Vendors','Occupancy %','Start SLA breach','End SLA breach','Avg start delay (min)','Avg total delay (min)','Start >10 min','Start >20 min','Start >30 min']], use_container_width=True, hide_index=True)

st.caption(f'Site status uses End SLA breach rate: 🟢 Healthy ≤ {WATCH_THRESHOLD}% • 🟠 Watch > {WATCH_THRESHOLD}% to {ATTENTION_THRESHOLD}% • 🔴 Attention > {ATTENTION_THRESHOLD}%. 10-minute SLA breach is an MVP assumption.')
st.divider()

# -----------------------------
# Exception queue + late-risk proxy
# -----------------------------
st.subheader('Exception queue')

exceptions = f[(f['Start Breach']) | (f['End Breach'])].copy()

# Historical late-risk proxy. This is NOT a live probability because the supplied file has no live GPS/ETA.
exceptions = exceptions.sort_values(['Cab ID','Site','Direction','Base Date','Planned Start']).copy()
groups = ['Cab ID','Site','Direction']
exceptions['Prior comparable count'] = exceptions.groupby(groups).cumcount()
exceptions['Prior comparable late rate'] = (
    exceptions.groupby(groups)['End Breach']
    .transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean())
)
exceptions['Route late rate'] = exceptions.groupby(['Site','Direction'])['End Breach'].transform('mean')
exceptions['Shift late rate'] = exceptions.groupby('Shift')['End Breach'].transform('mean')

# Score: current start delay (40%), recent same-cab/route history (30%), route history (20%), shift pattern (10%).
start_component = (exceptions['Positive Start Delay'].clip(0,30) / 30 * 100)
history_component = exceptions['Prior comparable late rate'].fillna(exceptions['Route late rate']).fillna(0) * 100
route_component = exceptions['Route late rate'].fillna(0) * 100
shift_component = exceptions['Shift late rate'].fillna(0) * 100
exceptions['Late Risk Score'] = (0.40*start_component + 0.30*history_component + 0.20*route_component + 0.10*shift_component).clip(0,100).round(0)

# Reason / owner assignment for MVP workflow.
def reason_owner(row):
    if row['Positive End Delay'] > 30:
        return 'Severe trip delay', 'City Ops 1'
    if row['Positive Start Delay'] > 10:
        return 'Late departure', 'City Ops 2'
    if pd.notna(row['Prior comparable late rate']) and row['Prior comparable late rate'] >= 0.50:
        return 'Repeated cab/route risk', 'City Ops 3'
    return 'Route/site pattern', 'City Ops 4'

reason_owner_values = exceptions.apply(reason_owner, axis=1, result_type='expand')
exceptions['Reason'] = reason_owner_values[0]
exceptions['Owner'] = reason_owner_values[1]
exceptions['Risk'] = pd.cut(exceptions['Late Risk Score'], bins=[-1,39,69,100], labels=['Low','Medium','High'])

exceptions = exceptions.sort_values(['Late Risk Score','Positive End Delay'], ascending=[False,False])

q1,q2,q3,q4 = st.columns(4)
q1.metric('Start breaches', f'{int(f["Start Breach"].sum()):,}')
q2.metric('End breaches', f'{int(f["End Breach"].sum()):,}')
q3.metric('Any breach', f'{len(exceptions):,}')
q4.metric('High-risk exceptions', f'{int((exceptions["Risk"] == "High").sum()):,}')

qcols = ['Risk','Late Risk Score','Reason','Owner','Cab ID','Site','Vendor','Direction','Shift','Planned Start','Start Time','Start Delay Min','Planned End','End Time','End Delay Min']
show = exceptions[[c for c in qcols if c in exceptions.columns]].head(150).copy()
for c in ['Start Delay Min','End Delay Min']:
    show[c] = show[c].round(1)
st.dataframe(show, use_container_width=True, hide_index=True)

st.caption('Late Risk Score is an MVP historical proxy using current recorded start delay + recent comparable cab/route history + route/site history + shift pattern. It is not a validated live probability; a live version would require current trip/ETA/GPS data.')
st.divider()

# -----------------------------
# Vendor service performance
# -----------------------------
st.subheader('Vendor service performance')

vc1, vc2 = st.columns([1,2])
vendor_options = sorted(f['Vendor'].dropna().unique())
with vc1:
    selected_vendors = st.multiselect('Vendor', vendor_options, key='vendor_filter')
with vc2:
    st.write(f'Using the global date range: {selected_dates[0].strftime("%d %b %Y")} – {selected_dates[1].strftime("%d %b %Y")}')

vf = f[f['Vendor'].isin(selected_vendors)].copy() if selected_vendors else f.copy()

v = (vf.groupby('Vendor').agg(Trips=('Cab ID','size'), Cabs=('Cab ID','nunique'),
                              Occupancy=('Occupancy %','mean'), Start_Breach=('Start Breach','mean'), End_Breach=('End Breach','mean'),
                              Avg_Start_Delay=('Positive Start Delay','mean'), Avg_End_Delay=('Positive End Delay','mean'),
                              Start_10=('Start >10','mean'), Start_20=('Start >20','mean'), Start_30=('Start >30','mean')).reset_index())
v['Status'] = np.select([v['End_Breach'] > ATTENTION_THRESHOLD/100, v['End_Breach'] > WATCH_THRESHOLD/100], ['🔴 Attention','🟠 Watch'], default='🟢 Healthy')
v = v.sort_values('End_Breach', ascending=False)
v['Start SLA breach'] = v['Start_Breach'].map(lambda x:f'{x:.1%}')
v['End SLA breach'] = v['End_Breach'].map(lambda x:f'{x:.1%}')
v['Occupancy %'] = v['Occupancy'].map(lambda x:f'{x:.1%}')
v['Start >10 min'] = v['Start_10'].map(lambda x:f'{x:.1%}')
v['Start >20 min'] = v['Start_20'].map(lambda x:f'{x:.1%}')
v['Start >30 min'] = v['Start_30'].map(lambda x:f'{x:.1%}')
v['Avg start delay (min)'] = v['Avg_Start_Delay'].round(1)
v['Avg total delay (min)'] = v['Avg_End_Delay'].round(1)
st.dataframe(v[['Status','Vendor','Trips','Cabs','Occupancy %','Start SLA breach','End SLA breach','Avg start delay (min)','Avg total delay (min)','Start >10 min','Start >20 min','Start >30 min']], use_container_width=True, hide_index=True)

st.caption('Assumptions: managed fleet = Site Type O. Occupancy = Employee Count / Cab Capacity, averaged at trip level. Total delay = positive delay at planned trip end. No-delay ride = both actual start and actual end are on/before plan. Status thresholds are MVP assumptions, not contractual SLAs.')
