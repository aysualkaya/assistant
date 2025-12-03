# app/core/orchestrator.py

from typing import Dict, Any
from app.core.intent_classifier import IntentClassifier
from app.llm.sql_generator import DynamicSQLGenerator
from app.llm.sql_generator import SQLGenerationError
from app.llm.result_summarizer import ResultSummarizer
from app.database.db_client import DatabaseClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AnalyticsAssistant:
    """
    LLM tabanlı akıllı analitik asistan için tam pipeline:
    
    Soru → Intent → SQL Draft → Normalize → Validate → Execute → Summary
    """
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.sql_generator = DynamicSQLGenerator()
        self.summarizer = ResultSummarizer()
        self.db = DatabaseClient()

    # --------------------
    #   PUBLIC ENTRY POINT
    # --------------------
    def answer_question(self, question: str) -> Dict[str, Any]:
        logger.info(f"🔍 Yeni soru alındı: {question}")

        # 1) Intent analizi
        intent = self.intent_classifier.classify(question)
        logger.info(f"🎯 Intent: {intent}")

        # 2) Domain kontrolü (Contoso dışı soruları reddetme)
        if not self._is_in_scope(question):
            return self._out_of_scope_response()

        # 3) SQL üretimi + self-correction pipeline
        try:
            sql = self.sql_generator.generate_sql(question)
        except SQLGenerationError as e:
            return self._sql_generation_failed_response(str(e))

        logger.info(f"🧩 Üretilen SQL: {sql}")

        # 4) SQL’i DB’de çalıştır
        try:
            rows, exec_time = self.db.execute_query(sql)
        except Exception as db_error:
            logger.error(f"❌ DB hata: {db_error}")
            
            # DB hatasını LLM'e geri besleyerek düzeltme şansı ver
            corrected_sql = self.sql_generator.fix_sql(
                question=question,
                faulty_sql=sql,
                error_message=str(db_error)
            )

            if corrected_sql is None:
                return self._sql_runtime_error_response(sql, db_error)

            logger.info("🔁 DB hatasına göre düzeltilmiş SQL üretildi")
            logger.info(corrected_sql)

            # Tekrar çalıştır
            try:
                rows, exec_time = self.db.execute_query(corrected_sql)
                sql = corrected_sql  # final SQL budur
            except Exception as final_error:
                return self._sql_runtime_error_response(corrected_sql, final_error)

        # 5) Sonuçları özetle
        summary = self.summarizer.summarize(
            user_question=question,
            sql_query=sql,
            query_results=rows,
            intent=intent,
            execution_time=exec_time
        )

        return {
            "status": "ok",
            "sql": sql,
            "rows": rows,
            "summary": summary,
            "execution_time": exec_time
        }

    # --------------------
    #       HELPERS
    # --------------------
    def _is_in_scope(self, question: str) -> bool:
        """
        Basit domain guard (istersen event-driven hale getirebilirim).
        """
        q = question.lower()
        keywords = [
            "satış", "satis", "ciro", "gelir", "ürün", "urun",
            "kategori", "mağaza", "magaza", "müşteri", "musteri",
            "iade", "karlılık", "profit", "revenue", "sales",
            "store", "online", "kanal", "bölge", "bolge", "segment"
        ]
        return any(k in q for k in keywords)

    def _out_of_scope_response(self) -> Dict[str, Any]:
        return {
            "status": "out_of_scope",
            "message": "Bu asistan yalnızca Contoso satış/müşteri/veri ambarı verilerine dayalı analizler yapabilir."
        }

    def _sql_generation_failed_response(self, error: str) -> Dict[str, Any]:
        return {
            "status": "sql_generation_failed",
            "message": "Sorduğunuz soru için geçerli bir SQL üretilirken hata oluştu.",
            "detail": error
        }

    def _sql_runtime_error_response(self, sql: str, error: Exception) -> Dict[str, Any]:
        return {
            "status": "sql_runtime_error",
            "message": "SQL sorgusu veritabanında çalıştırılırken hata oluştu.",
            "sql": sql,
            "detail": str(error)
        }
