"""
Intent Classifier: Routes user queries to appropriate handling paths.
Classifies queries as: factual, non_factual (opinion/creative), or unsafe.
"""

import logging
import re
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of intent classification."""
    intent: str  # "factual", "non_factual", "unsafe", "refusal_candidate"
    confidence: float  # 0.0 to 1.0
    domain: Optional[str] = None  # e.g., "science", "history", "technology"
    reasoning: str = ""


class IntentClassifier:
    """
    Rule-based query classifier for routing.
    Uses keyword patterns, regex, and heuristic rules derived from boundaries.json.
    Can be extended with ML model in future.
    """

    def __init__(self, boundaries_config: Dict, thresholds_config: Dict):
        """
        Initialize classifier.

        Args:
            boundaries_config: Loaded boundaries.json dict
            thresholds_config: Loaded thresholds.json dict
        """
        self.boundaries = boundaries_config
        self.thresholds = thresholds_config

        # Compile regex patterns for efficiency
        self.restricted_patterns = self._compile_restricted_patterns()
        self.factual_indicators = self._compile_factual_indicators()

        self.confidence_threshold = thresholds_config.get("intent_classification", {}).get(
            "confidence_threshold", 0.85
        )

    def _compile_restricted_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for restricted claim types."""
        patterns = []
        for claim in self.boundaries.get("restricted_claim_types", []):
            pattern = claim.get("pattern", "")
            if pattern:
                patterns.append(re.compile(pattern, re.IGNORECASE))
        return patterns

    def _compile_factual_indicators(self) -> List[re.Pattern]:
        """Compile patterns that indicate factual queries."""
        indicators = self.thresholds.get("intent_classification", {}).get("factual_indicators", [])
        return [re.compile(p, re.IGNORECASE) for p in indicators]

    def classify(self, query: str) -> ClassificationResult:
        """
        Classify a user query.

        Args:
            query: Raw user input string

        Returns:
            ClassificationResult with intent, confidence, domain, reasoning
        """
        query_lower = query.lower().strip()

        # Check for restricted claims first (highest priority)
        for pattern in self.restricted_patterns:
            if pattern.search(query):
                return ClassificationResult(
                    intent="refusal_candidate",
                    confidence=0.95,
                    domain=None,
                    reasoning=f"Matches restricted claim pattern: {pattern.pattern}",
                )

        # Heuristic scoring: factual vs non-factual
        factual_score = 0.0
        non_factual_score = 0.0

        # Indicator words
        for pattern in self.factual_indicators:
            if pattern.search(query_lower):
                factual_score += 0.3

        # Check for question words (who, what, when, where, why, how)
        question_words = {"what", "who", "when", "where", "why", "how", "which", "define", "explain"}
        if any(query_lower.startswith(q) for q in question_words):
            factual_score += 0.4

        # Non-factual indicators
        subjective_keywords = {
            "opinion", "think", "feel", "believe", "best", "worst", "favorite",
            "recommend", "should i", "advice", "personal"
        }
        for kw in subjective_keywords:
            if kw in query_lower:
                non_factual_score += 0.3

        creative_keywords = {"write", "create", "generate", "story", "poem", "fiction", "joke"}
        for kw in creative_keywords:
            if kw in query_lower:
                non_factual_score += 0.4
                break

        # Normalize scores
        total = factual_score + non_factual_score + 0.1  # base
        factual_confidence = factual_score / total if total > 0 else 0.5
        non_factual_confidence = non_factual_score / total if total > 0 else 0.5

        # Determine intent
        if factual_confidence > non_factual_confidence and factual_confidence >= self.confidence_threshold:
            intent = "factual"
            confidence = factual_confidence
        elif non_factual_confidence > factual_confidence:
            intent = "non_factual"
            confidence = non_factual_confidence
        else:
            # Uncertain: default to factual but flag low confidence
            intent = "factual"
            confidence = max(factual_confidence, 0.6)

        # Domain detection (optional)
        domain = self._detect_domain(query_lower)

        reasoning = f"Factual={factual_confidence:.2f}, Non-factual={non_factual_confidence:.2f}"
        return ClassificationResult(
            intent=intent,
            confidence=confidence,
            domain=domain,
            reasoning=reasoning,
        )

    def _detect_domain(self, query: str) -> Optional[str]:
        """
        Detect likely domain from query keywords.
        Maps query terms to allowed domains from boundaries.
        """
        domain_keywords = {
            "science": ["physics", "chemistry", "biology", "scientific", "experiment"],
            "technology": ["computer", "software", "hardware", "internet", "ai", "algorithm"],
            "history": ["history", "ancient", "war", "empire", "century"],
            "geography": ["country", "capital", "mountain", "river", "map"],
            "mathematics": ["math", "equation", "theorem", "geometry", "algebra"],
            "medicine": ["medical", "disease", "treatment", "symptom"],
            "law": ["law", "legal", "court", "rights"],
            "economics": ["economics", "market", "finance", "trade"],
        }

        query_words = set(query.split())
        best_domain = None
        best_score = 0

        for domain, keywords in domain_keywords.items():
            score = sum(1 for kw in keywords if kw in query)
            if score > best_score:
                best_score = score
                best_domain = domain

        return best_domain if best_score >= 1 else None

    def is_factual(self, query: str, min_confidence: float = 0.85) -> Tuple[bool, Optional[str]]:
        """
        Simple boolean check: is this query factual enough to process?

        Args:
            query: User query
            min_confidence: Minimum confidence threshold

        Returns:
            (is_factual, domain_or_None)
        """
        result = self.classify(query)
        if result.intent == "refusal_candidate":
            return False, None
        return result.confidence >= min_confidence, result.domain


def build_intent_classifier(config_dir: str = "config") -> IntentClassifier:
    """
    Factory function to build classifier from config files.

    Args:
        config_dir: Directory containing boundaries.json and thresholds.json

    Returns:
        Initialized IntentClassifier
    """
    import json

    boundaries_path = f"{config_dir}/boundaries.json"
    thresholds_path = f"{config_dir}/thresholds.json"

    with open(boundaries_path, "r") as f:
        boundaries = json.load(f)

    with open(thresholds_path, "r") as f:
        thresholds = json.load(f)

    return IntentClassifier(boundaries, thresholds)
