# tests/run_test_scenarios.py
"""
10+ Test Senaryosu Runner
Gereksinim 4: "En az 10 test senaryosu ve örnek iş sorusu oluşturma"
"""

import json
import time
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.llm.sql_generator import DynamicSQLGenerator
from app.database.db_client import execute_sql
from app.llm.result_summarizer import ResultSummarizer


def run_test_scenarios(verbose=True):
    """
    Run all test scenarios and generate report
    
    Args:
        verbose: Print detailed output
    """
    print("="*70)
    print("🧪 HARMONY AI - TEST SCENARIOS")
    print("="*70)
    print("\nRunning 10+ test scenarios as per project requirements...")
    print()
    
    # Load scenarios
    scenarios_path = Path(__file__).parent / 'test_scenarios.json'
    with open(scenarios_path) as f:
        data = json.load(f)
        scenarios = data['test_scenarios']
    
    # Initialize
    sql_gen = DynamicSQLGenerator()
    summarizer = ResultSummarizer()
    
    results = []
    
    # Run each scenario
    for scenario in scenarios:
        print(f"\n{'─'*70}")
        print(f"📝 Test #{scenario['id']}: {scenario['name']}")
        print(f"❓ Question: {scenario['question']}")
        print(f"📂 Category: {scenario['category']}")
        
        start_time = time.time()
        
        try:
            # Generate SQL
            if verbose:
                print("   ⚙️  Generating SQL...")
            
            sql = sql_gen.generate_sql(scenario['question'])
            
            if verbose:
                print(f"   ✅ SQL Generated")
                print(f"   📝 SQL Preview: {sql[:100]}...")
            
            # Execute SQL
            if verbose:
                print("   ⏳ Executing...")
            
            result = execute_sql(sql)
            
            # Check result
            if isinstance(result, dict) and 'error' in result:
                print(f"   ❌ FAILED: {result['error'][:100]}")
                results.append({
                    'id': scenario['id'],
                    'name': scenario['name'],
                    'status': 'FAILED',
                    'error': result['error'],
                    'time': time.time() - start_time
                })
            else:
                row_count = len(result) if isinstance(result, list) else 1
                print(f"   ✅ PASSED ({row_count} rows, {time.time()-start_time:.2f}s)")
                
                # Generate summary (optional)
                if verbose and isinstance(result, list) and len(result) > 0:
                    try:
                        summary = summarizer.summarize(
                            scenario['question'],
                            sql,
                            result[:5]  # First 5 rows only
                        )
                        print(f"   💡 Summary: {summary[:100]}...")
                    except:
                        pass
                
                results.append({
                    'id': scenario['id'],
                    'name': scenario['name'],
                    'status': 'PASSED',
                    'rows': row_count,
                    'time': time.time() - start_time
                })
        
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)[:100]}")
            results.append({
                'id': scenario['id'],
                'name': scenario['name'],
                'status': 'ERROR',
                'error': str(e),
                'time': time.time() - start_time
            })
    
    # Print Summary
    print(f"\n{'='*70}")
    print("📊 TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for r in results if r['status'] == 'PASSED')
    failed = sum(1 for r in results if r['status'] == 'FAILED')
    errors = sum(1 for r in results if r['status'] == 'ERROR')
    total = len(results)
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"❌ Failed: {failed} ({failed/total*100:.1f}%)")
    print(f"⚠️  Errors: {errors} ({errors/total*100:.1f}%)")
    
    avg_time = sum(r['time'] for r in results) / len(results)
    print(f"\n⏱️  Average Time: {avg_time:.2f}s per test")
    
    # Detailed results
    if failed > 0 or errors > 0:
        print(f"\n{'─'*70}")
        print("❌ FAILED/ERROR TESTS:")
        for r in results:
            if r['status'] != 'PASSED':
                print(f"\n  Test #{r['id']}: {r['name']}")
                print(f"  Status: {r['status']}")
                if 'error' in r:
                    print(f"  Error: {r['error'][:200]}")
    
    # Save results
    results_path = Path(__file__).parent / 'test_results.json'
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'success_rate': passed/total*100,
                'avg_time': avg_time
            },
            'results': results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {results_path}")
    print("="*70)
    
    return passed == total


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run test scenarios')
    parser.add_argument('--quiet', action='store_true', help='Minimal output')
    args = parser.parse_args()
    
    success = run_test_scenarios(verbose=not args.quiet)
    
    sys.exit(0 if success else 1)