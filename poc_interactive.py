# poc_interactive.py - CLEAN & MINIMAL (2025)
"""
Harmony AI - Contoso Analytics (Interactive PoC)
Simple terminal-based sandbox for:
- SQL Generation
- SQL Execution
- Business Summary (TR/EN)
"""

import json
import decimal
import time

from app.llm.sql_generator import DynamicSQLGenerator
from app.database.db_client import execute_sql
from app.llm.result_summarizer import ResultSummarizer
from app.memory.query_logger import QueryLogger
from app.utils.logger import get_logger

logger = get_logger(__name__)


def make_serializable(result):
    """Convert Decimal → float for printing"""
    if isinstance(result, list):
        return [
            {k: float(v) if isinstance(v, decimal.Decimal) else v for k, v in row.items()}
            for row in result
        ]
    return result


def print_banner():
    print("""
╔════════════════════════════════════════════╗
║  🤖 Harmony AI - Contoso Analytics PoC     ║
╚════════════════════════════════════════════╝

Examples:
 - 2008 yılında toplam satış nedir?
 - En çok satan 5 ürün hangisi?
 - Store vs online karşılaştırması 2009
 - 2008 monthly sales trend
Type 'exit' to quit.
""")


def run_poc():

    print_banner()

    sql_gen = DynamicSQLGenerator()
    summarizer = ResultSummarizer()
    logger_q = QueryLogger()

    while True:
        q = input("\n💬 Question: ").strip()

        if q.lower() in ["exit", "quit", "q"]:
            print("\n👋 Exiting. Goodbye!\n")
            break

        try:
            print("\n⚙️ Generating SQL...")
            sql = sql_gen.generate_sql(q)

            print("\n📝 SQL:")
            print(sql)
            print("-" * 60)

            print("\n⏳ Running SQL...")
            t0 = time.time()
            rows = execute_sql(sql)
            exec_time = time.time() - t0

            rows_serializable = make_serializable(rows)

            print("\n📊 RESULTS:")
            if len(rows_serializable) == 0:
                print("No results.")
            else:
                print(json.dumps(rows_serializable[:10], indent=2, ensure_ascii=False))
                if len(rows_serializable) > 10:
                    print(f"... ({len(rows_serializable)} total rows)")

            print(f"\n⏱ Execution time: {exec_time:.2f}s")

            # summary
            intent = sql_gen.intent_classifier.classify(q)
            summary = summarizer.summarize(
                user_question=q,
                sql_query=sql,
                query_results=rows_serializable,
                intent=intent,
                execution_time=exec_time
            )

            print("\n💡 SUMMARY:")
            print(summary)

            # log query
            logger_q.log_query(
                question=q,
                sql=sql,
                intent=intent,
                strategy="poc",
                success=True,
                execution_time=exec_time,
                results_count=len(rows_serializable)
            )

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            logger.error(f"PoC error: {e}", exc_info=True)

            intent = sql_gen.intent_classifier.classify(q)
            logger_q.log_query(
                question=q,
                sql=None,
                intent=intent,
                strategy="poc",
                success=False,
                error=str(e)
            )


if __name__ == "__main__":
    run_poc()
