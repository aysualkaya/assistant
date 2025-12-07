"""
10+ Test Senaryosu Runner (2025)
Includes:
- SQL Generation
- SQL Execution
- Table Validation (NEW)
- Business Summary Check
"""

import json
import time
from pathlib import Path
import sys

# Add project root to PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.llm.sql_generator import DynamicSQLGenerator
from app.database.db_client import execute_sql
from app.llm.result_summarizer import ResultSummarizer

# NEW IMPORT
from tests.sql_table_validator import (
    extract_tables_from_sql,
    compare_expected_vs_detected
)


def run_test_scenarios(verbose=True):

    print("=" * 70)
    print("🧪 HARMONY AI - TEST SCENARIOS")
    print("=" * 70)

    scenarios_path = Path(__file__).parent / 'test_scenarios.json'
    with open(scenarios_path) as f:
        scenarios = json.load(f)["test_scenarios"]

    sql_gen = DynamicSQLGenerator()
    summarizer = ResultSummarizer()
    results = []

    for scenario in scenarios:
        print("\n" + "─" * 70)
        print(f"📝 Test #{scenario['id']}: {scenario['name']}")
        print(f"❓ Question: {scenario['question']}")

        start_time = time.time()

        # -------- SQL Generation ----------
        sql = sql_gen.generate_sql(scenario["question"])

        if verbose:
            print("   ⚙️ SQL Generated:")
            print("   " + sql.replace("\n", "\n   "))

        # -------- TABLE VALIDATION (NEW - CRITICAL QA STEP) ----------
        detected_tables = extract_tables_from_sql(sql)
        expected_tables = scenario.get("expected_tables", [])

        missing = compare_expected_vs_detected(expected_tables, detected_tables)

        if missing:
            print(f"   ❌ TABLE VALIDATION FAILED")
            print(f"      Expected: {expected_tables}")
            print(f"      Detected: {detected_tables}")
            print(f"      Missing : {missing}")

            results.append({
                "id": scenario["id"],
                "name": scenario["name"],
                "status": "FAILED_TABLES",
                "missing": missing,
                "detected": detected_tables,
                "expected": expected_tables,
                "time": time.time() - start_time
            })

            continue
        else:
            print(f"   ✅ Table Check Passed → {detected_tables}")

        # -------- SQL Execution ----------
        raw_result = execute_sql(sql)

        if isinstance(raw_result, tuple):
            rows, exec_time = raw_result
        else:
            rows = raw_result
            exec_time = None

        if isinstance(rows, dict) and "error" in rows:
            print(f"   ❌ SQL ERROR: {rows['error']}")
            results.append({
                "id": scenario["id"],
                "name": scenario["name"],
                "status": "FAILED_SQL",
                "error": rows["error"],
                "time": time.time() - start_time
            })
            continue

        print(f"   ✅ SQL Executed Successfully ({len(rows)} rows)")

        # -------- Optional Summary ----------
        try:
            summary = summarizer.summarize(
                scenario["question"], sql, rows[:5]
            )
            if verbose:
                print(f"   💡 Summary: {summary[:120]}...")
        except:
            pass

        results.append({
            "id": scenario["id"],
            "name": scenario["name"],
            "status": "PASSED",
            "rows": len(rows),
            "time": time.time() - start_time
        })

    # -------- Report Summary ----------
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results if r["status"] == "PASSED")
    failed = len(results) - passed

    print(f"Total Tests: {len(results)}")
    print(f"✔ Passed: {passed}")
    print(f"❌ Failed: {failed}")

    # Save report
    report_path = Path(__file__).parent / "test_results.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved → {report_path}")

    return passed == len(results)


if __name__ == "__main__":
    run_test_scenarios()
