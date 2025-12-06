from openai import OpenAI
from app.core.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    """
    OpenAI Client (2025 Responses API)
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

    # ==================================================================
    # SQL GENERATION (STRICT)
    # ==================================================================
    def generate_sql(self, prompt: str) -> str:
        if not self.enabled:
            return ""

        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert SQL generator.\n"
                            "Rules:\n"
                            "1. Return ONLY SQL code.\n"
                            "2. Do NOT include explanations.\n"
                            "3. Do NOT include comments.\n"
                            "4. Output MUST start with SELECT or WITH.\n"
                            "5. No markdown, no backticks, no prose.\n"
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_output_tokens=800,
            )

            raw = self._extract_text(response)
            return raw.strip()

        except Exception as e:
            logger.error(f"❌ OpenAI SQL generation failed: {e}")
            return ""

    # ==================================================================
    # GENERAL TEXT GENERATION
    # ==================================================================
    def generate(self, prompt: str) -> str:
        if not self.enabled:
            return ""

        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                max_output_tokens=1000,
            )

            return self._extract_text(response).strip()

        except Exception as e:
            logger.error(f"❌ OpenAI text generation failed: {e}")
            return ""

    # ==================================================================
    # INTERNAL SAFE EXTRACTION
    # ==================================================================
    def _extract_text(self, response) -> str:
        try:
            if hasattr(response, "output_text"):
                return response.output_text

            if hasattr(response, "output"):
                for item in response.output:
                    if "content" in item:
                        return item["content"]

            return str(response)

        except Exception:
            return ""
