import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title='MoveInSync Operations Control Tower', page_icon='🚦', layout='wide')

st.markdown('''<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
.metric-card {padding: 12px 16px; border: 1px solid #e6e6e6; border-radius: 10px; background: #fff;}
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
    d['Start Breach'] = d['Start Delay Min'] > 10
    d['End Breach'] = d['End Delay Min'] > 10
    d['Site'] = np.where(d['Event Start Landmark'].astype(str).str.startswith('Residential Cluster'), d['Event End Landmark'], d['Event Start Landmark'])
    d['Site'] = np.where(d['Site'].astype(str).str.startswith('Residential Cluster'), np.nan, d['Site'])
    d['Direction'] = np.where(d['Event Start Landmark'].astype(str).str.startswith('Residential Cluster'), 'Home → Site', 'Site → Home')
    return d

df = load_data(uploaded)

# Scope to managed-service fleet
scope = df[df['Site Type'].eq('O')].copy()

# Thresholds are explicit MVP assumptions, not claimed contractual SLAs.
start_threshold = 10
end_threshold = 10
site_red = 30
site_amber = 20

st.sidebar.header('Filters')
vendors = sorted(scope['Vendor'].dropna().unique())
selected_vendor = st.sidebar.multiselect('Vendor', vendors)
shift_values = sorted(scope['Shift'].dropna().unique())
selected_shift = st.sidebar.multiselect('Shift', shift_values)
sites = sorted(scope['Site'].dropna().unique())
selected_sites = st.sidebar.multiselect('Site', sites)

f = scope.copy()
if selected_vendor: f = f[f['Vendor'].isin(selected_vendor)]
if selected_shift: f = f[f['Shift'].isin(selected_shift)]
if selected_sites: f = f[f['Site'].isin(selected_sites)]

st.subheader('City health')
c1,c2,c3,c4,c5 = st.columns(5)
c1.metric('Managed-fleet trips', f'{len(f):,}')
c2.metric('Sites', f'{f["Site"].nunique():,}')
c3.metric('Cabs', f'{f["Cab ID"].nunique():,}')
c4.metric('Vendors', f'{f["Vendor"].nunique():,}')
slab = f['Start Breach'].mean() if len(f) else 0
elab = f['End Breach'].mean() if len(f) else 0
c5.metric('End SLA breach', f'{elab:.1%}')

st.divider()

# Site health
st.subheader('Site health')
site = (f.groupby('Site', dropna=True)
          .agg(Trips=('Cab ID','size'), Cabs=('Cab ID','nunique'), Vendors=('Vendor','nunique'),
               Start_Breach=('Start Breach','mean'), End_Breach=('End Breach','mean'),
               Avg_Start_Delay=('Start Delay Min','mean'), Avg_End_Delay=('End Delay Min','mean'),
               Employees=('Employee Count','sum'))
          .reset_index())
site['Status'] = np.select([site['End_Breach'] > site_red/100, site['End_Breach'] > site_amber/100], ['🔴 Attention','🟠 Watch'], default='🟢 Healthy')
site = site.sort_values(['End_Breach','Trips'], ascending=[False,False])

display = site.rename(columns={'Start_Breach':'Start SLA breach','End_Breach':'End SLA breach','Avg_Start_Delay':'Avg start delay (min)','Avg_End_Delay':'Avg end delay (min)'})
display['Start SLA breach'] = display['Start SLA breach'].map(lambda x:f'{x:.1%}')
display['End SLA breach'] = display['End SLA breach'].map(lambda x:f'{x:.1%}')
display['Avg start delay (min)'] = display['Avg start delay (min)'].round(1)
display['Avg end delay (min)'] = display['Avg end delay (min)'].round(1)
st.dataframe(display[['Status','Site','Trips','Cabs','Vendors','Start SLA breach','End SLA breach','Avg start delay (min)','Avg end delay (min)']], use_container_width=True, hide_index=True)

st.divider()

# Exception queue
st.subheader('Exception queue')
exceptions = f[(f['Start Breach']) | (f['End Breach'])].copy()
exceptions['Severity'] = np.select([exceptions['End Delay Min'] > 30, exceptions['End Delay Min'] > 10], ['High','Medium'], default='Low')
exceptions = exceptions.sort_values(['Severity','End Delay Min'], ascending=[True,False])
# make severity order high first
order = pd.CategoricalDtype(['High','Medium','Low'], ordered=True)
exceptions['Severity'] = exceptions['Severity'].astype(order)
exceptions = exceptions.sort_values(['Severity','End Delay Min'], ascending=[True,False])

q1,q2,q3 = st.columns(3)
q1.metric('Trips with start breach', f'{int(f["Start Breach"].sum()):,}')
q2.metric('Trips with end breach', f'{int(f["End Breach"].sum()):,}')
q3.metric('Trips with any breach', f'{len(exceptions):,}')

cols = ['Severity','Cab ID','Site','Vendor','Shift','Planned Start','Start Time','Start Delay Min','Planned End','End Time','End Delay Min']
show = exceptions[[c for c in cols if c in exceptions.columns]].head(100).copy()
for c in ['Start Delay Min','End Delay Min']:
    if c in show: show[c] = show[c].round(1)
st.dataframe(show, use_container_width=True, hide_index=True)

st.divider()

# Vendor view
st.subheader('Vendor service performance')
v = (f.groupby('Vendor').agg(Trips=('Cab ID','size'), Cabs=('Cab ID','nunique'),
                              Start_Breach=('Start Breach','mean'), End_Breach=('End Breach','mean'),
                              Avg_End_Delay=('End Delay Min','mean')).reset_index())
v['Status'] = np.select([v['End_Breach'] > site_red/100, v['End_Breach'] > site_amber/100], ['🔴 Attention','🟠 Watch'], default='🟢 Healthy')
v = v.sort_values('End_Breach', ascending=False)
v['Start SLA breach'] = v['Start_Breach'].map(lambda x:f'{x:.1%}')
v['End SLA breach'] = v['End_Breach'].map(lambda x:f'{x:.1%}')
v['Avg end delay (min)'] = v['Avg_End_Delay'].round(1)
st.dataframe(v[['Status','Vendor','Trips','Cabs','Start SLA breach','End SLA breach','Avg end delay (min)']], use_container_width=True, hide_index=True)

st.caption('MVP assumption: a 10-minute delay is used as an illustrative operating threshold. This is not presented as the contractual SLA; confirm the actual threshold with MoveInSync.')
