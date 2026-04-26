"""
Assistant Core: Orchestration pipeline for query processing.
Coordinates intent classification, retrieval, generation, validation, and formatting.
"""

import logging
import time
import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .intent_classifier import IntentClassifier, ClassificationResult
from retrieval.vector_store import VectorStore
from retrieval.searcher import HybridSearcher
from retrieval.ingest_service import IngestService
from models.wrapper import LLMWrapper, LLMConfig
from models.constrained_gen import ConstrainedGenerator, GuardrailConfig
from models.prompt_templates import get_prompt_template
from core.fact_checker import FactChecker
from core.contradiction import ContradictionDetector
from core.auditor import AuditLogger
from utils.formatter import OutputFormatter, FormattedResponse, SourceMetadata
from utils.sanitizer import PIIRedactor
from utils.cache import Cache

logger = logging.getLogger(__name__)


@dataclass
class ProcessingContext:
    """Context carrying data through the pipeline."""
    query: str
    query_hash: str
    user_id: Optional[str]
    intent: ClassificationResult
    retrieved_sources: List[Dict[str, Any]]
    generated_response: Optional[str] = None
    validation_results: Optional[List[Dict]] = None
    contradictions: Optional[List] = None
    final_response: Optional[FormattedResponse] = None
    timing: Dict[str, float] = None
    warnings: List[str] = None


class VerityAssistant:
    """
    Main orchestration engine for the Verity Assistant.
    Implements full pipeline: classify → retrieve → generate → validate → format.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        llm_wrapper: LLMWrapper,
        config: Dict[str, Any],
        cache: Optional[Cache] = None,
    ):
        """
        Initialize assistant.

        Args:
            vector_store: Initialized VectorStore
            llm_wrapper: LLM provider wrapper
            config: Global application configuration dict
            cache: Optional cache instance
        """
        self.vector_store = vector_store
        self.llm = llm_wrapper
        self.config = config
        self.cache = cache or Cache()

        # Subsystems
        self.intent_classifier = IntentClassifier(
            config.get("boundaries", {}),
            config.get("thresholds", {}),
        )
        self.searcher = HybridSearcher(vector_store=vector_store)
        self.fact_checker = FactChecker(
            model_name=config.get("nli_model", "roberta-large-mnli"),
            threshold=config.get("validation", {}).get("nli_threshold", 0.8),
        )
        self.contradiction_detector = ContradictionDetector(
            model_name=config.get("nli_model", "roberta-large-mnli"),
            contradiction_threshold=config.get("validation", {}).get("contradiction_threshold", 0.8),
        )
        self.auditor = AuditLogger(
            db_path=config.get("audit_db_path", "data/audit/audit.db"),
            hmac_key=config.get("audit_hmac_key"),
        )
        self.formatter = OutputFormatter(
            model_version=self.llm.config.get("default_provider", "openai"),
            min_high_confidence_sources=config.get("confidence_scoring", {}).get("high_min_sources", 3),
            min_medium_confidence_sources=config.get("confidence_scoring", {}).get("medium_min_sources", 1),
        )
        self.pii_redactor = PIIRedactor()

        # Generator with guardrails
        guardrail_config = GuardrailConfig(
            temperature=config.get("generation", {}).get("temperature", 0.0),
            max_tokens=config.get("generation", {}).get("max_tokens", 1024),
            stop_sequences=config.get("generation", {}).get("stop_sequences"),
        )
        self.generator = ConstrainedGenerator(llm_wrapper, guardrail_config)

        logger.info("VerityAssistant initialized")

    def process_query(
        self,
        query: str,
        user_id: Optional[str] = None,
        strict_mode: bool = False,
        top_k: int = 5,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point: process user query end-to-end.

        Args:
            query: User question
            user_id: Optional user/session identifier
            strict_mode: Enforce high-confidence-only answers
            top_k: Number of sources to retrieve
            model_override: Override LLM model

        Returns:
            Structured response dict
        """
        context = ProcessingContext(
            query=query,
            query_hash=self._hash_query(query),
            user_id=user_id,
            intent=None,
            retrieved_sources=[],
            timing={},
            warnings=[],
        )

        start_total = time.time()

        try:
            # Stage 1: Intent classification
            t0 = time.time()
            intent = self.intent_classifier.classify(query)
            context.intent = intent
            context.timing["intent_classification_ms"] = (time.time() - t0) * 1000

            # Log classification
            self.auditor.log(
                event_type="query_classified",
                data={"query": query, "intent": intent.intent, "confidence": intent.confidence},
                user_id=user_id,
                query_hash=context.query_hash,
            )

            # Reject non-factual queries
            if intent.intent == "refusal_candidate":
                refusal_msg = "I cannot answer that type of question as it falls outside factual domains."
                return self._build_refusal_response(query, refusal_msg, context)

            if intent.intent == "non_factual":
                refusal_msg = (
                    "I'm a factual assistant and cannot provide opinions, recommendations, or creative content. "
                    "I can help with verifiable factual questions instead."
                )
                return self._build_refusal_response(query, refusal_msg, context)

            # Stage 2: Retrieval
            t0 = time.time()
            retrieved = self._retrieve_sources(query, top_k=top_k)
            context.retrieved_sources = retrieved
            context.timing["retrieval_ms"] = (time.time() - t0) * 1000

            if not retrieved:
                return self._build_no_evidence_response(query, context)

            # Stage 3: Constrained Generation
            t0 = time.time()
            response_text = self._generate_answer(query, retrieved, strict_mode, model_override)
            context.generated_response = response_text
            context.timing["generation_ms"] = (time.time() - t0) * 1000

            # Stage 4: Fact Validation
            t0 = time.time()
            validation_passed, validation_results = self._validate_response(response_text, retrieved)
            context.validation_results = validation_results
            context.timing["validation_ms"] = (time.time() - t0) * 1000

            # If validation fails after retries, refuse
            if not validation_passed:
                context.warnings.append("Fact validation failed; some claims unsupported.")
                # Could trigger regeneration here; currently passes with flag

            # Stage 5: Contradiction Detection
            t0 = time.time()
            if len(retrieved) > 1:
                excerpts = [s.get("text", "") for s in retrieved]
                contradictions = self.contradiction_detector.detect_pairwise(excerpts)
                context.contradictions = contradictions
                if contradictions:
                    context.warnings.append(f"Source conflicts detected: {len(contradictions)} contradictions")
            context.timing["contradiction_ms"] = (time.time() - t0) * 1000

            # Stage 6: Format output
            t0 = time.time()
            formatted = self.formatter.format(
                raw_answer=response_text,
                retrieved_sources=retrieved,
                fact_check_results=validation_results,
                model_version=model_override or "gpt-4-turbo",
                query_hash=context.query_hash,
                processing_time_ms=int((time.time() - start_total) * 1000),
                warnings=context.warnings,
                extra_metadata={"intent": intent.intent, "strict_mode": strict_mode},
            )
            context.final_response = formatted
            context.timing["formatting_ms"] = (time.time() - t0) * 1000

            # Audit successful response
            self.auditor.log(
                event_type="response_generated",
                data={
                    "response_id": formatted.id,
                    "confidence": formatted.confidence,
                    "num_sources": len(retrieved),
                    "processing_time_ms": formatted.processing_time_ms,
                    "validation_passed": validation_passed,
                },
                user_id=user_id,
                query_hash=context.query_hash,
            )

            return formatted.to_dict()

        except Exception as e:
            logger.error(f"Query processing failed: {e}", exc_info=True)
            self.auditor.log(
                event_type="processing_error",
                data={"query": query, "error": str(e)},
                user_id=user_id,
                query_hash=context.query_hash,
            )
            raise

    def _retrieve_sources(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Perform hybrid retrieval. Checks cache first.

        Returns:
            List of source dicts: {id, title, excerpt, text, score, ...}
        """
        cache_key = f"retrieval:{self._hash_query(query)}:{top_k}"

        def _do_retrieve():
            results = self.searcher.search(query, top_k=top_k)
            # Convert (doc_id, score, metadata, component_scores) to uniform dict
            return [
                {
                    "id": i + 1,
                    "score": score,
                    **meta,  # includes 'text', 'title', 'url', etc.
                }
                for i, (doc_id, score, meta, _) in enumerate(results)
            ]

        sources = self.cache.get_or_compute(cache_key, _do_retrieve, ttl=3600)
        return sources

    def _generate_answer(
        self,
        query: str,
        sources: List[Dict[str, Any]],
        strict_mode: bool,
        model_override: Optional[str],
    ) -> str:
        """Generate LLM answer using constrained generator."""
        # Prepare source list for prompt
        formatted_sources = [
            {
                "id": s["id"],
                "title": s.get("title", "Unknown"),
                "excerpt": s.get("text", s.get("excerpt", ""))[:1000],
                "url": s.get("url", ""),
            }
            for s in sources
        ]

        prompt, config = self.generator.format_prompt(query, formatted_sources, strict_mode)

        llm_response = self.llm.generate(
            prompt=prompt,
            model=model_override,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stop_sequences=config.stop_sequences,
        )

        return llm_response.content.strip()

    def _validate_response(
        self,
        response: str,
        sources: List[Dict[str, Any]],
    ) -> Tuple[bool, List[Dict]]:
        """
        Validate each claim against source excerpts using NLI.

        Returns:
            (all_claims_validated, per_claim_results)
        """
        # Split response into sentences (simple)
        import re
        sentences = [s.strip() for s in re.split(r"[.!?]+", response) if s.strip()]

        source_excerpts = [s.get("text", s.get("excerpt", "")) for s in sources]

        all_results = []
        for claim in sentences:
            result = self.fact_checker.check_claim_against_sources(claim, source_excerpts)
            all_results.append(result.to_dict())

        passed = all(r["entailed"] for r in all_results)
        return passed, all_results

    def _build_refusal_response(self, query: str, message: str, context: ProcessingContext) -> Dict[str, Any]:
        """Construct refusal message with metadata."""
        context.timing["total_ms"] = int((time.time() - time.time() + 0) * 1000)  # approx
        response = FormattedResponse(
            id=str(uuid.uuid4()),
            answer=message,
            confidence="Low",
            sources=[],
            gaps=["Query type outside factual scope"],
            warnings=[],
            model_version=self.config.get("llm", {}).get("default_provider", "none"),
            timestamp=datetime.utcnow().isoformat() + "Z",
            processing_time_ms=int(sum(context.timing.values()) if context.timing else 0),
            query_hash=context.query_hash,
            metadata={"refusal_reason": context.intent.intent if context.intent else "unknown"},
        )
        self.auditor.log("response_refused", {"query": query, "reason": message}, user_id=context.user_id, query_hash=context.query_hash)
        return response.to_dict()

    def _build_no_evidence_response(self, query: str, context: ProcessingContext) -> Dict[str, Any]:
        """Construct 'no sources' refusal."""
        message = "I don't have enough verified information to answer this. The knowledge base does not contain relevant data."
        return self._build_refusal_response(query, message, context)

    def _hash_query(self, query: str) -> str:
        """Compute SHA-256 hash of query."""
        return hashlib.sha256(query.encode("utf-8")).hexdigest()

    def add_document(self, file_path: str) -> List[int]:
        """
        External API: ingest new document into knowledge base.

        Returns:
            List of new document IDs added
        """
        ingest_service = IngestService(self.vector_store, raw_corpus_dir=self.config.get("knowledge_dir", "knowledge/raw"))
        return ingest_service.ingest_file(file_path, persist=False)
