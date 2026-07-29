# Data Cleanup & Archival Advisor — Cortex AI-powered unused table governance dashboard
import os
import re
import streamlit as st

st.set_page_config(page_title="Data Cleanup & Archival Advisor", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))


@st.cache_data(ttl=300)
def load_unused_tables():
    return conn.query("""
        SELECT TABLE_SCHEMA, TABLE_NAME, LAST_ALTERED, ROW_COUNT
        FROM MYDB.DB.UNUSED_TABLES
        ORDER BY ROW_COUNT DESC
    """)


@st.cache_data(ttl=300)
def load_recommendations():
    return conn.query("""
        SELECT TABLE_SCHEMA, TABLE_NAME, RECOMMENDATION
        FROM MYDB.DB.CLEANUP_RECOMMENDATIONS
    """)


def extract_risk_level(recommendation):
    match = re.search(r'\*\*Risk Level:\s*(LOW|MEDIUM|HIGH)\*\*', recommendation)
    return match.group(1) if match else "UNKNOWN"


def extract_storage_savings(recommendation):
    match = re.search(r'~?([\d.]+)\s*(GB|MB|KB)', recommendation)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        if unit == "GB":
            return value * 1024
        elif unit == "MB":
            return value
        elif unit == "KB":
            return value / 1024
    if "<1 MB" in recommendation:
        return 0.5
    return 0.0


st.title("Data Cleanup & Archival Advisor")
st.caption("Cortex AI-powered identification of unused tables with governance recommendations")

with st.spinner("Loading data..."):
    df_tables = load_unused_tables()
    df_recs = load_recommendations()

if df_tables.empty:
    st.warning("No unused tables found. Run the pipeline in Idea3.sql first.")
    st.stop()

# Enrich recommendations with parsed fields
df_recs["RISK_LEVEL"] = df_recs["RECOMMENDATION"].apply(extract_risk_level)
df_recs["STORAGE_SAVINGS_MB"] = df_recs["RECOMMENDATION"].apply(extract_storage_savings)

# Merge for combined view
df_combined = df_tables.merge(df_recs, on=["TABLE_SCHEMA", "TABLE_NAME"], how="left")

# --- KPI Row 1 ---
total_unused = len(df_tables)
total_rows_unused = df_tables["ROW_COUNT"].sum()
total_schemas_affected = df_tables["TABLE_SCHEMA"].nunique()
total_storage_savings_mb = df_recs["STORAGE_SAVINGS_MB"].sum()
total_storage_savings_gb = total_storage_savings_mb / 1024

with st.container(horizontal=True):
    st.metric("Unused Tables", f"{total_unused}", border=True)
    st.metric("Total Rows at Risk", f"{total_rows_unused:,.0f}", border=True)
    st.metric("Schemas Affected", f"{total_schemas_affected}", border=True)

# --- KPI Row 2 ---
risk_counts = df_recs["RISK_LEVEL"].value_counts()
low_risk = risk_counts.get("LOW", 0)
medium_risk = risk_counts.get("MEDIUM", 0)
high_risk = risk_counts.get("HIGH", 0)

with st.container(horizontal=True):
    st.metric("Est. Storage Savings", f"{total_storage_savings_gb:.1f} GB", border=True)
    st.metric("Low Risk (safe to drop)", f"{low_risk}", border=True)
    st.metric("Medium Risk (archive first)", f"{medium_risk}", border=True)

# --- Sidebar Filters ---
with st.sidebar:
    st.header("Filters")
    schemas = df_tables["TABLE_SCHEMA"].unique().tolist()
    selected_schemas = st.multiselect("Schema", schemas, default=schemas)
    risk_options = ["LOW", "MEDIUM", "HIGH"]
    selected_risks = st.multiselect("Risk Level", risk_options, default=risk_options)

df_display = df_combined[
    (df_combined["TABLE_SCHEMA"].isin(selected_schemas))
    & (df_combined["RISK_LEVEL"].isin(selected_risks))
]

# --- Charts ---
col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("Unused Tables by Schema")
        schema_counts = df_display.groupby("TABLE_SCHEMA")["TABLE_NAME"].count().reset_index()
        schema_counts.columns = ["TABLE_SCHEMA", "COUNT"]
        st.bar_chart(schema_counts, x="TABLE_SCHEMA", y="COUNT")

with col2:
    with st.container(border=True):
        st.subheader("Risk Level Distribution")
        risk_dist = df_display["RISK_LEVEL"].value_counts().reset_index()
        risk_dist.columns = ["RISK_LEVEL", "COUNT"]
        st.bar_chart(risk_dist, x="RISK_LEVEL", y="COUNT")

# --- Row Count by Table (top offenders) ---
with st.container(border=True):
    st.subheader("Largest Unused Tables (by Row Count)")
    top_tables = df_display[["TABLE_SCHEMA", "TABLE_NAME", "ROW_COUNT", "RISK_LEVEL", "STORAGE_SAVINGS_MB"]].copy()
    top_tables = top_tables.sort_values("ROW_COUNT", ascending=False)
    st.dataframe(top_tables, hide_index=True, use_container_width=True)

# --- AI Recommendations ---
with st.container(border=True):
    st.subheader("Cortex AI Cleanup Recommendations")
    if df_display.empty:
        st.info("No tables match current filters.")
    else:
        for _, row in df_display.iterrows():
            risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(row["RISK_LEVEL"], "⚪")
            with st.expander(f"{risk_icon} {row['TABLE_SCHEMA']}.{row['TABLE_NAME']} — {row['RISK_LEVEL']} risk"):
                st.markdown(row["RECOMMENDATION"])

# --- Refresh ---
if st.button("Refresh Data"):
    load_unused_tables.clear()
    load_recommendations.clear()
    st.rerun()
