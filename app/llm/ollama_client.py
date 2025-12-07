# app/llm/ollama_client.py
"""
OllamaClient - Final Production Version (2025)

Supports:
- SQL model (Config.OLLAMA_SQL_MODEL)
- Summary/text model (Config.OLLAMA_SUMMARY_MODEL)
- Streaming for SQL
- Non-streaming for Summary
- Retry + Timeout
- Simple in-memory caching
- SQL-aware postprocessing
- Optional OpenAI fallback (for both SQL + Summary)
- LangChain LLM wrapper for QuerySQLCheckerTool
"""

import json
import time
import re
import hashlib
from typing import Optional, Dict, Any

import requests

from app.utils.logger import get_logger
from app.core.config import Config
from app.llm.openai_client import OpenAIClient

logger = get_logger(__name__)


class OllamaClient:
    """
    High-level client used by:
    - DynamicSQLGenerator (generate_sql)
    - ResultSummarizer (generate_summary)
    - LLMRouter (generate)
    """

    def __init__(
        self,
        sql_model: Optional[str] = None,
        summary_model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        enable_cache: Optional[bool] = None,
    ):
        # Models (from Config)
        self.sql_model = sql_model or Config.OLLAMA_SQL_MODEL
        self.summary_model = summary_model or Config.OLLAMA_SUMMARY_MODEL

        # Base URL
        self.base_url = (base_url or Config.OLLAMA_HOST).rstrip("/")

        # Timeouts
        self.timeout = timeout or Config.OLLAMA_TIMEOUT

        # Cache settings
        self.enable_cache = (
            enable_cache if enable_cache is not None else Config.ENABLE_CACHING
        )

        # Retries
        self.max_retries = 2
        self.retry_delay = 1.2

        # OpenAI fallback
        self.enable_openai_fallback = Config.ENABLE_OPENAI_FALLBACK
        self.openai_client = OpenAIClient() if self.enable_openai_fallback else None

        # Simple in-memory cache
        self._cache: Dict[str, str] = {}
        self.metrics: Dict[str, Any] = {"errors": 0}

        logger.info(
            "🤖 OllamaClient initialized "
            f"(sql_model={self.sql_model}, summary_model={self.summary_model}, "
            f"fallback={'ON' if self.enable_openai_fallback else 'OFF'})"
        )

    # ======================================================
    # PUBLIC API - GENERIC
    # ======================================================
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        clean_sql: bool = False,
        stream: bool = False,
        stream_callback=None,
    ) -> Optional[str]:
        """
        Generic text generation entry.
        LLMRouter uses this.
        """
        chosen_model = model or self.summary_model

        return self._generate(
            model=chosen_model,
            prompt=prompt,
            stream=stream,
            stream_callback=stream_callback,
            clean_sql=clean_sql,
        )

    # ======================================================
    # PUBLIC API - SQL
    # ======================================================
    def generate_sql(self, prompt: str, stream_callback=None) -> Optional[str]:
        """
        Main SQL generator:
         1) Try Ollama (SQL model)
         2) If empty/failed → OpenAI fallback
        """
        logger.info("🔍 Generating SQL using primary Ollama SQL model...")

        sql_text = self._generate(
            model=self.sql_model,
            prompt=prompt,
            stream=True,
            stream_callback=stream_callback,
            clean_sql=True,
        )

        if sql_text:
            return sql_text

        # OpenAI fallback
        if self.enable_openai_fallback and self.openai_client:
            logger.warning("⚠️ Ollama SQL failed → switching to OpenAI SQL fallback...")
            try:
                fallback_sql = self.openai_client.generate_sql(prompt)
                if fallback_sql:
                    logger.info("✅ OpenAI SQL fallback succeeded.")
                    return fallback_sql
            except Exception as e:
                logger.error(f"❌ OpenAI SQL fallback failed: {e}")

        logger.error("❌ SQL generation failed in both Ollama and OpenAI.")
        return None

    # ======================================================
    # PUBLIC API - SUMMARY / TEXT
    # ======================================================
    def generate_summary(self, prompt: str) -> Optional[str]:
        """
        Summary generator:
         1) Try Ollama summary model
         2) Fallback to OpenAI
        """
        logger.info("📊 Generating summary using Ollama summary model...")

        summary = self._generate(
            model=self.summary_model,
            prompt=prompt,
            stream=False,
            stream_callback=None,
            clean_sql=False,
        )

        if summary:
            return summary.strip()

        # Summary fallback
        if self.enable_openai_fallback and self.openai_client:
            logger.warning("⚠️ Ollama summary failed → switching to OpenAI fallback...")
            try:
                fallback_summary = self.openai_client.generate(prompt)
                if fallback_summary:
                    logger.info("✅ OpenAI summary fallback succeeded.")
                    return fallback_summary.strip()
            except Exception as e:
                logger.error(f"❌ OpenAI summary fallback failed: {e}")

        logger.error("❌ Summary generation failed in both Ollama and OpenAI.")
        return None

    # ======================================================
    # CORE GENERATE
    # ======================================================
    def _generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        stream_callback=None,
        clean_sql: bool = False,
    ) -> Optional[str]:
        """
        Low-level HTTP wrapper for Ollama `/api/generate`.
        Retry / caching / parse / cleanup handled here.
        """
        cache_key = self._make_cache_key(model, prompt)

        # Cache hit
        if self.enable_cache and cache_key in self._cache:
            logger.info(f"💾 Cache hit (model={model})")
            return self._cache[cache_key]

        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": stream}

        for attempt in range(1, self.max_retries + 2):
            try:
                logger.info(
                    f"🔗 Calling Ollama (model={model}, attempt={attempt}, stream={stream})"
                )

                resp = requests.post(
                    url, json=payload, timeout=self.timeout, stream=stream
                )
                resp.raise_for_status()

                if stream:
                    raw = self._parse_streaming_response(resp, stream_callback)
                else:
                    raw = self._parse_non_streaming(resp)

                if not raw:
                    logger.warning("⚠️ Ollama returned empty response → retrying...")
                    continue

                cleaned = self._postprocess(raw, clean_sql)
                if cleaned:
                    if self.enable_cache:
                        self._cache[cache_key] = cleaned
                    return cleaned

            except Exception as e:
                logger.error(f"❌ Ollama error on attempt {attempt}: {e}")
                self.metrics["errors"] += 1
                if attempt <= self.max_retries:
                    time.sleep(self.retry_delay)

        return None

    # ======================================================
    # RESPONSE PARSING
    # ======================================================
    def _parse_streaming_response(self, resp, stream_callback=None) -> str:
        final = ""
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line.decode("utf-8"))
            except Exception:
                continue

            chunk = data.get("response") or data.get("text") or ""
            if chunk:
                final += chunk
                if stream_callback:
                    try:
                        stream_callback(chunk)
                    except Exception as e:
                        logger.warning(f"Stream callback error: {e}")

        return final.strip()

    def _parse_non_streaming(self, resp) -> str:
        try:
            data = resp.json()
        except Exception:
            return ""
        return (data.get("response") or data.get("text") or "").strip()

    # ======================================================
    # POSTPROCESS
    # ======================================================
    def _postprocess(self, text: str, clean_sql: bool) -> str:
        if not text:
            return ""
        if clean_sql:
            return self._clean_sql(text)
        return text.strip()

    def _clean_sql(self, raw: str) -> str:
        """
        Removes markdown fences and extracts valid SQL section.
        """
        txt = raw.strip()

        txt = re.sub(r"```sql", "", txt, flags=re.IGNORECASE)
        txt = re.sub(r"```", "", txt)

        match = re.search(
            r"(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE)[\s\S]*",
            txt,
            re.IGNORECASE,
        )
        if match:
            txt = match.group(0)

        txt = re.sub(r"\bGO\b", "", txt, flags=re.IGNORECASE)
        return txt.strip()

    # ======================================================
    # UTILITIES
    # ======================================================
    def _make_cache_key(self, model: str, prompt: str) -> str:
        return hashlib.md5(f"{model}||{prompt}".encode("utf-8")).hexdigest()

    # ======================================================
    # LANGCHAIN LLM WRAPPER (NEW)
    # ======================================================
    def as_langchain_llm(self):
        """
        Converts Ollama SQL model into a LangChain-compatible LLM.
        Required for QuerySQLCheckerTool.
        """
        try:
            from langchain_community.llms import Ollama

            llm = Ollama(
                base_url=self.base_url,
                model=self.sql_model,
                timeout=self.timeout,
                temperature=0.0,
            )
            return llm

        except Exception as e:
            logger.error(f"❌ Failed to create LangChain Ollama LLM: {e}")
            return None


# Singleton helper
_OLLAMA_SINGLETON: Optional[OllamaClient] = None


def get_default_ollama_client() -> OllamaClient:
    global _OLLAMA_SINGLETON
    if _OLLAMA_SINGLETON is None:
        _OLLAMA_SINGLETON = OllamaClient()
    return _OLLAMA_SINGLETON
