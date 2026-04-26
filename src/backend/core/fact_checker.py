"""
Fact Checker: Validates generated claims against retrieved source excerpts
using Natural Language Inference (NLI) model for entailment verification.
"""

import logging
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)


@dataclass
class FactCheckResult:
    """Result of fact-checking a claim against sources."""
    claim: str
    entailed: bool
    entailment_score: float
    contradiction_score: float
    neutral_score: float
    supporting_source_indices: List[int]  # indices of supporting excerpts
    total_sources: int
    rationale: str = ""

    def to_dict(self) -> Dict:
        return {
            "claim": self.claim,
            "entailed": self.entailed,
            "entailment_score": float(self.entailment_score),
            "contradiction_score": float(self.contradiction_score),
            "neutral_score": float(self.neutral_score),
            "supporting_source_indices": self.supporting_source_indices,
            "total_sources": self.total_sources,
            "rationale": self.rationale,
        }


class FactChecker:
    """
    Uses NLI model to determine if generated claims are entailed by retrieved sources.
    Model: roberta-large-mnli or similar (3-class: entailment/contradiction/neutral).
    """

    def __init__(
        self,
        model_name: str = "roberta-large-mnli",
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        batch_size: int = 10,
        threshold: float = 0.8,
    ):
        """
        Initialize fact checker.

        Args:
            model_name: HuggingFace NLI model identifier
            device: "cuda" or "cpu"
            batch_size: Number of (claim, source) pairs to evaluate per forward pass
            threshold: Minimum entailment probability for claim to pass
        """
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.threshold = threshold

        logger.info(f"Loading NLI model {model_name} on {device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(device)
        self.model.eval()
        logger.info("NLI model loaded successfully")

    def check_claim_against_sources(
        self,
        claim: str,
        source_excerpts: List[str],
    ) -> FactCheckResult:
        """
        Evaluate entailment of a claim against each source excerpt.

        Args:
            claim: Generated claim to verify
            source_excerpts: List of retrieved source excerpts

        Returns:
            FactCheckResult with entailment scores and supporting sources
        """
        if not source_excerpts:
            return FactCheckResult(
                claim=claim,
                entailed=False,
                entailment_score=0.0,
                contradiction_score=0.0,
                neutral_score=1.0,
                supporting_source_indices=[],
                total_sources=0,
                rationale="No source excerpts provided",
            )

        # Batch evaluate (claim, source) pairs
        entail_scores = []
        contra_scores = []
        neutral_scores = []

        with torch.no_grad():
            for i in range(0, len(source_excerpts), self.batch_size):
                batch_sources = source_excerpts[i : i + self.batch_size]
                inputs = self.tokenizer(
                    [claim] * len(batch_sources),
                    batch_sources,
                    padding=True,
                    truncation=True,
                    return_tensors="pt",
                    max_length=512,
                ).to(self.device)

                outputs = self.model(**inputs)
                probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()

                # NLI models typically: 0=contradiction, 1=neutral, 2=entailment
                for prob in probs:
                    contra_scores.append(float(prob[0]))
                    neutral_scores.append(float(prob[1]))
                    entail_scores.append(float(prob[2]))

        # Aggregate: claim passes if any source has entailment > threshold
        supporting_indices = [
            i for i, score in enumerate(entail_scores) if score >= self.threshold
        ]
        max_entail = max(entail_scores) if entail_scores else 0.0
        max_contra = max(contra_scores) if contra_scores else 0.0
        max_neutral = max(neutral_scores) if neutral_scores else 1.0

        entailed = len(supporting_indices) > 0

        rationale = (
            f"Claim entailed by {len(supporting_indices)}/{len(source_excerpts)} sources "
            f"(max entailment={max_entail:.3f}, max contradiction={max_contra:.3f})"
        )

        return FactCheckResult(
            claim=claim,
            entailed=entailed,
            entailment_score=max_entail,
            contradiction_score=max_contra,
            neutral_score=max_neutral,
            supporting_source_indices=supporting_indices,
            total_sources=len(source_excerpts),
            rationale=rationale,
        )

    def check_claims_batch(
        self,
        claims: List[str],
        source_excerpts: List[str],
    ) -> List[FactCheckResult]:
        """
        Batch fact-check multiple claims against same set of sources.

        Args:
            claims: List of claims to verify
            source_excerpts: Shared source excerpts for all claims

        Returns:
            List of FactCheckResult (one per claim)
        """
        results = []
        for claim in claims:
            result = self.check_claim_against_sources(claim, source_excerpts)
            results.append(result)
        return results

    def validate_full_response(
        self,
        generated_text: str,
        source_excerpts: List[str],
        sentence_split: bool = True,
    ) -> Tuple[bool, List[FactCheckResult], str]:
        """
        Validate entire response by checking each sentence or claim.

        Args:
            generated_text: Full assistant response
            source_excerpts: Retrieved excerpts used for generation
            sentence_split: Split by sentence for granular checking

        Returns:
            (overall_passed, list_of_results, failure_rationale)
        """
        if sentence_split:
            import re

            sentences = re.split(r"[.!?]+", generated_text)
            sentences = [s.strip() for s in sentences if s.strip()]
        else:
            sentences = [generated_text]

        all_results = self.check_claims_batch(sentences, source_excerpts)

        failed = [r for r in all_results if not r.entailed]
        passed = len(all_results) - len(failed)

        overall_passed = len(failed) == 0

        if failed:
            failure_rationale = (
                f"{passed}/{len(all_results)} claims validated. "
                f"Unsupported claims: {[r.claim for r in failed[:3]]}"
            )
        else:
            failure_rationale = f"All {len(all_results)} claims validated."

        return overall_passed, all_results, failure_rationale
