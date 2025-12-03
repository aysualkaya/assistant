# poc_streamlit.py
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
from app.memory.pattern_miner import PatternMiner
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Page configuration
st.set_page_config(
    page_title="Harmony AI - Contoso Analytics",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .sql-box {
        background-color: #282c34;
        color: #abb2bf;
        padding: 1rem;
        border-radius: 5px;
        font-family: 'Courier New', monospace;
        overflow-x: auto;
    }
</style>
""", unsafe_allow_html=True)


# Initialize session state
if 'query_history' not in st.session_state:
    st.session_state.query_history = []

if 'sql_generator' not in st.session_state:
    st.session_state.sql_generator = DynamicSQLGenerator()

if 'summarizer' not in st.session_state:
    st.session_state.summarizer = ResultSummarizer()

if 'query_logger' not in st.session_state:
    st.session_state.query_logger = QueryLogger()

if 'pattern_miner' not in st.session_state:
    st.session_state.pattern_miner = PatternMiner()


def main():
    """Main application"""
    
    # Header
    st.markdown('<div class="main-header">🤖 Harmony AI - Contoso Analytics Assistant</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://assets.zyrosite.com/cdn-cgi/image/format=auto,w=560,fit=crop,q=95/dWxbjG54J4FrOnry/harmony-logo-gradient-YBg4yWLpRriXjwvG.png", use_container_width=True)
        
        st.markdown("---")
        st.markdown("### 📊 Quick Stats")
        
        stats = st.session_state.query_logger.get_statistics()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Queries", stats.get('total_queries', 0))
            st.metric("Success Rate", f"{stats.get('success_rate', 0)*100:.1f}%")
        
        with col2:
            st.metric("Successful", stats.get('successful_queries', 0))
            st.metric("Failed", stats.get('failed_queries', 0))
        
        st.markdown("---")
        st.markdown("### 🎯 Features")
        st.markdown("""
        - ✨ Dynamic intent classification
        - 🧠 LLM-first SQL generation
        - 📚 Few-shot learning
        - 🔍 Auto-correction
        - 📊 Business summaries
        - 📈 Auto visualization
        """)
        
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
        
        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            show_sql = st.checkbox("Show Generated SQL", value=True)
            show_intent = st.checkbox("Show Intent Classification", value=True)
            show_execution_time = st.checkbox("Show Execution Time", value=True)
            auto_visualize = st.checkbox("Auto Visualization", value=True)
            
            st.session_state.show_sql = show_sql
            st.session_state.show_intent = show_intent
            st.session_state.show_execution_time = show_execution_time
            st.session_state.auto_visualize = auto_visualize
        
        st.markdown("---")
        
        # View patterns
        if st.button("🔍 View Patterns", use_container_width=True):
            st.session_state.show_patterns = True
        
        # Clear history
        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state.query_history = []
            st.success("History cleared!")
    
    # Main content
    tabs = st.tabs(["💬 Chat", "📊 Analytics", "📚 History", "🔍 Patterns"])
    
    # Tab 1: Chat Interface
    with tabs[0]:
        chat_interface()
    
    # Tab 2: Analytics
    with tabs[1]:
        analytics_dashboard()
    
    # Tab 3: History
    with tabs[2]:
        query_history_view()
    
    # Tab 4: Patterns
    with tabs[3]:
        patterns_view()


def chat_interface():
    """Main chat interface"""
    
    st.markdown("### 💬 Ask Your Question")
    
    # Query input
    query = st.text_input(
        "Enter your business question:",
        placeholder="e.g., 2008 yılında toplam satış miktarı nedir?",
        key="query_input",
        label_visibility="collapsed"
    )
    
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        submit = st.button("🚀 Submit", type="primary", use_container_width=True)
    
    with col2:
        clear = st.button("🔄 Clear", use_container_width=True)
    
    if clear:
        st.session_state.query_input = ""
        st.rerun()
    
    if submit and query:
        process_query(query)
    
    # Display conversation history
    if st.session_state.query_history:
        st.markdown("---")
        st.markdown("### 💭 Conversation")
        
        for item in reversed(st.session_state.query_history[-5:]):  # Last 5
            with st.container():
                st.markdown(f"**👤 You:** {item['question']}")
                
                if item.get('success'):
                    st.markdown(f"**🤖 Harmony AI:**")
                    st.markdown(item['summary'])
                    
                    if st.session_state.get('show_execution_time'):
                        st.caption(f"⏱️ Completed in {item.get('execution_time', 0):.2f}s")
                else:
                    st.error(f"❌ Error: {item.get('error', 'Unknown error')}")
                
                st.markdown("---")


def process_query(query: str):
    """Process user query"""
    
    with st.spinner("🤔 Analyzing your question..."):
        start_time = time.time()
        
        try:
            # Generate SQL
            sql_generator = st.session_state.sql_generator
            
            # Show intent if enabled
            if st.session_state.get('show_intent', True):
                intent = sql_generator.intent_classifier.classify(query)
                
                with st.expander("🎯 Intent Classification", expanded=False):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Query Type", intent.get('query_type', 'N/A'))
                    with col2:
                        st.metric("Complexity", f"{intent.get('complexity', 0)}/10")
                    with col3:
                        st.metric("Confidence", f"{intent.get('confidence', 0)*100:.0f}%")
                    with col4:
                        strategy = "Direct" if intent.get('complexity', 5) <= 3 else "Few-Shot" if intent.get('complexity', 5) <= 7 else "CoT"
                        st.metric("Strategy", strategy)
                    
                    st.caption(f"**Tables needed:** {', '.join(intent.get('tables_needed', []))}")
            
            # Generate SQL
            with st.spinner("⚙️ Generating SQL..."):
                sql = sql_generator.generate_sql(query)
            
            # Show SQL if enabled
            if st.session_state.get('show_sql', True):
                with st.expander("📝 Generated SQL", expanded=True):
                    st.code(sql, language="sql")
            
            # Execute SQL
            with st.spinner("⏳ Executing query..."):
                results = execute_sql(sql)
            
            if isinstance(results, dict) and "error" in results:
                st.error(f"❌ SQL Execution Error: {results['error']}")
                
                # Log failed query
                st.session_state.query_logger.log_query(
                    question=query,
                    sql=sql,
                    intent=intent,
                    strategy="streamlit",
                    success=False,
                    error=results['error']
                )
                
                return
            
            # Convert results
            results_serializable = make_serializable(results)
            
            # Display results
            st.success("✅ Query executed successfully!")
            
            with st.expander("📊 Query Results", expanded=True):
                if isinstance(results_serializable, list) and len(results_serializable) > 0:
                    df = pd.DataFrame(results_serializable)
                    st.dataframe(df, use_container_width=True)
                    
                    # Download button
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "📥 Download CSV",
                        csv,
                        "query_results.csv",
                        "text/csv",
                        key='download-csv'
                    )
                else:
                    st.warning("No results found")
            
            # Generate summary
            with st.spinner("🧠 Generating business summary..."):
                summary = st.session_state.summarizer.summarize(
                    user_question=query,
                    sql_query=sql,
                    query_results=results_serializable,
                    intent=intent
                )
            
            # Display summary
            st.markdown("### 💡 Business Summary")
            st.markdown(summary)
            
            # Visualization
            if st.session_state.get('auto_visualize', True) and isinstance(results_serializable, list) and len(results_serializable) > 1:
                try:
                    df = pd.DataFrame(results_serializable)
                    numeric_cols = df.select_dtypes(include=['float64', 'int64', 'int32']).columns.tolist()
                    text_cols = df.select_dtypes(include=['object']).columns.tolist()
                    
                    if numeric_cols and text_cols:
                        st.markdown("### 📈 Visualization")
                        
                        chart_type = st.selectbox(
                            "Chart Type",
                            ["Bar Chart", "Line Chart", "Area Chart"],
                            key="chart_type"
                        )
                        
                        x_col = text_cols[0]
                        y_col = numeric_cols[0]
                        
                        plot_df = df.nlargest(10, y_col) if len(df) > 10 else df
                        
                        if chart_type == "Bar Chart":
                            st.bar_chart(plot_df.set_index(x_col)[y_col])
                        elif chart_type == "Line Chart":
                            st.line_chart(plot_df.set_index(x_col)[y_col])
                        else:
                            st.area_chart(plot_df.set_index(x_col)[y_col])
                
                except Exception as viz_error:
                    logger.warning(f"Visualization error: {viz_error}")
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Add to history
            st.session_state.query_history.append({
                'question': query,
                'sql': sql,
                'results_count': len(results_serializable) if isinstance(results_serializable, list) else 1,
                'summary': summary,
                'execution_time': execution_time,
                'timestamp': datetime.now().isoformat(),
                'success': True
            })
            
            # Log successful query
            st.session_state.query_logger.log_query(
                question=query,
                sql=sql,
                intent=intent,
                strategy="streamlit",
                success=True,
                execution_time=execution_time,
                results_count=len(results_serializable) if isinstance(results_serializable, list) else 1
            )
            
            if st.session_state.get('show_execution_time', True):
                st.info(f"⏱️ Query completed in {execution_time:.2f} seconds")
        
        except Exception as e:
            st.error(f"❌ Error: {e}")
            logger.error(f"Query processing error: {e}", exc_info=True)
            
            # Add to history
            st.session_state.query_history.append({
                'question': query,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'success': False
            })


def analytics_dashboard():
    """Analytics dashboard"""
    
    st.markdown("### 📊 Analytics Dashboard")
    
    stats = st.session_state.query_logger.get_statistics()
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Queries",
            stats.get('total_queries', 0),
            delta=None
        )
    
    with col2:
        st.metric(
            "Success Rate",
            f"{stats.get('success_rate', 0)*100:.1f}%",
            delta=None
        )
    
    with col3:
        st.metric(
            "Avg Complexity",
            f"{stats.get('avg_complexity', 0):.1f}/10",
            delta=None
        )
    
    with col4:
        st.metric(
            "Successful",
            stats.get('successful_queries', 0),
            delta=None
        )
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Query Types Distribution")
        if stats.get('query_types'):
            df_types = pd.DataFrame(
                list(stats['query_types'].items()),
                columns=['Type', 'Count']
            )
            st.bar_chart(df_types.set_index('Type'))
        else:
            st.info("No data yet")
    
    with col2:
        st.markdown("#### Strategies Used")
        if stats.get('strategies'):
            df_strategies = pd.DataFrame(
                list(stats['strategies'].items()),
                columns=['Strategy', 'Count']
            )
            st.bar_chart(df_strategies.set_index('Strategy'))
        else:
            st.info("No data yet")


def query_history_view():
    """Query history view"""
    
    st.markdown("### 📚 Query History")
    
    if not st.session_state.query_history:
        st.info("No queries yet. Start asking questions!")
        return
    
    # Filters
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search = st.text_input("🔍 Search queries", "")
    
    with col2:
        filter_success = st.selectbox(
            "Filter",
            ["All", "Successful", "Failed"]
        )
    
    # Filter history
    filtered_history = st.session_state.query_history
    
    if search:
        filtered_history = [
            h for h in filtered_history
            if search.lower() in h['question'].lower()
        ]
    
    if filter_success == "Successful":
        filtered_history = [h for h in filtered_history if h.get('success')]
    elif filter_success == "Failed":
        filtered_history = [h for h in filtered_history if not h.get('success')]
    
    # Display history
    st.markdown(f"**Showing {len(filtered_history)} queries**")
    
    for i, item in enumerate(reversed(filtered_history)):
        with st.expander(
            f"{'✅' if item.get('success') else '❌'} {item['question'][:60]}... - {item['timestamp'][:19]}"
        ):
            st.markdown(f"**Question:** {item['question']}")
            
            if item.get('success'):
                if item.get('sql'):
                    st.code(item['sql'], language="sql")
                
                st.markdown(f"**Summary:** {item.get('summary', 'N/A')}")
                st.caption(f"Results: {item.get('results_count', 0)} rows | Time: {item.get('execution_time', 0):.2f}s")
            else:
                st.error(f"Error: {item.get('error', 'Unknown error')}")


def patterns_view():
    """Patterns view"""
    
    st.markdown("### 🔍 Discovered Patterns")
    
    patterns = st.session_state.pattern_miner.mine_patterns(min_frequency=2)
    
    if not patterns:
        st.info("Not enough queries to discover patterns. Keep asking questions!")
        return
    
    st.markdown(f"**Found {len(patterns)} patterns**")
    
    # Group by pattern type
    pattern_types = {}
    for pattern in patterns:
        ptype = pattern.get('type', 'unknown')
        if ptype not in pattern_types:
            pattern_types[ptype] = []
        pattern_types[ptype].append(pattern)
    
    # Display patterns
    for ptype, plist in pattern_types.items():
        st.markdown(f"#### {ptype.replace('_', ' ').title()}")
        
        for pattern in plist:
            with st.expander(f"Frequency: {pattern.get('frequency', 0)} times"):
                st.json(pattern)


def make_serializable(result):
    """Convert Decimal values to float"""
    import decimal
    
    if isinstance(result, list):
        return [{k: float(v) if isinstance(v, decimal.Decimal) else v 
                for k, v in row.items()} if isinstance(row, dict) else row 
                for row in result]
    elif isinstance(result, dict):
        return {k: float(v) if isinstance(v, decimal.Decimal) else v 
                for k, v in result.items()}
    return result


if __name__ == "__main__":
    main()