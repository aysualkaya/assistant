# app/core/intent_classifier.py
"""
LLM-based Intent Classification with Improved Turkish Keyword Detection
Analyzes user questions to determine query strategy and required resources
IMPROVED: Better fallback logic for Turkish keywords
"""

from typing import Dict, List, Optional
import json
import re
from app.llm.ollama_client import OllamaClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


class IntentClassifier:
    """
    Intelligent intent classification for dynamic SQL generation
    IMPROVED: Better Turkish keyword handling
    """
    
    def __init__(self):
        self.llm = OllamaClient()
        self.classification_cache = {}
    
    def classify(self, question: str) -> Dict:
        """
        Classify user intent and extract query metadata
        
        Args:
            question: User's natural language question
            
        Returns:
            Dict with intent metadata
        """
        # Check cache
        cache_key = question.lower().strip()
        if cache_key in self.classification_cache:
            logger.info("📦 Using cached intent classification")
            return self.classification_cache[cache_key]
        
        logger.info("🔍 Classifying user intent...")
        
        # IMPROVED: Try rule-based first for clear patterns
        rule_based_intent = self._rule_based_classify(question)
        if rule_based_intent and rule_based_intent.get('confidence', 0) >= 0.8:
            logger.info(f"✅ Rule-based classification: {rule_based_intent['query_type']}")
            self.classification_cache[cache_key] = rule_based_intent
            return rule_based_intent
        
        # Fall back to LLM if rules are uncertain
        prompt = self._build_classification_prompt(question)
        
        try:
            response = self.llm.generate_sql(prompt)
            intent = self._parse_intent_response(response)
            
            # Cache the result
            self.classification_cache[cache_key] = intent
            
            logger.info(f"✅ Intent: {intent['query_type']} (complexity: {intent['complexity']}, confidence: {intent['confidence']:.2f})")
            return intent
            
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            # Use rule-based as final fallback
            fallback = rule_based_intent if rule_based_intent else self._fallback_intent(question)
            return fallback
    
    def _rule_based_classify(self, question: str) -> Optional[Dict]:
        """
        IMPROVED: Rule-based classification using Turkish keywords
        Returns intent with high confidence if patterns are clear
        """
        question_lower = question.lower()
        
        # RANKING patterns - IMPROVED
        ranking_patterns = [
            # Turkish patterns
            (r'\ben\s+(çok|cok|fazla|yüksek|yuksek)\s+satan', 'ranking', 'desc', 'top'),
            (r'\ben\s+(az|düşük|dusuk)\s+satan', 'ranking', 'asc', 'bottom'),
            (r'\bilk\s+\d+\s+', 'ranking', 'desc', 'top'),
            (r'\btop\s+\d+', 'ranking', 'desc', 'top'),
            (r'\ben\s+(iyi|başarılı|basarili)', 'ranking', 'desc', 'top'),
            (r'\ben\s+(kötü|kotü|başarısız|basarisiz)', 'ranking', 'asc', 'bottom'),
            # English patterns
            (r'\btop\s+\d+', 'ranking', 'desc', 'top'),
            (r'\bbest\s+\d+', 'ranking', 'desc', 'top'),
            (r'\bworst\s+\d+', 'ranking', 'asc', 'bottom'),
            (r'\bhighest', 'ranking', 'desc', 'top'),
            (r'\blowest', 'ranking', 'asc', 'bottom'),
        ]
        
        for pattern, qtype, order, position in ranking_patterns:
            if re.search(pattern, question_lower):
                # Extract top_n
                top_n = None
                top_n_match = re.search(r'\b(\d+)\s+(urun|ürün|product|magaza|mağaza|store)', question_lower)
                if not top_n_match:
                    top_n_match = re.search(r'\b(ilk|top)\s+(\d+)', question_lower)
                    if top_n_match:
                        top_n = int(top_n_match.group(2))
                else:
                    top_n = int(top_n_match.group(1))
                
                # Detect tables
                tables = self._detect_tables(question_lower)
                
                return {
                    'complexity': 5,
                    'query_type': 'ranking',
                    'tables_needed': tables,
                    'time_dimension': self._has_time_dimension(question_lower),
                    'time_granularity': self._detect_time_granularity(question_lower),
                    'aggregation_type': 'sum',
                    'requires_comparison': False,
                    'comparison_type': 'none',
                    'top_n': top_n or 5,
                    'order_direction': order,
                    'confidence': 0.90
                }
        
        # COMPARISON patterns
        comparison_patterns = [
            (r'\bvs\b', 'comparison'),
            (r'\bkarşı\b|karsi', 'comparison'),
            (r'\bkarşılaştır|karsilastir', 'comparison'),
            (r'\bcompare', 'comparison'),
            (r'\bcomparison', 'comparison'),
            (r'\b(magaza|mağaza)\s+(ve|ile)\s+online', 'comparison'),
            (r'\bstore\s+and\s+online', 'comparison'),
        ]
        
        for pattern, qtype in comparison_patterns:
            if re.search(pattern, question_lower):
                tables = self._detect_tables(question_lower)
                
                # Detect comparison type
                comp_type = 'none'
                if re.search(r'(magaza|mağaza|store).+(online|internet)', question_lower):
                    comp_type = 'store_vs_online'
                    if 'FactOnlineSales' not in tables:
                        tables.append('FactOnlineSales')
                
                return {
                    'complexity': 7,
                    'query_type': 'comparison',
                    'tables_needed': tables,
                    'time_dimension': self._has_time_dimension(question_lower),
                    'time_granularity': self._detect_time_granularity(question_lower),
                    'aggregation_type': 'sum',
                    'requires_comparison': True,
                    'comparison_type': comp_type,
                    'top_n': None,
                    'order_direction': 'none',
                    'confidence': 0.85
                }
        
        # TREND patterns
        trend_patterns = [
            (r'\btrend', 'trend'),
            (r'\baylık|aylik|monthly', 'trend'),
            (r'\byıllık|yillik|yearly|annual', 'trend'),
            (r'\bhaftalık|haftalik|weekly', 'trend'),
            (r'\bçeyrek|ceyrek|quarter', 'trend'),
            (r'\bzaman\s+içinde|over\s+time', 'trend'),
        ]
        
        for pattern, qtype in trend_patterns:
            if re.search(pattern, question_lower):
                tables = self._detect_tables(question_lower)
                granularity = self._detect_time_granularity(question_lower)
                
                return {
                    'complexity': 6,
                    'query_type': 'trend',
                    'tables_needed': tables,
                    'time_dimension': True,
                    'time_granularity': granularity,
                    'aggregation_type': 'sum',
                    'requires_comparison': False,
                    'comparison_type': 'none',
                    'top_n': None,
                    'order_direction': 'asc',
                    'confidence': 0.85
                }
        
        # AGGREGATION patterns
        aggregation_patterns = [
            (r'\btoplam|total', 'aggregation'),
            (r'\bortalama|average|avg', 'aggregation'),
            (r'\bsayı|sayi|count', 'aggregation'),
            (r'\bsum\b', 'aggregation'),
        ]
        
        for pattern, qtype in aggregation_patterns:
            if re.search(pattern, question_lower):
                tables = self._detect_tables(question_lower)
                
                return {
                    'complexity': 3,
                    'query_type': 'aggregation',
                    'tables_needed': tables,
                    'time_dimension': self._has_time_dimension(question_lower),
                    'time_granularity': self._detect_time_granularity(question_lower),
                    'aggregation_type': 'sum',
                    'requires_comparison': False,
                    'comparison_type': 'none',
                    'top_n': None,
                    'order_direction': 'none',
                    'confidence': 0.75
                }
        
        # Not confident enough
        return None
    
    def _detect_tables(self, question_lower: str) -> List[str]:
        """Detect which tables are needed"""
        tables = []
        
        # Default to FactSales
        tables.append('FactSales')
        
        # Check for specific mentions
        if 'online' in question_lower or 'internet' in question_lower:
            if 'FactOnlineSales' not in tables:
                tables.append('FactOnlineSales')
        
        if any(word in question_lower for word in ['urun', 'ürün', 'product']):
            tables.append('DimProduct')
        
        if any(word in question_lower for word in ['musteri', 'müşteri', 'customer']):
            tables.append('DimCustomer')
        
        if any(word in question_lower for word in ['magaza', 'mağaza', 'store']):
            tables.append('DimStore')
        
        if any(word in question_lower for word in ['kategori', 'category']):
            tables.extend(['DimProductCategory', 'DimProductSubcategory'])
        
        return tables
    
    def _has_time_dimension(self, question_lower: str) -> bool:
        """Check if question has time dimension"""
        time_keywords = [
            'yil', 'yıl', 'year', 'ay', 'month', 'tarih', 'date',
            '2007', '2008', '2009', 'quarter', 'ceyrek', 'çeyrek'
        ]
        return any(word in question_lower for word in time_keywords)
    
    def _detect_time_granularity(self, question_lower: str) -> str:
        """Detect time granularity"""
        if any(word in question_lower for word in ['aylik', 'aylık', 'monthly', 'ay ']):
            return 'month'
        elif any(word in question_lower for word in ['yillik', 'yıllık', 'yearly', 'annual']):
            return 'year'
        elif any(word in question_lower for word in ['ceyrek', 'çeyrek', 'quarter']):
            return 'quarter'
        elif any(word in question_lower for word in ['hafta', 'week']):
            return 'week'
        elif self._has_time_dimension(question_lower):
            return 'year'
        return 'none'
    
    def _build_classification_prompt(self, question: str) -> str:
        """Build the intent classification prompt (unchanged)"""
        
        return f"""You are a SQL query intent analyzer for Contoso Retail Data Warehouse.

USER QUESTION: "{question}"

Analyze this question and return ONLY a valid JSON object with this exact structure:

{{
    "complexity": <integer 1-10>,
    "query_type": "<one of: ranking|comparison|aggregation|trend|filter|complex>",
    "tables_needed": ["<table names from available tables>"],
    "time_dimension": <true|false>,
    "time_granularity": "<year|month|day|none>",
    "aggregation_type": "<sum|avg|count|min|max|rank|none>",
    "requires_comparison": <true|false>,
    "comparison_type": "<store_vs_online|year_over_year|category|none>",
    "top_n": <integer or null>,
    "order_direction": "<asc|desc|none>",
    "confidence": <float 0.0-1.0>
}}

CRITICAL: Questions asking for "top N", "best", "highest", "en çok", "en yüksek" are RANKING queries, NOT comparison!

Return ONLY the JSON object, no other text or explanations.
"""
    
    def _parse_intent_response(self, response: str) -> Dict:
        """Parse LLM response into intent dict (unchanged)"""
        
        # Clean response
        response = response.strip()
        
        # Remove markdown code blocks
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        response = response.strip()
        
        # Parse JSON
        intent = json.loads(response)
        
        # Validate required fields
        required_fields = ["complexity", "query_type", "tables_needed", "confidence"]
        for field in required_fields:
            if field not in intent:
                raise ValueError(f"Missing required field: {field}")
        
        # Ensure complexity is in range
        intent["complexity"] = max(1, min(10, intent["complexity"]))
        
        # Ensure confidence is in range
        intent["confidence"] = max(0.0, min(1.0, intent.get("confidence", 0.5)))
        
        return intent
    
    def _fallback_intent(self, question: str) -> Dict:
        """
        Fallback intent classification using rule-based heuristics
        """
        logger.warning("⚠️ Using fallback intent classification")
        
        # Try rule-based first
        rule_based = self._rule_based_classify(question)
        if rule_based:
            return rule_based
        
        # Ultimate fallback
        question_lower = question.lower()
        
        return {
            "complexity": 5,
            "query_type": "aggregation",  # Safe default
            "tables_needed": ["FactSales"],
            "time_dimension": self._has_time_dimension(question_lower),
            "time_granularity": self._detect_time_granularity(question_lower),
            "aggregation_type": "sum",
            "requires_comparison": False,
            "comparison_type": "none",
            "top_n": None,
            "order_direction": "none",
            "confidence": 0.6
        }