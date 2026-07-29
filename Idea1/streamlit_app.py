# SQL Optimization Engine — KPIs for Cortex-powered SQL optimization
import os
import streamlit as st

st.set_page_config(page_title="SQL Optimization Engine", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))


@st.cache_data(ttl=300)
def load_expensive_queries():
    return conn.query("""
        SELECT
            QUERY_ID,
            QUERY_TEXT,
            EXECUTION_SECONDS,
            BYTES_SCANNED,
            WAREHOUSE_NAME,
            USER_NAME
        FROM MYDB.DB.TOP_EXPENSIVE_QUERIES
        ORDER BY BYTES_SCANNED DESC
    """)


@st.cache_data(ttl=300)
def load_optimization_results():
    return conn.query("""
        SELECT
            QUERY_ID,
            QUERY_TEXT,
            OPTIMIZED_QUERY,
            EXPLANATION
        FROM MYDB.DB.QUERY_OPTIMIZATION_RESULTS
    """)


st.title("SQL Optimization Engine")
st.caption("Cortex AI-powered query cost reduction insights")

with st.spinner("Loading data..."):
    df_queries = load_expensive_queries()
    df_optimized = load_optimization_results()

if df_queries.empty:
    st.warning("No expensive queries found. Run the pipeline in Idea1.sql first.")
    st.stop()

# --- KPI Row ---
total_queries = len(df_queries)
total_optimized = len(df_optimized)
optimization_rate = (total_optimized / total_queries * 100) if total_queries > 0 else 0
total_bytes_scanned = df_queries["BYTES_SCANNED"].sum()
avg_execution_sec = df_queries["EXECUTION_SECONDS"].mean()

with st.container(horizontal=True):
    st.metric("Expensive Queries (30d)", f"{total_queries}", border=True)
    st.metric("Optimized by Cortex", f"{total_optimized}", border=True)
    st.metric("Optimization Rate", f"{optimization_rate:.0f}%", border=True)

with st.container(horizontal=True):
    st.metric("Total Data Scanned", f"{total_bytes_scanned / 1e12:.2f} TB", border=True)
    st.metric("Avg Execution Time", f"{avg_execution_sec:.1f}s", border=True)
    st.metric("Unique Users", f"{df_queries['USER_NAME'].nunique()}", border=True)

# --- Charts ---
col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("Data Scanned by Warehouse")
        wh_data = (
            df_queries.groupby("WAREHOUSE_NAME")["BYTES_SCANNED"]
            .sum()
            .reset_index()
            .sort_values("BYTES_SCANNED", ascending=False)
        )
        wh_data["BYTES_SCANNED_TB"] = wh_data["BYTES_SCANNED"] / 1e12
        st.bar_chart(wh_data, x="WAREHOUSE_NAME", y="BYTES_SCANNED_TB")

with col2:
    with st.container(border=True):
        st.subheader("Queries by User")
        user_data = (
            df_queries.groupby("USER_NAME")["QUERY_ID"]
            .count()
            .reset_index()
            .rename(columns={"QUERY_ID": "QUERY_COUNT"})
            .sort_values("QUERY_COUNT", ascending=False)
            .head(10)
        )
        st.bar_chart(user_data, x="USER_NAME", y="QUERY_COUNT")

# --- Top Expensive Queries Table ---
with st.container(border=True):
    st.subheader("Top Expensive Queries")
    display_df = df_queries[["QUERY_ID", "USER_NAME", "WAREHOUSE_NAME", "EXECUTION_SECONDS", "BYTES_SCANNED"]].copy()
    display_df["GB_SCANNED"] = display_df["BYTES_SCANNED"] / 1e9
    st.dataframe(
        display_df[["QUERY_ID", "USER_NAME", "WAREHOUSE_NAME", "EXECUTION_SECONDS", "GB_SCANNED"]],
        hide_index=True,
        use_container_width=True,
    )

# --- Optimization Results ---
with st.container(border=True):
    st.subheader("Cortex Optimization Results")
    if df_optimized.empty:
        st.info("No optimization results yet.")
    else:
        for _, row in df_optimized.head(5).iterrows():
            with st.expander(f"Query: {row['QUERY_ID']}"):
                st.markdown("**Original:**")
                st.code(row["QUERY_TEXT"], language="sql")
                st.markdown("**Optimized:**")
                st.code(row["OPTIMIZED_QUERY"], language="sql")
                if row.get("EXPLANATION"):
                    st.markdown("**Explanation:**")
                    st.write(row["EXPLANATION"])

# --- Refresh ---
if st.button("Refresh Data"):
    load_expensive_queries.clear()
    load_optimization_results.clear()
    st.rerun()
