"""
🌐 Harmony AI - Web Interface
Streamlit-based web UI for Contoso Analytics Assistant
"""

import streamlit as st
import pandas as pd
import time
import json
from datetime import datetime

from app.llm.sql_generator import DynamicSQLGenerator
from app.database.db_client import execute_sql
from app.llm.result_summarizer import ResultSummarizer
from app.memory.query_logger import QueryLogger
from app.memory.pattern_miner import get_pattern_miner
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ------------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------------
st.set_page_config(
    page_title="Harmony AI - Contoso Analytics",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ------------------------------------------------------------
# Custom CSS
# ------------------------------------------------------------
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px;
        margin-bottom: 2rem;
    }

    .sql-box {
        background-color: #1e1e1e;
        color: #cfcfcf;
        padding: 1rem;
        border-radius: 8px;
        font-family: 'Courier New', monospace;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------
# Session State Initialization
# ------------------------------------------------------------
if "sql_generator" not in st.session_state:
    st.session_state.sql_generator = DynamicSQLGenerator()

if "summarizer" not in st.session_state:
    st.session_state.summarizer = ResultSummarizer()

if "query_logger" not in st.session_state:
    st.session_state.query_logger = QueryLogger()

if "query_history" not in st.session_state:
    st.session_state.query_history = []

if "patterns_cache" not in st.session_state:
    st.session_state.patterns_cache = None
    st.session_state.patterns_cache_time = 0


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main():
    st.markdown('<div class="main-header">🤖 Harmony AI - Contoso Analytics Assistant</div>', unsafe_allow_html=True)

    with st.sidebar:
        sidebar_ui()

    tabs = st.tabs(["💬 Chat", "📊 Analytics", "📚 History", "🔍 Patterns"])
    
    with tabs[0]:
        chat_interface()

    with tabs[1]:
        analytics_dashboard()

    with tabs[2]:
        query_history_view()

    with tabs[3]:
        patterns_view()


# ------------------------------------------------------------
# SIDEBAR UI
# ------------------------------------------------------------
def sidebar_ui():

    st.image(
        "https://assets.zyrosite.com/cdn-cgi/image/format=auto,w=560,fit=crop,q=95/dWxbjG54J4FrOnry/harmony-logo-gradient-YBg4yWLpRriXjwvG.png",
        width="stretch",
    )

    st.markdown("---")
    st.markdown("### 📊 Quick Stats")

    stats = st.session_state.query_logger.get_statistics()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Queries", stats.get("total_queries", 0))
        st.metric("Success Rate", f"{stats.get('success_rate', 0)*100:.1f}%")

    with col2:
        st.metric("Successful", stats.get("successful_queries", 0))
        st.metric("Failed", stats.get("failed_queries", 0))

    st.markdown("---")
    st.markdown("### 💡 Example Questions")

    examples = [
        "2008 yılında toplam satış nedir?",
        "En çok satan 5 ürün hangisi?",
        "Mağaza vs online satış 2007",
        "2009 aylık satış trendi",
        "En az satan ürün nedir?"
    ]

    for example in examples:
        if st.button(example, key=f"ex_{example}", use_container_width=True):
            st.session_state.query_input = example
            st.rerun()

    st.markdown("---")

    with st.expander("⚙️ Advanced Options"):
        st.session_state.show_sql = st.checkbox("Show Generated SQL", True)
        st.session_state.show_intent = st.checkbox("Show Intent Classification", True)
        st.session_state.show_execution_time = st.checkbox("Show Execution Time", True)
        st.session_state.auto_visualize = st.checkbox("Auto Visualization", True)

    st.markdown("---")

    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.query_history = []
        st.success("History cleared!")


# ------------------------------------------------------------
# CHAT INTERFACE
# ------------------------------------------------------------
def chat_interface():

    st.markdown("### 💬 Ask Your Question")

    query = st.text_input(
        "Enter your business question:",
        key="query_input",
        placeholder="Örn: 2008 yılında toplam satış nedir?",
        label_visibility="collapsed"
    )

    col1, col2 = st.columns(2)
    submit = col1.button("🚀 Submit", type="primary", use_container_width=True)
    clear = col2.button("🔄 Clear", use_container_width=True)

    if clear:
        st.session_state.query_input = ""
        st.rerun()

    if submit and query:
        process_query(query)

    if st.session_state.query_history:
        st.markdown("---")
        st.markdown("### 💭 Conversation")

        for item in reversed(st.session_state.query_history[-5:]):
            st.markdown(f"**👤 You:** {item['question']}")
            if item.get("success"):
                st.markdown(f"**🤖 Harmony AI:** {item['summary']}")
            else:
                st.error(f"❌ Error: {item['error']}")


# ------------------------------------------------------------
# QUERY PROCESSOR (FIXED)
# ------------------------------------------------------------
def process_query(query):

    sql_gen = st.session_state.sql_generator
    summarizer = st.session_state.summarizer

    with st.spinner("🤔 Analyzing your question..."):
        start = time.time()

        # ---------- INTENT ----------
        intent = sql_gen.intent_classifier.classify(query)

        if st.session_state.show_intent:
            with st.expander("🎯 Intent Classification"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Type", intent.get("query_type"))
                col2.metric("Complexity", f"{intent.get('complexity')}/10")
                col3.metric("Confidence", f"{intent.get('confidence')*100:.0f}%")

        # ---------- SQL ----------
        with st.spinner("⚙️ Generating SQL..."):
            sql = sql_gen.generate_sql(query)

        if st.session_state.show_sql:
            with st.expander("📝 Generated SQL", expanded=True):
                st.code(sql, language="sql")

        # ---------- EXECUTION ----------
        with st.spinner("⏳ Executing SQL..."):
            raw_results = execute_sql(sql)

        # *** FIX: Handle (results, exec_time) tuple ***
        if isinstance(raw_results, tuple) and len(raw_results) == 2:
            results, exec_time = raw_results
        else:
            results = raw_results
            exec_time = None

        # Error?
        if isinstance(results, dict) and "error" in results:
            st.error("❌ SQL Error: " + results["error"])
            return

        # Non-select
        if isinstance(results, dict) and "rowcount" in results:
            st.success(f"Query executed successfully. {results['rowcount']} rows affected.")
            return

        # ---------- SANITIZE RESULTS ----------
        safe_results = make_serializable(results)
        df = pd.DataFrame(safe_results)

        with st.expander("📊 Query Results", expanded=True):
            st.dataframe(df, width="stretch")

        # ---------- SUMMARY ----------
        with st.spinner("🧠 Generating business summary..."):
            summary = summarizer.summarize(
                user_question=query,
                sql_query=sql,
                query_results=safe_results,
                intent=intent,
                execution_time=exec_time
            )

        st.markdown("### 💡 Business Summary")
        st.markdown(summary)

        # ---------- VISUALIZATION ----------
        try:
            if st.session_state.auto_visualize and len(df) > 1:

                text_cols = [
                    col for col in df.columns
                    if df[col].dtype == "object" and df[col].apply(lambda x: isinstance(x, str)).all()
                ]

                numeric_cols = df.select_dtypes(include=["float", "int"]).columns

                if len(text_cols) > 0 and len(numeric_cols) > 0:
                    safe_df = df[[text_cols[0], numeric_cols[0]]]

                    st.markdown("### 📈 Visualization")
                    st.bar_chart(safe_df.set_index(text_cols[0])[numeric_cols[0]])

        except Exception as e:
            logger.warning(f"Visualization error: {e}")

        # ---------- SAVE HISTORY ----------
        elapsed = time.time() - start
        st.session_state.query_history.append({
            "question": query,
            "sql": sql,
            "summary": summary,
            "results_count": len(df),
            "execution_time": elapsed,
            "timestamp": datetime.now().isoformat(),
            "success": True
        })

        st.success(f"Completed in {elapsed:.2f}s")


# ------------------------------------------------------------
# ANALYTICS DASHBOARD
# ------------------------------------------------------------
def analytics_dashboard():

    st.markdown("### 📊 Analytics Dashboard")
    stats = st.session_state.query_logger.get_statistics()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Queries", stats.get("total_queries", 0))
    col2.metric("Success Rate", f"{stats.get('success_rate', 0)*100:.0f}%")
    col3.metric("Avg Complexity", f"{stats.get('avg_complexity', 0):.1f}/10")

    st.markdown("---")

    if stats.get("query_types"):
        df_types = pd.DataFrame(stats["query_types"].items(), columns=["Type", "Count"])
        st.bar_chart(df_types.set_index("Type"), width="stretch")


# ------------------------------------------------------------
# HISTORY VIEW
# ------------------------------------------------------------
def query_history_view():

    st.markdown("### 📚 Query History")

    history = st.session_state.query_history

    if not history:
        st.info("No queries yet.")
        return

    for row in reversed(history):
        with st.expander(f"{row['question']} — {row['timestamp'][:19]}"):
            st.write("**SQL:**")
            st.code(row["sql"], language="sql")
            st.write("**Summary:**", row["summary"])
            st.caption(f"{row['results_count']} rows | {row['execution_time']:.2f}s")


# ------------------------------------------------------------
# PATTERNS
# ------------------------------------------------------------
def patterns_view():

    st.markdown("### 🔍 Discovered Patterns")

    col1, col2 = st.columns([1, 3])

    with col1:
        refresh = st.button("🔄 Refresh Patterns", use_container_width=True)

    with col2:
        min_freq = st.number_input("Min Frequency", 2, 20, 3, step=1)

    miner = get_pattern_miner()

    if refresh or st.session_state.patterns_cache is None:
        patterns = miner.mine_patterns(min_frequency=min_freq, force_refresh=refresh)
        st.session_state.patterns_cache = patterns
        st.session_state.patterns_cache_time = time.time()
    else:
        patterns = st.session_state.patterns_cache

    if not patterns:
        st.info("⚠️ Not enough data for pattern mining.")
        return

    st.markdown(f"Found **{len(patterns)}** patterns")

    df = pd.json_normalize(patterns)
    st.dataframe(df, width="stretch")

    st.caption(
        f"Last updated: {datetime.fromtimestamp(st.session_state.patterns_cache_time).strftime('%H:%M:%S')}"
    )


# ------------------------------------------------------------
# UTILS (FINAL SERIALIZER)
# ------------------------------------------------------------
def make_serializable(result):
    """
    Make SQL results fully serializable.
    Fixes Decimal, dict, list formatting issues.
    Prevents Streamlit '[object Object]' error.
    """
    import decimal

    def fix(v):
        if isinstance(v, decimal.Decimal):
            return float(v)
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False)
        return v

    fixed_rows = []

    if isinstance(result, list):
        for row in result:
            fixed_rows.append({k: fix(v) for k, v in row.items()})

    elif isinstance(result, dict):
        fixed_rows.append({k: fix(v) for k, v in result.items()})

    else:
        fixed_rows.append({"value": str(result)})

    return fixed_rows


# ------------------------------------------------------------
# RUN
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
