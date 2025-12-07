# app/llm/openai_client.py
"""
OpenAIClient - 2025 Production Version
Compatible with:
- DynamicSQLGenerator
- LLMRouter
- ResultSummarizer
- Responses API (v2025)
"""

from openai import OpenAI
from app.core.config import Config
from app.utils.logger import get_logger
import re

logger = get_logger(__name__)


class OpenAIClient:
    """
    Thin wrapper over OpenAI Responses API.
    Provides:
    - SQL generation (strict)
    - General text generation
    - Safe extraction
    """

    def __init__(self):
        api_key = Config.OPENAI_API_KEY

        if not api_key:
            logger.warning("⚠️ OPENAI_API_KEY missing — OpenAI disabled.")
            self.enabled = False
            return

        try:
            self.client = OpenAI(api_key=api_key)
            self.model = Config.OPENAI_MODEL
            self.enabled = True

            logger.info(f"🧠 OpenAI client initialized with model: {self.model}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI client: {e}")
            self.enabled = False

    # =====================================================
    # SQL GENERATION
    # =====================================================
    def generate_sql(self, prompt: str) -> str:
        if not self.enabled:
            return ""

        try:
            logger.info("🧠 OpenAI SQL generation started...")

            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert SQL generator.\n"
                            "STRICT RULES:\n"
                            "1. Return ONLY SQL.\n"
                            "2. No explanations.\n"
                            "3. No comments.\n"
                            "4. Must start with SELECT or WITH.\n"
                            "5. No markdown or backticks.\n"
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_output_tokens=700,
            )

            raw = self._extract_text(response)
            cleaned = self._clean_sql(raw)

            return cleaned.strip()

        except Exception as e:
            logger.error(f"❌ OpenAI SQL generation failed: {e}")
            return ""

    # =====================================================
    # GENERAL TEXT GENERATION
    # =====================================================
    def generate(self, prompt: str) -> str:
        if not self.enabled:
            return ""

        try:
            response = self.client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": prompt}],
                max_output_tokens=1200,
            )

            return self._extract_text(response).strip()

        except Exception as e:
            logger.error(f"❌ OpenAI text generation failed: {e}")
            return ""

    # =====================================================
    # SAFE EXTRACTION FOR RESPONSES API
    # =====================================================
    def _extract_text(self, response) -> str:
        """
        Robust extractor for Responses API formats:
        - response.output_text
        - response.output[n].content
        """
        try:
            # Format 1
            if hasattr(response, "output_text") and response.output_text:
                return response.output_text

            # Format 2
            if hasattr(response, "output"):
                for part in response.output:
                    if isinstance(part, dict) and "content" in part:
                        return part["content"]

            return str(response)

        except Exception:
            return ""

    # =====================================================
    # SQL CLEANING
    # =====================================================
    def _clean_sql(self, text: str) -> str:
        if not text:
            return ""

        sql = text.strip()

        # Remove markdown ```
        sql = re.sub(r"```sql|```", "", sql, flags=re.IGNORECASE)

        # Remove explanations
        lines = []
        for line in sql.split("\n"):
            if re.match(r"^[A-Za-z ]+:\s*$", line.strip()):
                continue
            if "explanation" in line.lower():
                continue
            lines.append(line)
        sql = "\n".join(lines)

        # Extract only actual SQL
        match = re.search(r"(SELECT|WITH)[\s\S]*", sql, flags=re.IGNORECASE)
        if match:
            sql = match.group(0)

        return sql.strip()
