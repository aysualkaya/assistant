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
from app.memory.pattern_miner import PatternMiner
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
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
sql_generator = DynamicSQLGenerator()
summarizer = ResultSummarizer()
query_logger = QueryLogger()
pattern_miner = PatternMiner()


# Request/Response Models
class QueryRequest(BaseModel):
    question: str
    include_sql: bool = True
    include_intent: bool = True
    include_visualization: bool = False
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


class PatternResponse(BaseModel):
    patterns: List[Dict]
    total_patterns: int


# Health check
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Harmony AI - Contoso Analytics API",
        "version": "2.0.0",
        "status": "operational",
        "features": [
            "Dynamic intent classification",
            "LLM-first SQL generation",
            "Few-shot learning",
            "Auto-correction",
            "Business summaries",
            "Pattern mining"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# Main query endpoint
@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Process a natural language query
    
    Args:
        request: Query request containing the question and options
        
    Returns:
        Query response with SQL, results, and summary
    """
    start_time = time.time()
    
    try:
        logger.info(f"Processing query: {request.question}")
        
        # Classify intent
        intent = sql_generator.intent_classifier.classify(request.question)
        
        # Generate SQL
        sql = sql_generator.generate_sql(request.question)
        
        # Execute SQL
        results = execute_sql(sql)
        
        # Check for execution errors
        if isinstance(results, dict) and "error" in results:
            raise HTTPException(
                status_code=400,
                detail=f"SQL execution error: {results['error']}"
            )
        
        # Convert results
        results_serializable = make_serializable(results)
        
        # Limit results if requested
        if request.max_results and isinstance(results_serializable, list):
            results_serializable = results_serializable[:request.max_results]
        
        # Generate summary
        summary = summarizer.summarize(
            user_question=request.question,
            sql_query=sql,
            query_results=results_serializable,
            intent=intent
        )
        
        execution_time = time.time() - start_time
        
        # Log query in background
        background_tasks.add_task(
            log_query_async,
            question=request.question,
            sql=sql,
            intent=intent,
            success=True,
            execution_time=execution_time,
            results_count=len(results_serializable) if isinstance(results_serializable, list) else 1
        )
        
        # Build response
        response = QueryResponse(
            success=True,
            question=request.question,
            intent=intent if request.include_intent else None,
            sql=sql if request.include_sql else None,
            results=results_serializable,
            results_count=len(results_serializable) if isinstance(results_serializable, list) else 1,
            summary=summary,
            execution_time=execution_time,
            timestamp=datetime.now().isoformat()
        )
        
        logger.info(f"Query processed successfully in {execution_time:.2f}s")
        return response
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Query processing error: {e}", exc_info=True)
        
        # Log failed query
        background_tasks.add_task(
            log_query_async,
            question=request.question,
            sql=None,
            intent=None,
            success=False,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}"
        )


@app.get("/stats", response_model=StatsResponse)
async def get_statistics():
    """
    Get query statistics
    
    Returns:
        Statistics about query history
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


@app.get("/patterns", response_model=PatternResponse)
async def get_patterns(min_frequency: int = 2):
    """
    Get discovered query patterns
    
    Args:
        min_frequency: Minimum pattern frequency
        
    Returns:
        Discovered patterns
    """
    try:
        patterns = pattern_miner.mine_patterns(min_frequency=min_frequency)
        
        return PatternResponse(
            patterns=patterns,
            total_patterns=len(patterns)
        )
    
    except Exception as e:
        logger.error(f"Error mining patterns: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mine patterns: {str(e)}"
        )


@app.get("/history")
async def get_query_history(limit: int = 50):
    """
    Get recent query history
    
    Args:
        limit: Maximum number of queries to return
        
    Returns:
        Recent query history
    """
    try:
        queries = query_logger._load_all_queries()
        
        # Return most recent queries
        recent = queries[-limit:] if len(queries) > limit else queries
        
        return {
            "total": len(queries),
            "returned": len(recent),
            "queries": list(reversed(recent))
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


@app.get("/examples")
async def get_examples():
    """Get example questions"""
    return {
        "examples": [
            {
                "category": "Aggregation",
                "questions": [
                    "2008 yılında toplam satış miktarı nedir?",
                    "2007 yılında kaç adet ürün satıldı?",
                    "Toplam online satış nedir?"
                ]
            },
            {
                "category": "Ranking",
                "questions": [
                    "En çok satan 5 ürün hangisi?",
                    "En az satan 3 kategori nedir?",
                    "2009'da en başarılı mağazalar hangileri?"
                ]
            },
            {
                "category": "Comparison",
                "questions": [
                    "2007'de mağaza vs online satış karşılaştırması",
                    "Kategori bazında satış karşılaştırması",
                    "2008 ve 2009 yıl karşılaştırması"
                ]
            },
            {
                "category": "Trend",
                "questions": [
                    "2008 yılı aylık satış trendi",
                    "Yıllık satış gelişimi nasıl?",
                    "Çeyrek bazında trend analizi"
                ]
            }
        ]
    }


# Helper functions
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


async def log_query_async(
    question: str,
    sql: Optional[str],
    intent: Optional[Dict],
    success: bool,
    execution_time: Optional[float] = None,
    results_count: Optional[int] = None,
    error: Optional[str] = None
):
    """Background task to log query"""
    try:
        query_logger.log_query(
            question=question,
            sql=sql,
            intent=intent or {},
            strategy="api",
            success=success,
            execution_time=execution_time,
            results_count=results_count,
            error=error
        )
    except Exception as e:
        logger.error(f"Failed to log query: {e}")


# Run with: uvicorn api:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)