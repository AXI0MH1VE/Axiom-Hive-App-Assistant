"""
Knowledge Service: High-level orchestration for retrieval, generation, validation.
Facade over individual modules; handles caching and batch operations.
"""

import logging
from typing import Dict, Any, List, Optional

from retrieval.vector_store import VectorStore
from retrieval.searcher import HybridSearcher
from models.wrapper import LLMWrapper
from models.constrained_gen import ConstrainedGenerator
from core.assistant import VerityAssistant
from utils.cache import Cache

logger = logging.getLogger(__name__)


class KnowledgeService:
    """
    Public API for knowledge-base queries.
    Encapsulates assistant instance; exposes simplified interface.
    """

    def __init__(
        self,
        assistant: VerityAssistant,
        cache: Optional[Cache] = None,
    ):
        """
        Initialize knowledge service.

        Args:
            assistant: VerityAssistant instance
            cache: Optional external cache
        """
        self.assistant = assistant
        self.cache = cache or assistant.cache

    def query(
        self,
        question: str,
        user_id: Optional[str] = None,
        strict: bool = False,
        top_k: int = 5,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a natural language query.

        Args:
            question: User's question
            user_id: Optional user identifier
            strict: If True, require >2 sources for answer
            top_k: Number of sources to retrieve
            model: Override default LLM model

        Returns:
            Structured response dict
        """
        logger.info(f"Processing query: {question[:60]}")
        return self.assistant.process_query(
            query=question,
            user_id=user_id,
            strict_mode=strict,
            top_k=top_k,
            model_override=model,
        )

    def batch_query(
        self,
        questions: List[str],
        user_id: Optional[str] = None,
        strict: bool = False,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Process multiple questions in batch (sequential; parallel possible future).
        """
        results = []
        for q in questions:
            result = self.query(q, user_id=user_id, strict=strict, top_k=top_k)
            results.append(result)
        return results

    def search_only(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Perform retrieval only, without LLM generation.
        Useful for exploration and debugging.
        """
        searcher = self.assistant.searcher
        raw_results = searcher.search(query, top_k=top_k)

        # Return simplified structure
        return [
            {
                "id": r[0],
                "score": r[1],
                "title": r[2].get("title", ""),
                "excerpt": r[2].get("text", "")[:300],
                "source": r[2].get("source", "unknown"),
            }
            for r in raw_results
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Return system statistics."""
        return {
            "vector_store": self.assistant.vector_store.get_stats(),
            "cache": self.cache.info(),
            "audit_log": self.assistant.auditor.get_stats(),
        }
