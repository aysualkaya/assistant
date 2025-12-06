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
    LLM tabanlı akıllı analitik asistan için final üretim pipeline’ı:

    Soru → Intent → SQL → Normalize → Validate → Execute → Summary
    Tüm hata durumlarında self-correction SQL generator tarafından yapılır.
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

        # 1) Intent analizi
        intent = self.intent_classifier.classify(question)
        logger.info(f"🎯 Intent: {intent}")

        # 2) Domain guard
        if not self._is_in_scope(question):
            return self._out_of_scope_response()

        # 3) SQL üretimi + self-correction pipeline (DynamicSQLGenerator içinde)
        try:
            sql = self.sql_generator.generate_sql(question)
        except Exception as e:
            # SQLGenerationError artık yok → genel hata yakalayıcı
            return self._sql_generation_failed_response(str(e))

        logger.info(f"🧩 Üretilen SQL:\n{sql}")

        # 4) SQL’i DB’de çalıştır
        try:
            rows, exec_time = self.db.execute_query(sql)
        except Exception as db_error:
            logger.error(f"❌ DB Executing Error: {db_error}")

            # DynamicSQLGenerator içinde self-correction zaten var
            # Ama DB hatası için explicit correction isteyebiliriz:
            corrected_sql = self._attempt_runtime_correction(
                question=question,
                faulty_sql=sql,
                db_error=str(db_error)
            )

            if corrected_sql is None:
                return self._sql_runtime_error_response(sql, db_error)

            # yeniden çalıştır
            try:
                rows, exec_time = self.db.execute_query(corrected_sql)
                sql = corrected_sql
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

    # ============================================================
    # RUNTIME SQL CORRECTION (DB ERROR’A GÖRE)
    # ============================================================
    def _attempt_runtime_correction(self, question: str, faulty_sql: str, db_error: str):
        """
        DB error aldığında SQL'i yeniden üretmek için SQL generator içinde correction çalıştırır.
        Correction prompt'unu generator halleder.
        """

        logger.warning("🔁 DB error sonrası self-correction tetiklendi.")

        try:
            corrected_sql = self.sql_generator.generate_sql(
                f"Sorgu hatası oluştu, düzelt: {question}\n\n"
                f"Önceki SQL:\n{faulty_sql}\n\n"
                f"Hata mesajı:\n{db_error}"
            )
            return corrected_sql
        except Exception as e:
            logger.error(f"❌ DB self-correction başarısız: {e}")
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
            "message": "Bu asistan yalnızca Contoso satış/müşteri/veri ambarı verilerine dayalı analizler yapabilir."
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
