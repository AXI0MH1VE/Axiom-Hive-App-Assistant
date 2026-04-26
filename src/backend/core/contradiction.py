"""
Contradiction Detector: Identifies conflicting claims across retrieved sources.
Uses NLI model pairwise to surface disagreements before synthesis.
"""

import logging
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import itertools
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)


@dataclass
class ContradictionResult:
    """Result of contradiction detection."""
    source_a_idx: int
    source_b_idx: int
    claim_a: str
    claim_b: str
    contradiction_score: float  # higher = more contradictory
    entailment_a_to_b: float
    entailment_b_to_a: float
    rationale: str = ""

    def to_dict(self) -> Dict:
        return {
            "source_a_idx": self.source_a_idx,
            "source_b_idx": self.source_b_idx,
            "claim_a": self.claim_a,
            "claim_b": self.claim_b,
            "contradiction_score": float(self.contradiction_score),
            "entailment_a_to_b": float(self.entailment_a_to_b),
            "entailment_b_to_a": float(self.entailment_b_to_a),
            "rationale": self.rationale,
        }


class ContradictionDetector:
    """
    Detects contradictions among retrieved source excerpts using NLI.
    Essential for surfacing conflicts without silent source selection.
    """

    def __init__(
        self,
        model_name: str = "roberta-large-mnli",
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        contradiction_threshold: float = 0.7,
    ):
        """
        Initialize contradiction detector.

        Args:
            model_name: HuggingFace NLI model
            device: "cuda" or "cpu"
            contradiction_threshold: Minimum contradiction probability to flag
        """
        self.model_name = model_name
        self.device = device
        self.threshold = contradiction_threshold

        logger.info(f"Loading NLI model {model_name} for contradiction detection...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(device)
        self.model.eval()
        logger.info("NLI model loaded")

    def detect_pairwise(
        self,
        excerpts: List[str],
        max_pairs: int = 100,
    ) -> List[ContradictionResult]:
        """
        Detect contradictions among all pairs of excerpts.

        Args:
            excerpts: List of source excerpt texts
            max_pairs: Limit number of pairs to check (for large candidate sets)

        Returns:
            List of ContradictionResult where contradiction_score >= threshold
        """
        n = len(excerpts)
        if n < 2:
            return []

        # Generate candidate pairs (limiting if too many)
        pairs = list(itertools.combinations(range(n), 2))
        if len(pairs) > max_pairs:
            import random
            pairs = random.sample(pairs, max_pairs)
            logger.info(f"Sampled {max_pairs} pairs from {len(pairs)} total for contradiction check")

        contradictions = []

        with torch.no_grad():
            for i, j in pairs:
                text_a = excerpts[i]
                text_b = excerpts[j]

                # Check A → B (does A entail B? contradiction if A contradicts B)
                contra_ab, entail_a2b, contra_ba, entail_b2a = self._pairwise_nli(text_a, text_b)

                # Contradiction detected if either direction exceeds threshold
                if contra_ab >= self.threshold or contra_ba >= self.threshold:
                    result = ContradictionResult(
                        source_a_idx=i,
                        source_b_idx=j,
                        claim_a=text_a[:200],  # truncated for brevity
                        claim_b=text_b[:200],
                        contradiction_score=max(contra_ab, contra_ba),
                        entailment_a_to_b=entail_a2b,
                        entailment_b_to_a=entail_b2a,
                        rationale=f"Mutual contradiction detected (score={max(contra_ab, contra_ba):.3f})",
                    )
                    contradictions.append(result)

        logger.info(f"Detected {len(contradictions)} contradictions among {n} excerpts")
        return contradictions

    def _pairwise_nli(self, text_a: str, text_b: str) -> Tuple[float, float, float, float]:
        """
        Compute NLI scores for text_a vs text_b and text_b vs text_a.

        Returns:
            (contra_ab, entail_a2b, contra_ba, entail_b2a)
        """
        inputs_ab = self.tokenizer(
            text_a, text_b, return_tensors="pt", truncation=True, max_length=512
        ).to(self.device)
        outputs_ab = self.model(**inputs_ab)
        probs_ab = torch.softmax(outputs_ab.logits, dim=-1).cpu().numpy()[0]

        inputs_ba = self.tokenizer(
            text_b, text_a, return_tensors="pt", truncation=True, max_length=512
        ).to(self.device)
        outputs_ba = self.model(**inputs_ba)
        probs_ba = torch.softmax(outputs_ba.logits, dim=-1).cpu().numpy()[0]

        # 0=contradiction, 1=neutral, 2=entailment (for roberta-mnli)
        contra_ab = float(probs_ab[0])
        entail_a2b = float(probs_ab[2])
        contra_ba = float(probs_ba[0])
        entail_b2a = float(probs_ba[2])

        return contra_ab, entail_a2b, contra_ba, entail_b2a

    def summarize_contradictions(self, contradictions: List[ContradictionResult]) -> str:
        """
        Generate human-readable summary of detected contradictions.
        """
        if not contradictions:
            return "No contradictions detected among sources."

        lines = [f"Found {len(contradictions)} conflicting source pairs:"]
        for idx, c in enumerate(contradictions[:5], 1):  # top 5
            lines.append(
                f"\n{idx}. Conflict between sources {c.source_a_idx} and {c.source_b_idx}:"
                f"\n   Source {c.source_a_idx}: {c.claim_a}"
                f"\n   Source {c.source_b_idx}: {c.claim_b}"
                f"\n   Contradiction score: {c.contradiction_score:.2f}"
            )

        if len(contradictions) > 5:
            lines.append(f"\n...and {len(contradictions) - 5} more conflicts")

        return "\n".join(lines)
