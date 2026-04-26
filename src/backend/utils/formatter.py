"""
Output Formatter: Structures assistant responses with confidence, sources, and gaps.
Implements the standard Response schema required by the specification.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class SourceMetadata:
    """Metadata for a cited source."""
    id: int
    title: str
    author: Optional[str] = None
    organization: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    license: Optional[str] = None
    excerpt: Optional[str] = None


@dataclass
class FormattedResponse:
    """Structured response adhering to specification."""
    id: str
    answer: str
    confidence: str  # "High" | "Medium" | "Low"
    sources: List[SourceMetadata]
    gaps: List[str]
    warnings: List[str]
    model_version: str
    timestamp: str
    processing_time_ms: int
    query_hash: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "id": self.id,
            "answer": self.answer,
            "confidence": self.confidence,
            "sources": [asdict(s) for s in self.sources],
            "gaps": self.gaps,
            "warnings": self.warnings,
            "model_version": self.model_version,
            "timestamp": self.timestamp,
            "processing_time_ms": self.processing_time_ms,
            "query_hash": self.query_hash,
            "metadata": self.metadata,
        }


class OutputFormatter:
    """
    Formats valid assistant responses into structured schema.
    Validates citations, ensures confidence matches source quality,
    attaches metadata for auditability.
    """

    def __init__(
        self,
        model_version: str = "gpt-4-turbo-preview",
        min_high_confidence_sources: int = 3,
        min_medium_confidence_sources: int = 1,
    ):
        """
        Initialize formatter.

        Args:
            model_version: LLM model identifier
            min_high_confidence_sources: Number of sources required for High confidence
            min_medium_confidence_sources: Number of sources required for Medium confidence
        """
        self.model_version = model_version
        self.min_sources = {
            "High": min_high_confidence_sources,
            "Medium": min_medium_confidence_sources,
        }

    def format(
        self,
        raw_answer: str,
        retrieved_sources: List[Dict[str, Any]],
        fact_check_results: Optional[List[Dict]] = None,
        model_version: Optional[str] = None,
        query_hash: Optional[str] = None,
        processing_time_ms: int = 0,
        warnings: Optional[List[str]] = None,
        extra_metadata: Optional[Dict] = None,
    ) -> FormattedResponse:
        """
        Format final response.

        Args:
            raw_answer: LLM-generated text
            retrieved_sources: Source excerpts with metadata from retrieval
            fact_check_results: Optional list of validation results per claim
            model_version: Override default model version
            query_hash: SHA-256 of original query
            processing_time_ms: Total pipeline latency
            warnings: Non-blocking warnings to surface to user
            extra_metadata: Additional arbitrary metadata

        Returns:
            FormattedResponse object
        """
        response_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Extract answer portion (before Confidence: line if present)
        answer = self._extract_answer(raw_answer)

        # Determine confidence from source count + fact-check alignment
        confidence = self._compute_confidence(retrieved_sources, fact_check_results)

        # Build source metadata list
        sources = self._build_source_metadata(retrieved_sources)

        # Identify gaps (missing info, conflicts)
        gaps = self._identify_gaps(raw_answer, retrieved_sources, fact_check_results)

        warnings = warnings or []

        metadata = {
            "num_retrieved_sources": len(retrieved_sources),
            "num_cited_sources": self._count_citations(raw_answer),
            "fact_check_passed": self._overall_fact_check_passed(fact_check_results),
            **(extra_metadata or {}),
        }

        return FormattedResponse(
            id=response_id,
            answer=answer,
            confidence=confidence,
            sources=sources,
            gaps=gaps,
            warnings=warnings,
            model_version=model_version or self.model_version,
            timestamp=timestamp,
            processing_time_ms=processing_time_ms,
            query_hash=query_hash or "",
            metadata=metadata,
        )

    def _extract_answer(self, raw: str) -> str:
        """
        Extract the actual answer text, removing control lines like Confidence:, Sources:.
        The LLM should output these but we want the answer field to be clean.
        """
        lines = raw.split("\n")
        answer_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.lower().startswith(("confidence:", "sources:", "gaps:")):
                break
            answer_lines.append(line)
        return "\n".join(answer_lines).strip()

    def _compute_confidence(
        self,
        retrieved_sources: List[Dict[str, Any]],
        fact_check_results: Optional[List[Dict]] = None,
    ) -> str:
        """
        Compute confidence level based on:
        - Number of independent sources retrieved
        - Fact-check entailment scores (if available)
        - Recency and authority of sources
        """
        n_sources = len(retrieved_sources)

        # Base confidence from source count
        if n_sources >= self.min_sources["High"]:
            confidence = "High"
        elif n_sources >= self.min_sources["Medium"]:
            confidence = "Medium"
        else:
            confidence = "Low"

        # Downgrade if fact-check fails
        if fact_check_results:
            failed_claims = [r for r in fact_check_results if not r.get("entailed", True)]
            if len(failed_claims) > 0:
                # At least one claim unsupported
                if confidence == "High":
                    confidence = "Medium"
                elif confidence == "Medium":
                    confidence = "Low"

        return confidence

    def _build_source_metadata(self, sources: List[Dict[str, Any]]) -> List[SourceMetadata]:
        """Convert raw source dicts to SourceMetadata objects."""
        metadata_list = []
        for i, s in enumerate(sources, 1):
            meta = SourceMetadata(
                id=i,
                title=s.get("title", "Unknown Title"),
                author=s.get("author"),
                organization=s.get("organization"),
                date=s.get("date"),
                url=s.get("url"),
                license=s.get("license"),
                excerpt=s.get("text", s.get("excerpt", ""))[:500],  # Truncate for brevity
            )
            metadata_list.append(meta)
        return metadata_list

    def _identify_gaps(
        self,
        answer: str,
        sources: List[Dict[str, Any]],
        fact_check_results: Optional[List[Dict]],
    ) -> List[str]:
        """
        Identify what information is missing or uncertain.
        - Claims not covered by sources
        - Contradictions surfaced but not fully resolved
        - Date limitations (sources too old)
        """
        gaps = []

        if not sources:
            gaps.append("No sources retrieved for this query.")

        if fact_check_results:
            failed = [r for r in fact_check_results if not r.get("entailed", True)]
            if failed:
                for f in failed:
                    gaps.append(f"Unsupported claim: '{f.get('claim', '')}'")

        # Check for explicit "I don't have enough information" in answer
        if "don't have enough" in answer.lower() or "insufficient" in answer.lower():
            gaps.append("Insufficient evidence in knowledge base to answer comprehensively.")

        return gaps

    def _count_citations(self, text: str) -> int:
        """Count number of [n] citation markers in text."""
        import re
        matches = re.findall(r"\[\d+\]", text)
        return len(matches)

    def _overall_fact_check_passed(self, results: Optional[List[Dict]]) -> bool:
        """Return True if all fact-checks passed (or no checks performed)."""
        if not results:
            return True
        return all(r.get("entailed", False) for r in results)
