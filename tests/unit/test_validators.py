"""
Unit tests for core assistant modules.
Execute: pytest tests/unit/ -v
"""

import pytest
from src.backend.core.intent_classifier import IntentClassifier, ClassificationResult

# ── Intent Classifier ──────────────────────────────────────────────────────────

def test_classifier_initialization():
    boundaries = {
        "restricted_claim_types": [
            {"type": "medical_advice", "pattern": "\\b(diagnose|treatment)\\b"}
        ]
    }
    thresholds = {
        "intent_classification": {
            "confidence_threshold": 0.85,
            "factual_indicators": ["what is", "how does"],
        }
    }
    clf = IntentClassifier(boundaries, thresholds)
    assert clf.confidence_threshold == 0.85


def test_factual_query_classification():
    boundaries = {
        "restricted_claim_types": []
    }
    thresholds = {
        "intent_classification": {
            "confidence_threshold": 0.7,
            "factual_indicators": [],
        }
    }
    clf = IntentClassifier(boundaries, thresholds)
    result = clf.classify("What is photosynthesis?")
    assert result.intent == "factual"
    assert result.confidence > 0.7


def test_opinion_query_classification():
    boundaries = {
        "restricted_claim_types": [
            {"type": "personal_opinion", "pattern": "\\b(best|recommend|favorite)\\b"}
        ]
    }
    thresholds = {
        "intent_classification": {
            "confidence_threshold": 0.7,
            "factual_indicators": [],
        }
    }
    clf = IntentClassifier(boundaries, thresholds)
    result = clf.classify("What is the best movie?")
    assert result.intent == "refusal_candidate" or result.intent == "non_factual"
