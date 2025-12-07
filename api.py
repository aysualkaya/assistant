# api.py
"""
🌐 Harmony AI - REST API
FastAPI backend for Contoso Analytics Assistant
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
from datetime import datetime

from app.llm.sql_generator import DynamicSQLGenerator
from app.database.db_client import execute_sql
from app.llm.result_summarizer import ResultSummarizer
from app.memory.query_logger import QueryLogger
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Initialize FastAPI app
app = FastAPI(
    title="Harmony AI - Contoso Analytics API",
    description="LLM-powered Analytics Assistant API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict origins for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services (singletons for the process)
sql_generator = DynamicSQLGenerator()
summarizer = ResultSummarizer()
query_logger = QueryLogger()


# -------------------------------------------------------------
# Request / Response Models
# -------------------------------------------------------------
class QueryRequest(BaseModel):
    question: str
    include_sql: bool = True
    include_intent: bool = True
    include_visualization: bool = False  # reserved for future use
    max_results: Optional[int] = 100


class QueryResponse(BaseModel):
    success: bool
    question: str
    intent: Optional[Dict] = None
    sql: Optional[str] = None
    results: Optional[List[Dict]] = None
    results_count: int
    summary: str
    execution_time: float
    timestamp: str
    error: Optional[str] = None


class StatsResponse(BaseModel):
    total_queries: int
    successful_queries: int
    failed_queries: int
    success_rate: float
    avg_complexity: float
    query_types: Dict[str, int]
    strategies: Dict[str, int]


# -------------------------------------------------------------
# Root & Health
# -------------------------------------------------------------
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Harmony AI - Contoso Analytics API",
        "version": "2.0.0",
        "status": "operational",
        "features": [
            "Rule-based intent classification",
            "LangChain-assisted schema-aware SQL generation",
            "Template engine for common queries",
            "LLM SQL self-correction with OpenAI fallback",
            "Executive business summaries (TR + EN)",
            "Query logging & statistics"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# -------------------------------------------------------------
# Main query endpoint
# -------------------------------------------------------------
@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Process a natural language query:
    - Classify intent
    - Generate SQL (template → LLM)
    - Execute SQL on ContosoRetailDW
    - Generate TR/EN business summary
    """
    start_time = time.time()

    try:
        logger.info(f"Processing query: {request.question}")

        # 1) Classify intent once (used by generator + summarizer + logger)
        intent = sql_generator.intent_classifier.classify(request.question)
        logger.info("Intent: %s", intent)

        # 2) Generate SQL (pass intent via user_context to avoid re-classification)
        sql = sql_generator.generate_sql(
            request.question,
            user_context={"intent": intent}
        )

        # 3) Execute SQL
        raw_results = execute_sql(sql)

        # If DB client returns an error dict
        if isinstance(raw_results, dict) and "error" in raw_results:
            raise HTTPException(
                status_code=400,
                detail=f"SQL execution error: {raw_results['error']}"
            )

        # 4) Make results JSON-serializable (Decimal → float etc.)
        results_serializable = make_serializable(raw_results)

        # Ensure results is a list of dicts for the response model
        if isinstance(results_serializable, dict):
            results_list: List[Dict[str, Any]] = [results_serializable]
        else:
            results_list = results_serializable or []

        # 5) Limit results if requested
        if request.max_results and isinstance(results_list, list):
            results_list = results_list[:request.max_results]

        # 6) Generate business summary (TR/EN auto-detected)
        summary = summarizer.summarize(
            user_question=request.question,
            sql_query=sql,
            query_results=results_list,
            intent=intent,
        )

        execution_time = time.time() - start_time

        # 7) Log query in background
        background_tasks.add_task(
            log_query_async,
            question=request.question,
            sql=sql,
            intent=intent,
            success=True,
            execution_time=execution_time,
            results_count=len(results_list),
        )

        # 8) Build response
        response = QueryResponse(
            success=True,
            question=request.question,
            intent=intent if request.include_intent else None,
            sql=sql if request.include_sql else None,
            results=results_list,
            results_count=len(results_list),
            summary=summary,
            execution_time=execution_time,
            timestamp=datetime.now().isoformat(),
            error=None,
        )

        logger.info(f"Query processed successfully in {execution_time:.2f}s")
        return response

    except HTTPException:
        # Already has correct status + message
        raise

    except Exception as e:
        logger.error(f"Query processing error: {e}", exc_info=True)

        # Log failed query
        background_tasks.add_task(
            log_query_async,
            question=request.question,
            sql=None,
            intent={},
            success=False,
            execution_time=None,
            results_count=None,
            error=str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}"
        )


# -------------------------------------------------------------
# Stats & History
# -------------------------------------------------------------
@app.get("/stats", response_model=StatsResponse)
async def get_statistics():
    """
    Get query statistics from QueryLogger
    """
    try:
        stats = query_logger.get_statistics()
        return StatsResponse(**stats)

    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch statistics: {str(e)}"
        )


@app.get("/history")
async def get_query_history(limit: int = 50):
    """
    Get recent query history

    Args:
        limit: Maximum number of queries to return
    """
    try:
        queries = query_logger._load_all_queries()

        # Return most recent queries
        recent = queries[-limit:] if len(queries) > limit else queries

        return {
            "total": len(queries),
            "returned": len(recent),
            "queries": list(reversed(recent)),
        }

    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch history: {str(e)}"
        )


@app.post("/clear-history")
async def clear_history():
    """Clear query history"""
    try:
        query_logger.clear_history()
        return {"message": "History cleared successfully"}

    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear history: {str(e)}"
        )


# -------------------------------------------------------------
# Example queries (for UI)
# -------------------------------------------------------------
@app.get("/examples")
async def get_examples():
    """Get example questions for the frontend"""
    return {
        "examples": [
            {
                "category": "Aggregation",
                "questions": [
                    "2008 yılında toplam satış miktarı nedir?",
                    "2007 yılında kaç adet ürün satıldı?",
                    "Toplam online satış nedir?"
                ],
            },
            {
                "category": "Ranking",
                "questions": [
                    "En çok satan 5 ürün hangisi?",
                    "En az satan 3 kategori nedir?",
                    "2009'da en başarılı mağazalar hangileri?"
                ],
            },
            {
                "category": "Comparison",
                "questions": [
                    "2007'de mağaza vs online satış karşılaştırması",
                    "Kategori bazında satış karşılaştırması",
                    "2008 ve 2009 yıl karşılaştırması"
                ],
            },
            {
                "category": "Trend",
                "questions": [
                    "2008 yılı aylık satış trendi",
                    "Yıllık satış gelişimi nasıl?",
                    "Çeyrek bazında trend analizi"
                ],
            },
        ]
    }


# -------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------
def make_serializable(result: Any):
    """Convert Decimal values to float for JSON serialization."""
    import decimal

    if isinstance(result, list):
        converted = []
        for row in result:
            if isinstance(row, dict):
                converted.append({
                    k: float(v) if isinstance(v, decimal.Decimal) else v
                    for k, v in row.items()
                })
            else:
                converted.append(row)
        return converted

    if isinstance(result, dict):
        return {
            k: float(v) if isinstance(v, decimal.Decimal) else v
            for k, v in result.items()
        }

    return result


async def log_query_async(
    question: str,
    sql: Optional[str],
    intent: Dict,
    success: bool,
    execution_time: Optional[float] = None,
    results_count: Optional[int] = None,
    error: Optional[str] = None,
):
    """Background task to log query."""
    try:
        query_logger.log_query(
            question=question,
            sql=sql,
            intent=intent or {},
            strategy="api",
            success=success,
            execution_time=execution_time,
            results_count=results_count,
            error=error,
        )
    except Exception as e:
        logger.error(f"Failed to log query: {e}")


# Run with: uvicorn api:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
