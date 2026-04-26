"""
Sanitizer: PII detection and redaction using Presidio.
Ensures no personal data leaked into logs or responses.
"""

import logging
from typing import List, Dict, Any, Tuple
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

logger = logging.getLogger(__name__)


class PIIRedactor:
    """
    Detects and redacts personally identifiable information (PII) from text.
    Uses Microsoft Presidio for comprehensive entity recognition.
    """

    def __init__(self, language: str = "en"):
        """
        Initialize PII redactor.

        Args:
            language: ISO language code (e.g., "en")
        """
        self.language = language
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        logger.info("PII redactor initialized with Presidio")

    def detect_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect PII entities in text.

        Returns:
            List of entity dicts with start, end, type, score
        """
        results = self.analyzer.analyze(text=text, language=self.language, entities=None)
        return [r.to_dict() for r in results]

    def redact(self, text: str, anonymize: bool = False) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Redact or anonymize PII from text.

        Args:
            text: Input text
            anonymize: If True, replace with fake equivalents; if False, replace with "[REDACTED]"

        Returns:
            (redacted_text, detected_entities)
        """
        entities = self.analyzer.analyze(text=text, language=self.language)

        if anonymize:
            # Replace with realistic fake data (presidio-anonymizer)
            result = self.anonymizer.anonymize(text=text, analyzer_results=entities)
            redacted = result.text
        else:
            # Simple redaction
            redacted = text
            for entity in sorted(entities, key=lambda e: e.start, reverse=True):
                redacted = redacted[: entity.start] + f"[{entity.entity_type.upper()}_REDACTED]" + redacted[entity.end :]

        return redacted, [e.to_dict() for e in entities]

    def redact_if_contains_pii(self, text: str) -> Tuple[bool, str, List[Dict]]:
        """
        Check if text contains PII; if so, redact and return flag.

        Returns:
            (had_pii, redacted_text, entities)
        """
        entities = self.detect_entities(text)
        if entities:
            redacted, _ = self.redact(text, anonymize=False)
            return True, redacted, entities
        return False, text, []
