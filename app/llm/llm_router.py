"""
LLM Router
----------
Merkezi LLM seçicisi.

Öncelik sırası:
1) OpenAI (varsa ve çalışıyorsa)
2) Ollama fallback
3) Model bazlı dinamik routing (ileride kolayca genişler)
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

        # Eğer API key yoksa OpenAI'yi otomatik devre dışı bırak
        self.openai_enabled = bool(Config.OPENAI_API_KEY)

        # Model seçimi
        self.primary_model = Config.OPENAI_MODEL
        self.fallback_model = Config.OLLAMA_MODEL

        logger.info(f"🔄 LLM Router initialized. "
                    f"OpenAI enabled: {self.openai_enabled}, "
                    f"Primary: {self.primary_model}, Fallback: {self.fallback_model}")

    # ------------------------------------------------------------
    # CENTRAL SQL GENERATION ENTRY
    # ------------------------------------------------------------
    def generate_sql(self, prompt: str) -> str:
        """
        Main entry point — SQL üretmek için OpenAI → Ollama fallback mekanizması.
        """

        # 1) Try OpenAI first
        if self.openai_enabled:
            try:
                logger.info("🧠 Using OpenAI for SQL generation...")
                return self.openai.generate(prompt)
            except Exception as e:
                logger.warning(f"⚠️ OpenAI failed, falling back to Ollama: {str(e)}")

        # 2) Fallback: Ollama
        try:
            logger.info("🧩 Using Ollama fallback model...")
            return self.ollama.generate_sql(prompt)
        except Exception as e:
            logger.error(f"❌ Both OpenAI and Ollama failed: {str(e)}")
            raise RuntimeError("Both LLM backends failed.") from e

    # ------------------------------------------------------------
    # Optional: multi-model routing for advanced use cases
    # ------------------------------------------------------------
    def generate_text(self, prompt: str) -> str:
        """General text generation, same fallback logic."""
        if self.openai_enabled:
            try:
                return self.openai.generate(prompt)
            except:
                pass

        return self.ollama.generate(prompt)
