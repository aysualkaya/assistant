"""
🌐 Harmony AI - Web Interface (2025 Clean Edition)
Streamlit UI for Contoso Analytics Assistant
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime

from app.llm.sql_generator import DynamicSQLGenerator
from app.database.db_client import get_db_client
from app.llm.result_summarizer import ResultSummarizer
from app.memory.query_logger import QueryLogger
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Harmony AI - Contoso Analytics",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# SESSION STATE
# ============================================================
if "sql_gen" not in st.session_state:
    st.session_state.sql_gen = DynamicSQLGenerator()

if "summarizer" not in st.session_state:
    st.session_state.summarizer = ResultSummarizer()

if "query_logger" not in st.session_state:
    st.session_state.query_logger = QueryLogger()

if "query_history" not in st.session_state:
    st.session_state.query_history = []


db = get_db_client()


# ============================================================
# MAIN APP
# ============================================================
def main():
    st.markdown("<h1 style='text-align:center;'>🤖 Harmony AI – Contoso Analytics Assistant</h1>", unsafe_allow_html=True)

    with st.sidebar:
        sidebar()

    tab_chat, tab_analytics, tab_history = st.tabs([
        "💬 Chat",
        "📊 Analytics",
        "📚 History"
    ])

    with tab_chat:
        chat_ui()

    with tab_analytics:
        analytics_ui()

    with tab_history:
        history_ui()


# ============================================================
# SIDEBAR
# ============================================================
def sidebar():
    st.image(
        "https://assets.zyrosite.com/cdn-cgi/image/format=auto,w=560,fit=crop,q=95/dWxbjG54J4FrOnry/harmony-logo-gradient-YBg4yWLpRriXjwvG.png",
        width=260
    )

    st.markdown("---")

    stats = st.session_state.query_logger.get_statistics()
    st.metric("Total Queries", stats.get("total_queries", 0))
    st.metric("Success Rate", f"{stats.get('success_rate', 0)*100:.1f}%")
    st.metric("Avg Complexity", f"{stats.get('avg_complexity', 0):.1f}/10")

    st.markdown("---")
    st.markdown("### 💡 Example Questions")

    examples = [
        "2008 yılında toplam satış nedir?",
        "En çok satan 5 ürün hangisi?",
        "Mağaza vs online satış 2007",
        "2009 aylık satış trendi",
        "En az satan ürün nedir?"
    ]

    for q in examples:
        if st.button(q, use_container_width=True):
            st.session_state.query_input = q
            st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Options")
    st.session_state.show_sql = st.checkbox("Show SQL", True)
    st.session_state.show_intent = st.checkbox("Show Intent", True)
    st.session_state.auto_visualize = st.checkbox("Auto Visualization", True)

    if st.button("🗑 Clear History", use_container_width=True):
        st.session_state.query_history = []
        st.success("History cleared!")


# ============================================================
# CHAT UI
# ============================================================
def chat_ui():

    query = st.text_input(
        "Ask a business question:",
        key="query_input",
        placeholder="e.g., What are the top 5 selling products in 2008?"
    )

    col1, col2 = st.columns(2)
    submit = col1.button("🚀 Submit", use_container_width=True)
    clear = col2.button("🔄 Clear", use_container_width=True)

    if clear:
        st.session_state.query_input = ""
        st.rerun()

    if submit and query:
        process_query(query)

    # conversation preview
    if st.session_state.query_history:
        st.markdown("---")
        st.markdown("### 💭 Recent Conversation")

        for item in reversed(st.session_state.query_history[-4:]):
            st.write(f"**🧍 You:** {item['question']}")
            st.write(f"**🤖 Harmony AI:** {item['summary']}")


# ============================================================
# QUERY PROCESSING
# ============================================================
def process_query(query: str):
    sql_gen = st.session_state.sql_gen
    summarizer = st.session_state.summarizer
    logger.info(f"Processing: {query}")

    start = time.time()

    # -------- INTENT --------
    intent = sql_gen.intent_classifier.classify(query)

    if st.session_state.show_intent:
        with st.expander("🎯 Intent"):
            st.json(intent)

    # -------- SQL --------
    with st.spinner("Generating SQL..."):
        sql = sql_gen.generate_sql(query)

    if st.session_state.show_sql:
        with st.expander("📝 SQL"):
            st.code(sql, language="sql")

    # -------- RUN QUERY --------
    with st.spinner("Executing SQL..."):
        rows, exec_time = db.execute_query(sql)

    if rows and "error" in rows[0]:
        st.error("❌ SQL Execution Error: " + rows[0]["error"])
        return

    df = pd.DataFrame(rows)

    with st.expander("📊 Results", expanded=True):
        st.dataframe(df, height=380)

    # -------- SUMMARY --------
    with st.spinner("Generating Summary..."):
        summary = summarizer.summarize(
            user_question=query,
            sql_query=sql,
            query_results=rows,
            intent=intent,
            execution_time=exec_time
        )

    st.markdown("### 💡 Business Summary")
    st.write(summary)

    # -------- VISUALIZATION --------
    if st.session_state.auto_visualize and len(df) > 1:
        try:
            numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns
            text_cols = df.select_dtypes(include=["object"]).columns

            if len(numeric_cols) > 0 and len(text_cols) > 0:
                st.markdown("### 📈 Visualization")
                st.bar_chart(df.set_index(text_cols[0])[numeric_cols[0]])
        except Exception as e:
            logger.warning(f"Visualization error: {e}")

    # -------- HISTORY --------
    st.session_state.query_history.append({
        "question": query,
        "sql": sql,
        "summary": summary,
        "timestamp": datetime.now().isoformat()
    })

    st.success(f"Completed in {time.time()-start:.2f}s")


# ============================================================
# ANALYTICS
# ============================================================
def analytics_ui():
    st.markdown("### 📊 Query Analytics")

    stats = st.session_state.query_logger.get_statistics()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Queries", stats["total_queries"])
    col2.metric("Success Rate", f"{stats['success_rate']*100:.1f}%")
    col3.metric("Avg Complexity", f"{stats['avg_complexity']:.1f}/10")

    if stats.get("query_types"):
        df = pd.DataFrame(stats["query_types"].items(), columns=["Type", "Count"])
        st.bar_chart(df.set_index("Type"))


# ============================================================
# HISTORY UI
# ============================================================
def history_ui():
    st.markdown("### 📚 Query History")

    hist = st.session_state.query_history

    if not hist:
        st.info("No history yet.")
        return

    for item in reversed(hist):
        with st.expander(f"{item['question']} – {item['timestamp'][:19]}"):
            st.code(item["sql"], language="sql")
            st.write(item["summary"])


# ============================================================
# RUN APP
# ============================================================
if __name__ == "__main__":
    main()
