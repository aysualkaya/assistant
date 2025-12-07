# app/core/orchestrator.py

from typing import Dict, Any
from app.core.intent_classifier import IntentClassifier
from app.llm.sql_generator import DynamicSQLGenerator
from app.llm.result_summarizer import ResultSummarizer
from app.database.db_client import DatabaseClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AnalyticsAssistant:
    """
    Final Production Pipeline (Simplified & Clean)

    Question → Intent → SQL → Execute → Summary

    Notes:
    - SQL validation & self-correction SQLGenerator içinde yapılır.
    - LangChain schema-awareness → DB errors %70+ azalır.
    """

    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.sql_generator = DynamicSQLGenerator()
        self.summarizer = ResultSummarizer()
        self.db = DatabaseClient()

    # ============================================================
    # PUBLIC ENTRY POINT
    # ============================================================
    def answer_question(self, question: str) -> Dict[str, Any]:
        logger.info(f"🔍 Yeni soru alındı: {question}")

        # 1) Intent (tek yerde hesaplanıyor)
        intent = self.intent_classifier.classify(question)
        logger.info(f"🎯 Intent: {intent}")

        # 2) Domain guard
        if not self._is_in_scope(question):
            return self._out_of_scope_response()

        # 3) SQL Generation
        try:
            sql = self.sql_generator.generate_sql(
                question=question,
                user_context={"intent": intent}   # ✔ intent twice compute engellendi
            )
        except Exception as e:
            return self._sql_generation_failed_response(str(e))

        logger.info(f"🧩 Üretilen SQL:\n{sql}")

        # 4) SQL Execute (try-run)
        try:
            rows, exec_time = self.db.execute_query(sql)
        except Exception as db_error:
            logger.error(f"❌ DB Executing Error: {db_error}")

            # 4a) Try Runtime correction
            corrected_sql = self._attempt_runtime_correction(question, sql, str(db_error))

            if corrected_sql is None:
                return self._sql_runtime_error_response(sql, db_error)

            # Try corrected SQL
            try:
                rows, exec_time = self.db.execute_query(corrected_sql)
                sql = corrected_sql
            except Exception as final_error:
                return self._sql_runtime_error_response(corrected_sql, final_error)

        # 5) Summarize
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

    # ============================================================
    # RUNTIME SQL CORRECTION
    # ============================================================
    def _attempt_runtime_correction(self, question: str, faulty_sql: str, db_error: str):
        """
        DB error durumunda SQL'i yeniden denemek için simplified correction.
        SQLGenerator kendi içinde prompt & logic halleder.
        """
        logger.warning("🔁 DB error sonrası runtime self-correction çalışıyor...")

        correction_prompt = (
            f"Sorgu hatası oluştu, düzelt:\n{question}\n\n"
            f"Önceki SQL:\n{faulty_sql}\n\n"
            f"Hata Mesajı:\n{db_error}"
        )

        try:
            return self.sql_generator.generate_sql(correction_prompt)
        except Exception:
            return None

    # ============================================================
    # HELPERS
    # ============================================================
    def _is_in_scope(self, question: str) -> bool:
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
            "message": "Bu asistan yalnızca Contoso veri ambarına dayalı analizler yapabilir."
        }

    def _sql_generation_failed_response(self, error: str) -> Dict[str, Any]:
        return {
            "status": "sql_generation_failed",
            "message": "Geçerli bir SQL üretilemedi.",
            "detail": error
        }

    def _sql_runtime_error_response(self, sql: str, error: Exception) -> Dict[str, Any]:
        return {
            "status": "sql_runtime_error",
            "message": "SQL sorgusu veritabanında çalıştırılırken hata oluştu.",
            "sql": sql,
            "detail": str(error)
        }
