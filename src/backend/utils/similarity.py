"""
Similarity Detection: Copyright and plagiarism checks using BLEU and embedding similarity.
Implements dual-layer filtering per configuration.
"""

import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

import numpy as np
from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)


@dataclass
class SimilarityResult:
    """Result of similarity check."""
    score_bleu: float
    score_cosine: float
    source_text: str
    generated_text: str
    threshold_exceeded: bool
    violation_type: Optional[str] = None  # "copyright" or "plagiarism"


class SimilarityChecker:
    """
    Detects textual similarity between generated output and reference corpus.
    Used for copyright compliance and plagiarism prevention.
    """

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        bleu_threshold: float = 0.3,
        cosine_threshold: float = 0.6,
        check_window_chars: int = 50,
    ):
        """
        Initialize similarity checker.

        Args:
            embedding_model: Sentence-transformer model for semantic similarity
            bleu_threshold: BLEU-4 score threshold for block
            cosine_threshold: Cosine similarity threshold for block
            check_window_chars: Sentence-level window size for sliding check
        """
        self.embedding_model = SentenceTransformer(embedding_model)
        self.bleu_threshold = bleu_threshold
        self.cosine_threshold = cosine_threshold
        self.window_size = check_window_chars

        self.copyrighted_corpus: List[str] = []
        self.corpus_embeddings = None

        logger.info("Similarity checker initialized with dual-threshold approach")

    def load_corpus(self, corpus_texts: List[str]):
        """
        Load reference corpus of copyrighted or proprietary texts.

        Args:
            corpus_texts: List of reference documents to check against
        """
        self.copyrighted_corpus = corpus_texts
        if corpus_texts:
            self.corpus_embeddings = self.embedding_model.encode(
                corpus_texts, convert_to_tensor=True, normalize_embeddings=True
            )
            logger.info(f"Loaded {len(corpus_texts)} copyrighted works into similarity checker")

    def check_against_corpus(
        self,
        generated_text: str,
        return_details: bool = False,
    ) -> Tuple[bool, List[SimilarityResult]]:
        """
        Check generated text for similarity to copyrighted works.

        Args:
            generated_text: Candidate response to evaluate
            return_details: Include detailed per-sentence results

        Returns:
            (block_required, detail_list)
        """
        if not self.copyrighted_corpus:
            logger.debug("No copyrighted corpus loaded; skipping similarity check")
            return False, []

        # Sliding window: break generated text into overlapping chunks
        windows = self._sliding_windows(generated_text, self.window_size)

        block_signal = False
        details = []

        for window in windows:
            # BLEU score against each reference
            max_bleu = self._max_bleu(window, self.copyrighted_corpus)

            # Cosine similarity via embeddings
            window_emb = self.embedding_model.encode([window], convert_to_tensor=True, normalize_embeddings=True)
            cosine_scores = util.cos_sim(window_emb, self.corpus_embeddings)[0].cpu().numpy()
            max_cosine = float(np.max(cosine_scores))

            # Determine if this window triggers a block
            exceeds_bleu = max_bleu >= self.bleu_threshold
            exceeds_cosine = max_cosine >= self.cosine_threshold
            exceeded = exceeds_bleu or exceeds_cosine

            if exceeded:
                block_signal = True
                # Identify which reference documents triggered the block (top-1)
                best_ref_idx = int(np.argmax(cosine_scores))
                source_text = self.copyrighted_corpus[best_ref_idx]
                logger.warning(
                    f"Similarity violation: bleu={max_bleu:.3f}, cosine={max_cosine:.3f} "
                    f"against reference[{best_ref_idx}]"
                )
            else:
                source_text = ""

            details.append(
                SimilarityResult(
                    score_bleu=max_bleu,
                    score_cosine=max_cosine,
                    source_text=source_text[:100],
                    generated_text=window[:100],
                    threshold_exceeded=exceeded,
                    violation_type="copyright" if exceeded else None,
                )
            )

        if block_signal and return_details:
            logger.info(f"Copyright check blocked: {len([d for d in details if d.threshold_exceeded])} windows exceeded thresholds")

        return block_signal, details

    def _sliding_windows(self, text: str, window_size: int, stride: int = 25) -> List[str]:
        """
        Break text into overlapping windows for fine-grained checking.

        Args:
            text: Full text
            window_size: Characters per window
            stride: Step between windows

        Returns:
            List of text windows
        """
        if len(text) <= window_size:
            return [text]

        windows = []
        start = 0
        while start < len(text):
            end = min(start + window_size, len(text))
            # Try to break at sentence boundary
            if end < len(text):
                for boundary in {". ", "! ", "? ", "\n"}:
                    idx = text.rfind(boundary, start, end)
                    if idx != -1:
                        end = idx + 2
                        break
            windows.append(text[start:end].strip())
            start += stride
            if start >= len(text):
                break
        return windows

    def _max_bleu(self, hypothesis: str, references: List[str]) -> float:
        """
        Compute BLEU-4 score against best-matching reference.
        Exact implementation may use sacreBLEU; here we approximate.
        """
        try:
            from sacrebleu import corpus_bleu
            # Use sacreBLEU for robust, language-agnostic BLEU
            bleu = corpus_bleu([hypothesis], [references]).score / 100.0
            return float(bleu)
        except ImportError:
            # Fallback: rough n-gram overlap
            return self._approximate_bleu(hypothesis, references)

    def _approximate_bleu(self, hypothesis: str, references: List[str]) -> float:
        """
        lightweight BLEU approximation (1-4 gram precision with brevity penalty).
        For production, install sacrebleu.
        """
        import math
        from collections import Counter

        def ngrams(tokens, n):
            return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]

        hyp_tokens = hypothesis.lower().split()
        if len(hyp_tokens) < 4:
            return 0.0

        ref_ngrams = [Counter(ngrams(ref.lower().split(), 4)) for ref in references]

        ref_length = min(len(ref.split()) for ref in references)
        brevity_penalty = math.exp(1 - ref_length / len(hyp_tokens)) if len(hyp_tokens) < ref_length else 1.0

        hyp_4grams = ngrams(hyp_tokens, 4)
        hyp_counter = Counter(hyp_4grams)

        # Count matches across all references
        matches = 0
        for gram, count in hyp_counter.items():
            max_ref_count = max(ref[gram] for ref in ref_ngrams)
            matches += min(count, max_ref_count)

        precision = matches / len(hyp_4grams) if hyp_4grams else 0.0
        return precision * brevity_penalty

    def check_uniqueness(self, generated_text: str, source_excerpts: List[str]) -> float:
        """
        Compute uniqueness score: 1 - max_similarity_to_any_source.
        Used to detect over-reliance on single source.

        Args:
            generated_text: Output to evaluate
            source_excerpts: Retrieved sources used for generation

        Returns:
            Uniqueness score (0-1, higher = more unique)
        """
        if not source_excerpts:
            return 1.0

        gen_emb = self.embedding_model.encode([generated_text], convert_to_tensor=True, normalize_embeddings=True)
        src_embs = self.embedding_model.encode(source_excerpts, convert_to_tensor=True, normalize_embeddings=True)
        sims = util.cos_sim(gen_emb, src_embs)[0].cpu().numpy()
        max_sim = float(np.max(sims))
        uniqueness = 1.0 - max_sim
        return max(0.0, uniqueness)
