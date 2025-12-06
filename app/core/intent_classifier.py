# app/core/intent_classifier.py
"""
Hybrid Intent Classifier (Ollama + OpenAI Fallback)
----------------------------------------------------
- Rule-based first
- Ollama model second
- OpenAI 4o-mini fallback if Ollama fails or low-confidence
- Robust JSON parsing
- Backward-compatible with existing DynamicSQLGenerator
"""

from typing import Dict, List, Optional
import json
import re

from app.llm.ollama_client import OllamaClient
from app.llm.openai_client import OpenAIClient  # NEW: fallback layer
from app.utils.logger import get_logger

logger = get_logger(__name__)


class IntentClassifier:

    def __init__(self):
        self.ollama = OllamaClient()
        self.openai = OpenAIClient()  # NEW
        self.classification_cache = {}

    # ============================================================
    # PUBLIC METHOD
    # ============================================================
    def classify(self, question: str) -> Dict:
        question_lc = question.lower().strip()

        # Cache
        if question_lc in self.classification_cache:
            return self.classification_cache[question_lc]

        logger.info("🔍 Classifying user intent (hybrid)...")

        # 1) RULE-BASED FIRST
        rb = self._rule_based_classify(question)
        if rb and rb["confidence"] >= 0.80:
            logger.info("🎯 High-confidence rule-based classification used")
            self.classification_cache[question_lc] = rb
            return rb

        # 2) OLLAMA LLM ATTEMPT
        ollama_intent = self._llm_intent(question)
        if ollama_intent and ollama_intent["confidence"] >= 0.60:
            logger.info("🤖 Ollama intent accepted")
            self.classification_cache[question_lc] = ollama_intent
            return ollama_intent

        logger.warning("⚠️ Ollama uncertain → switching to OpenAI fallback")

        # 3) OPENAI FALLBACK (NEW)
        if self.openai.enabled:
            openai_intent = self._openai_intent(question)
            if openai_intent and openai_intent["confidence"] >= 0.60:
                logger.info("🧠 OpenAI fallback intent accepted")
                self.classification_cache[question_lc] = openai_intent
                return openai_intent

        logger.error("❌ Both LLM intent classifications failed → using safe fallback")

        # 4) SAFE DEFAULT
        fallback = self._fallback_intent(question)
        self.classification_cache[question_lc] = fallback
        return fallback

    # ============================================================
    # RULE-BASED CLASSIFICATION (UNCHANGED FROM YOUR VERSION)
    # ============================================================
    def _rule_based_classify(self, question: str) -> Optional[Dict]:
        """Improved Turkish keyword logic"""
        q = question.lower()

        # Ranking detection
        if any(k in q for k in ["en çok", "en cok", "top", "best", "highest"]):
            return {
                "complexity": 5,
                "query_type": "ranking",
                "tables_needed": self._detect_tables(q),
                "time_dimension": self._has_time_dimension(q),
                "time_granularity": self._detect_time_granularity(q),
                "aggregation_type": "sum",
                "requires_comparison": False,
                "comparison_type": "none",
                "top_n": None,
                "order_direction": "desc",
                "confidence": 0.90
            }

        # Comparison
        if any(k in q for k in ["karşı", "karsı", "vs", "compare"]):
            return {
                "complexity": 7,
                "query_type": "comparison",
                "tables_needed": self._detect_tables(q),
                "time_dimension": self._has_time_dimension(q),
                "time_granularity": self._detect_time_granularity(q),
                "aggregation_type": "sum",
                "requires_comparison": True,
                "comparison_type": "store_vs_online" if "online" in q else "none",
                "top_n": None,
                "order_direction": "none",
                "confidence": 0.85
            }

        # Trend
        if any(k in q for k in ["trend", "aylık", "aylik", "çeyrek", "hafta"]):
            return {
                "complexity": 6,
                "query_type": "trend",
                "tables_needed": self._detect_tables(q),
                "time_dimension": True,
                "time_granularity": self._detect_time_granularity(q),
                "aggregation_type": "sum",
                "requires_comparison": False,
                "comparison_type": "none",
                "confidence": 0.85
            }

        # Aggregation
        if any(k in q for k in ["toplam", "ortalama", "count", "sum"]):
            return {
                "complexity": 3,
                "query_type": "aggregation",
                "tables_needed": self._detect_tables(q),
                "time_dimension": self._has_time_dimension(q),
                "time_granularity": self._detect_time_granularity(q),
                "aggregation_type": "sum",
                "requires_comparison": False,
                "comparison_type": "none",
                "confidence": 0.75
            }

        return None

    # ============================================================
    # OLLAMA LLM INTENT
    # ============================================================
    def _llm_intent(self, question: str) -> Optional[Dict]:
        try:
            prompt = self._build_classification_prompt(question)
            response = self.ollama.run(prompt)  # textual JSON
            return self._parse_intent_response(response)
        except Exception as e:
            logger.error(f"Ollama intent failed: {e}")
            return None

    # ============================================================
    # OPENAI FALLBACK (NEW)
    # ============================================================
    def _openai_intent(self, question: str) -> Optional[Dict]:
        if not self.openai.enabled:
            return None
        try:
            prompt = self._build_classification_prompt(question)
            response = self.openai.generate(prompt)  # JSON string
            return self._parse_intent_response(response)
        except Exception as e:
            logger.error(f"OpenAI fallback intent failed: {e}")
            return None

    # ============================================================
    # CLASSIFICATION PROMPT (UNCHANGED)
    # ============================================================
    def _build_classification_prompt(self, question: str) -> str:
        return f"""
Classify the intent of this question for SQL generation:

QUESTION: "{question}"

Return ONLY a JSON object with:
{{
    "complexity": <1-10>,
    "query_type": "ranking|comparison|aggregation|trend|filter|complex",
    "tables_needed": ["..."],
    "time_dimension": true/false,
    "time_granularity": "year|month|day|none",
    "aggregation_type": "sum|avg|count|none",
    "requires_comparison": true/false,
    "comparison_type": "store_vs_online|year_over_year|none",
    "top_n": <int|null>,
    "order_direction": "asc|desc|none",
    "confidence": <0.0-1.0>
}}

Return ONLY the JSON. No text before or after it.
"""

    # ============================================================
    # JSON PARSER (ROBUST)
    # ============================================================
    def _parse_intent_response(self, response: str) -> Dict:
        if not response:
            raise ValueError("Empty intent response")

        response = response.strip()

        # Remove markdown
        if "```" in response:
            response = response.split("```")[1].split("```")[0].strip()

        # Extract JSON only
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if not match:
            raise ValueError("JSON not found in LLM response")

        data = json.loads(match.group(0))

        # Normalize fields
        data["complexity"] = max(1, min(10, int(data.get("complexity", 5))))
        data["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0.5))))

        return data

    # ============================================================
    # FALLBACK INTENT
    # ============================================================
    def _fallback_intent(self, question: str) -> Dict:
        q = question.lower()
        return {
            "complexity": 5,
            "query_type": "aggregation",
            "tables_needed": ["FactSales"],
            "time_dimension": self._has_time_dimension(q),
            "time_granularity": self._detect_time_granularity(q),
            "aggregation_type": "sum",
            "requires_comparison": False,
            "comparison_type": "none",
            "top_n": None,
            "order_direction": "none",
            "confidence": 0.50
        }

    # ============================================================
    # HELPERS (AS IS)
    # ============================================================
    def _detect_tables(self, q: str) -> List[str]:
        tables = ["FactSales"]
        if "online" in q:
            tables.append("FactOnlineSales")
        if "urun" in q or "product" in q:
            tables.append("DimProduct")
        if "magaza" in q or "mağaza" in q or "store" in q:
            tables.append("DimStore")
        return tables

    def _has_time_dimension(self, q: str) -> bool:
        return any(t in q for t in ["2007", "2008", "2009", "yil", "year", "ay", "month"])

    def _detect_time_granularity(self, q: str) -> str:
        if "ay" in q or "month" in q:
            return "month"
        if "yil" in q or "year" in q:
            return "year"
        return "none"
