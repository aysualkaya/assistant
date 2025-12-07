# app/llm/router.py
"""
LLM Router (Production 2025)

Priority:
1) OpenAI (if key exists)
2) Ollama fallback

Features:
- Dedicated SQL vs TEXT model routing
- Graceful fallback
- Unified error handling
- Config-aware model selection
"""

from app.llm.openai_client import OpenAIClient
from app.llm.ollama_client import OllamaClient
from app.core.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMRouter:
    def __init__(self):
        self.openai = OpenAIClient()
        self.ollama = OllamaClient()

        # OpenAI availability
        self.openai_enabled = bool(Config.OPENAI_API_KEY)

        # Models
        self.openai_model = Config.OPENAI_MODEL
        self.ollama_sql_model = Config.OLLAMA_SQL_MODEL
        self.ollama_text_model = Config.OLLAMA_SUMMARY_MODEL

        logger.info(
            f"🔄 LLM Router initialized | "
            f"OpenAI: {self.openai_enabled} | "
            f"OpenAI model: {self.openai_model} | "
            f"Ollama SQL model: {self.ollama_sql_model} | "
            f"Ollama TEXT model: {self.ollama_text_model}"
        )

    # ------------------------------------------------------------------
    #  SQL GENERATION (Main Entry)
    # ------------------------------------------------------------------
    def generate_sql(self, prompt: str) -> str:
        """
        First try OpenAI → fallback to Ollama SQL model.
        """

        openai_error = None
        ollama_error = None

        # 1) Try OpenAI
        if self.openai_enabled:
            try:
                logger.info("🧠 Using OpenAI for SQL generation...")
                return self.openai.generate(prompt, model=self.openai_model)
            except Exception as e:
                openai_error = str(e)
                logger.warning(f"⚠️ OpenAI SQL generation failed: {e}")

        # 2) Fallback: Ollama (SQL model)
        try:
            logger.info("🧩 Using Ollama SQL fallback model...")
            return self.ollama.generate(prompt, model=self.ollama_sql_model)
        except Exception as e:
            ollama_error = str(e)
            logger.error(f"❌ Ollama SQL generation failed: {e}")

        # 3) If both failed → fail with details
        raise RuntimeError(
            "Both LLM backends failed.\n"
            f"OpenAI error: {openai_error}\n"
            f"Ollama error: {ollama_error}"
        )

    # ------------------------------------------------------------------
    # TEXT / SUMMARY GENERATION
    # ------------------------------------------------------------------
    def generate_text(self, prompt: str) -> str:
        """
        General text generation, summary, explanation.
        """

        openai_error = None

        # Try OpenAI first
        if self.openai_enabled:
            try:
                logger.info("🧠 Using OpenAI for text generation...")
                return self.openai.generate(prompt, model=self.openai_model)
            except Exception as e:
                openai_error = str(e)
                logger.warning(f"⚠️ OpenAI text generation failed: {e}")

        # Fallback to Ollama text model
        try:
            logger.info("🧩 Using Ollama text fallback model...")
            return self.ollama.generate(prompt, model=self.ollama_text_model)
        except Exception as e:
            raise RuntimeError(
                "Text generation failed on all backends.\n"
                f"OpenAI error: {openai_error}\n"
                f"Ollama error: {str(e)}"
            )
