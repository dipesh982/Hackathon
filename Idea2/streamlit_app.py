# Cost Attribution Copilot — Cortex AI-powered warehouse cost anomaly dashboard
import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Cost Attribution Copilot", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))


@st.cache_data(ttl=300)
def load_daily_costs():
    return conn.query("""
        SELECT WAREHOUSE_NAME, USAGE_DATE, TOTAL_CREDITS
        FROM MYDB.DB.DAILY_WAREHOUSE_COST
        ORDER BY USAGE_DATE
    """)


@st.cache_data(ttl=300)
def load_spikes():
    return conn.query("""
        SELECT WAREHOUSE_NAME, USAGE_DATE, TOTAL_CREDITS, PREV_DAY, SPIKE
        FROM MYDB.DB.COST_SPIKES
        ORDER BY SPIKE DESC
    """)


@st.cache_data(ttl=300)
def load_insights():
    return conn.query("""
        SELECT WAREHOUSE_NAME, USAGE_DATE, SPIKE, COST_EXPLANATION
        FROM MYDB.DB.COST_INSIGHTS
        ORDER BY SPIKE DESC
    """)


st.title("Cost Attribution Copilot")
st.caption("Cortex AI-powered warehouse cost anomaly detection & explanation")

with st.spinner("Loading data..."):
    df_daily = load_daily_costs().copy()
    df_spikes = load_spikes().copy()
    df_insights = load_insights().copy()

df_daily["USAGE_DATE"] = pd.to_datetime(df_daily["USAGE_DATE"]).dt.date
df_spikes["USAGE_DATE"] = pd.to_datetime(df_spikes["USAGE_DATE"]).dt.date
df_insights["USAGE_DATE"] = pd.to_datetime(df_insights["USAGE_DATE"]).dt.date

if df_daily.empty:
    st.warning("No cost data found. Run the pipeline in Idea2.sql first.")
    st.stop()

# --- KPI Row 1: Overview ---
total_credits = df_daily["TOTAL_CREDITS"].sum()
avg_daily_credits = df_daily.groupby("USAGE_DATE")["TOTAL_CREDITS"].sum().mean()
num_spikes = len(df_spikes)
num_warehouses = df_daily["WAREHOUSE_NAME"].nunique()
max_single_day = df_daily.groupby("USAGE_DATE")["TOTAL_CREDITS"].sum().max()
total_spike_credits = df_spikes["SPIKE"].sum()

with st.container(horizontal=True):
    st.metric("Total Credits (30d)", f"{total_credits:.1f}", border=True)
    st.metric("Avg Daily Credits", f"{avg_daily_credits:.1f}", border=True)
    st.metric("Peak Day Credits", f"{max_single_day:.1f}", border=True)

with st.container(horizontal=True):
    st.metric("Cost Spikes Detected", f"{num_spikes}", border=True)
    st.metric("Credits Lost to Spikes", f"{total_spike_credits:.1f}", border=True)
    st.metric("Warehouses Monitored", f"{num_warehouses}", border=True)

# --- Sidebar Filters ---
with st.sidebar:
    st.header("Filters")
    warehouses = df_daily["WAREHOUSE_NAME"].unique().tolist()
    selected_wh = st.multiselect("Warehouse", warehouses, default=warehouses)

df_filtered = df_daily[df_daily["WAREHOUSE_NAME"].isin(selected_wh)]
df_spikes_filtered = df_spikes[df_spikes["WAREHOUSE_NAME"].isin(selected_wh)]
df_insights_filtered = df_insights[df_insights["WAREHOUSE_NAME"].isin(selected_wh)]

# --- Daily Cost Trend Chart ---
with st.container(border=True):
    st.subheader("Daily Credit Usage by Warehouse")
    pivot_data = df_filtered.pivot_table(
        index="USAGE_DATE", columns="WAREHOUSE_NAME", values="TOTAL_CREDITS", aggfunc="sum"
    ).reset_index()
    st.line_chart(pivot_data, x="USAGE_DATE", y=[c for c in pivot_data.columns if c != "USAGE_DATE"])

# --- Spike Details ---
col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("Spike Magnitude by Warehouse")
        if not df_spikes_filtered.empty:
            st.bar_chart(df_spikes_filtered, x="WAREHOUSE_NAME", y="SPIKE", color="WAREHOUSE_NAME")
        else:
            st.info("No spikes for selected warehouses.")

with col2:
    with st.container(border=True):
        st.subheader("Spike Events")
        if not df_spikes_filtered.empty:
            st.dataframe(
                df_spikes_filtered[["WAREHOUSE_NAME", "USAGE_DATE", "TOTAL_CREDITS", "PREV_DAY", "SPIKE"]],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No spikes for selected warehouses.")

# --- Cortex AI Explanations ---
with st.container(border=True):
    st.subheader("Cortex AI Cost Spike Explanations")
    if df_insights_filtered.empty:
        st.info("No AI insights available for selected warehouses.")
    else:
        for _, row in df_insights_filtered.iterrows():
            with st.expander(f"{row['WAREHOUSE_NAME']} — {row['USAGE_DATE']} (spike: +{row['SPIKE']:.1f} credits)"):
                st.write(row["COST_EXPLANATION"])

# --- Refresh ---
if st.button("Refresh Data"):
    load_daily_costs.clear()
    load_spikes.clear()
    load_insights.clear()
    st.rerun()
