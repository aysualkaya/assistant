# poc_interactive.py - ENHANCED VERSION
"""
🤖 Harmony AI - Contoso LLM Analytics Assistant
Enhanced Interactive PoC with Dynamic LLM-First Architecture

FEATURES:
- Dynamic intent classification
- LLM-first SQL generation with multiple strategies
- Query learning and pattern mining
- Enhanced result analysis
- Performance metrics
"""

import json
import decimal
import pandas as pd
import time
from typing import Dict, Any

from app.core.config import Config
from app.llm.sql_generator import DynamicSQLGenerator
from app.database.db_client import execute_sql
from app.llm.result_summarizer import ResultSummarizer
from app.visualization.visualizer import Visualizer
from app.memory.query_logger import QueryLogger
from app.memory.pattern_miner import PatternMiner
from app.utils.logger import get_logger

logger = get_logger(__name__)


def decimal_to_float(obj):
    """JSON Decimal to float converter"""
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError


def make_serializable(result):
    """Convert Decimal values to float for JSON serialization"""
    if isinstance(result, list):
        return [{k: float(v) if isinstance(v, decimal.Decimal) else v 
                for k, v in row.items()} if isinstance(row, dict) else row 
                for row in result]
    elif isinstance(result, dict):
        return {k: float(v) if isinstance(v, decimal.Decimal) else v 
                for k, v in result.items()}
    return result


def print_banner():
    """Print application banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║      🤖 Harmony AI - Contoso Analytics Assistant            ║
║                                                              ║
║      Dynamic LLM-First Architecture                         ║
║      Powered by Intent Classification & Pattern Learning    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    
    print("\n🚀 FEATURES:")
    print("   ✨ Dynamic intent-based strategy selection")
    print("   🧠 LLM-first SQL generation")
    print("   📚 Few-shot learning from query history")
    print("   🔍 Intelligent validation & self-correction")
    print("   📊 Enhanced business summaries in Turkish")
    print("   📈 Automatic visualization recommendations")
    print("   🎯 Query learning & pattern mining")
    
    print("\n📊 Available data years: 2007, 2008, 2009")
    print("\n💡 EXAMPLE QUESTIONS:")
    print("   • '2008 yılında toplam satış miktarı nedir?'")
    print("   • '2009 yılında en çok satan 5 ürün hangisi?'")
    print("   • 'mağaza vs online satış karşılaştırması 2007'")
    print("   • '2007 yılı aylık satış trendini göster'")
    print("   • 'en az satan ürün hangisi?'")
    print("   • 'hangi kategoride en yüksek satış var?'")
    
    print("\n📋 COMMANDS:")
    print("   • 'stats' - View query statistics")
    print("   • 'patterns' - Show discovered patterns")
    print("   • 'metrics' - Show LLM performance metrics")
    print("   • 'clear' - Clear screen")
    print("   • 'exit' - Quit application")
    print("\n" + "="*70 + "\n")


def run_poc():
    """Main PoC application loop"""
    
    # Print banner
    print_banner()
    
    # Initialize services
    sql_generator = DynamicSQLGenerator()
    summarizer = ResultSummarizer()
    visualizer = Visualizer()
    query_logger = QueryLogger()
    pattern_miner = PatternMiner()
    
    # Session statistics
    session_stats = {
        "queries_executed": 0,
        "successful_queries": 0,
        "failed_queries": 0,
        "total_execution_time": 0.0
    }
    
    while True:
        try:
            # Get user question
            user_question = input("\n💬 Your Question: ").strip()
            
            if not user_question:
                continue
            
            # Handle commands
            if user_question.lower() in ["exit", "quit", "çıkış", "q"]:
                print("\n" + "="*70)
                print("📊 SESSION SUMMARY:")
                print(f"   Total queries: {session_stats['queries_executed']}")
                print(f"   Successful: {session_stats['successful_queries']}")
                print(f"   Failed: {session_stats['failed_queries']}")
                print(f"   Success rate: {session_stats['successful_queries']/max(session_stats['queries_executed'],1)*100:.1f}%")
                print(f"   Total time: {session_stats['total_execution_time']:.2f}s")
                print("\n👋 Thank you for using Harmony AI!")
                print("="*70 + "\n")
                break
            
            if user_question.lower() == "stats":
                show_statistics(query_logger)
                continue
            
            if user_question.lower() == "patterns":
                show_patterns(pattern_miner)
                continue
            
            if user_question.lower() == "metrics":
                show_metrics(sql_generator)
                continue
            
            if user_question.lower() == "clear":
                import os
                os.system('cls' if os.name == 'nt' else 'clear')
                print_banner()
                continue
            
            # Process query
            session_stats["queries_executed"] += 1
            start_time = time.time()
            
            try:
                # Generate SQL
                print("\n⚙️  Generating SQL...")
                sql_query = sql_generator.generate_sql(user_question)
                
                print("\n📝 GENERATED SQL:")
                print("─" * 70)
                print(sql_query)
                print("─" * 70)
                
                # Execute SQL
                print("\n⏳ Executing SQL...")
                exec_start = time.time()
                results = execute_sql(sql_query)
                exec_time = time.time() - exec_start
                
                # Check for execution errors
                if isinstance(results, dict) and "error" in results:
                    print(f"\n❌ SQL EXECUTION ERROR: {results['error']}")
                    session_stats["failed_queries"] += 1
                    continue
                
                # Process results
                results_serializable = make_serializable(results)
                
                print("\n📊 QUERY RESULTS:")
                print("=" * 70)
                
                if isinstance(results_serializable, list):
                    if len(results_serializable) == 0:
                        print("❌ No results found.")
                    elif len(results_serializable) <= 10:
                        print(json.dumps(results_serializable, indent=2, ensure_ascii=False))
                    else:
                        print(f"📈 Total {len(results_serializable)} rows found.")
                        print("\n📍 First 5 rows:")
                        print(json.dumps(results_serializable[:5], indent=2, ensure_ascii=False))
                        print(f"\n... ({len(results_serializable) - 10} more rows) ...")
                        print("\n📍 Last 5 rows:")
                        print(json.dumps(results_serializable[-5:], indent=2, ensure_ascii=False))
                else:
                    print(json.dumps(results_serializable, indent=2, ensure_ascii=False))
                
                print("=" * 70)
                
                # Generate summary
                print("\n🧠 GENERATING BUSINESS SUMMARY...")
                
                # Get intent for context-aware summary
                intent = sql_generator.intent_classifier.classify(user_question)
                
                summary = summarizer.summarize(
                    user_question=user_question,
                    sql_query=sql_query,
                    query_results=results_serializable,
                    intent=intent,
                    execution_time=exec_time
                )
                
                print("\n💡 BUSINESS SUMMARY:")
                print("=" * 70)
                print(summary)
                print("=" * 70)
                
                # Visualization (if applicable)
                if results_serializable and isinstance(results_serializable, list) and len(results_serializable) > 1:
                    if intent.get("query_type") in ["ranking", "trend", "comparison"]:
                        try:
                            df = pd.DataFrame(results_serializable)
                            numeric_cols = df.select_dtypes(include=['float64', 'int64', 'int32']).columns.tolist()
                            text_cols = df.select_dtypes(include=['object']).columns.tolist()
                            
                            if numeric_cols and text_cols:
                                print("\n📊 Generating visualization...")
                                x_col = text_cols[0]
                                y_col = numeric_cols[0]
                                
                                # Limit to top 10 for clarity
                                plot_df = df.nlargest(10, y_col) if len(df) > 10 else df
                                
                                title = f"{user_question[:40]}..." if len(user_question) > 40 else user_question
                                visualizer.plot_matplotlib(plot_df, x_col, y_col, title)
                                print("✅ Visualization displayed")
                        except Exception as viz_error:
                            logger.warning(f"Visualization error: {viz_error}")
                
                # Update statistics
                total_time = time.time() - start_time
                session_stats["successful_queries"] += 1
                session_stats["total_execution_time"] += total_time
                
                # Log successful query
                query_logger.log_query(
                    question=user_question,
                    sql=sql_query,
                    intent=intent,
                    strategy="dynamic",
                    success=True,
                    execution_time=total_time,
                    results_count=len(results_serializable) if isinstance(results_serializable, list) else 1
                )
                
                print(f"\n✅ Query completed in {total_time:.2f}s")
                
            except Exception as e:
                print(f"\n❌ Error: {e}")
                logger.error(f"Query processing error: {e}", exc_info=True)
                session_stats["failed_queries"] += 1
                
                # Log failed query
                intent = sql_generator.intent_classifier.classify(user_question)
                query_logger.log_query(
                    question=user_question,
                    sql=None,
                    intent=intent,
                    strategy="dynamic",
                    success=False,
                    error=str(e)
                )
        
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Exiting...")
            break
        
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            logger.error(f"Unexpected error: {e}", exc_info=True)


def show_statistics(query_logger: QueryLogger):
    """Show query statistics"""
    stats = query_logger.get_statistics()
    
    print("\n" + "="*70)
    print("📊 QUERY STATISTICS")
    print("="*70)
    print(f"Total queries: {stats['total_queries']}")
    print(f"Successful: {stats['successful_queries']}")
    print(f"Failed: {stats['failed_queries']}")
    print(f"Success rate: {stats['success_rate']*100:.1f}%")
    print(f"Average complexity: {stats['avg_complexity']:.1f}/10")
    
    print("\n📋 Query Types:")
    for qtype, count in stats.get('query_types', {}).items():
        print(f"  • {qtype}: {count}")
    
    print("\n🎯 Strategies Used:")
    for strategy, count in stats.get('strategies', {}).items():
        print(f"  • {strategy}: {count}")
    
    print("="*70)


def show_patterns(pattern_miner: PatternMiner):
    """Show discovered patterns"""
    patterns = pattern_miner.mine_patterns(min_frequency=2)
    
    print("\n" + "="*70)
    print("🔍 DISCOVERED PATTERNS")
    print("="*70)
    
    if not patterns:
        print("No patterns discovered yet. Ask more questions to build history!")
    else:
        for i, pattern in enumerate(patterns[:10], 1):
            print(f"\n{i}. {pattern.get('type', 'unknown').upper()}")
            print(f"   Frequency: {pattern.get('frequency', 0)}")
            
            if pattern.get('type') == 'query_type_pattern':
                print(f"   Query type: {pattern.get('query_type')}")
                print(f"   Common keywords: {', '.join(pattern.get('common_keywords', [])[:5])}")
            
            elif pattern.get('type') == 'table_combination':
                print(f"   Tables: {', '.join(pattern.get('tables', []))}")
                print(f"   Usage: {pattern.get('percentage', 0):.1f}%")
    
    print("="*70)


def show_metrics(sql_generator: DynamicSQLGenerator):
    """Show LLM performance metrics"""
    sql_generator.llm.log_metrics()


if __name__ == "__main__":
    try:
        run_poc()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"❌ Critical error: {e}")