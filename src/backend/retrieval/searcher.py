"""
Hybrid search combining vector similarity and BM25 keyword ranking.
Performs metadata-aware filtering and score fusion.
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
import numpy as np

from rank_bm25 import BM25Okapi
import jieba
import jieba.analyse  # for Chinese keyword extraction
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)


class HybridSearcher:
    """
    Combines vector similarity search with BM25 keyword search.
    Supports metadata filtering and configurable result fusion.
    """

    def __init__(
        self,
        vector_store,
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
        enable_chinese: bool = True,
        min_bm25_score: float = 0.1,
    ):
        """
        Initialize hybrid searcher.

        Args:
            vector_store: VectorStore instance for semantic search
            bm25_weight: Weight for BM25 scores (0-1)
            vector_weight: Weight for vector similarity scores (0-1)
            enable_chinese: Enable Chinese tokenization via jieba
            min_bm25_score: Minimum BM25 score for a document to be included
        """
        self.vector_store = vector_store
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight

        if enable_chinese:
            jieba.initialize()
            self.tokenize = lambda text: list(jieba.cut(text, cut_all=False))
        else:
            import re

            self.tokenize = lambda text: re.findall(r"\w+", text.lower())

        self.bm25_model: Optional[BM25Okapi] = None
        self.documents: List[str] = []
        self.doc_ids: List[int] = []
        self.min_bm25_score = min_bm25_score

    def index_documents(self, force_rebuild: bool = False):
        """
        Build BM25 index from all documents in vector store.
        Call this after adding new documents to the vector store.

        Args:
            force_rebuild: Rebuild even if already indexed
        """
        if self.bm25_model is not None and not force_rebuild:
            logger.debug("BM25 index already built; use force_rebuild=True to rebuild")
            return

        logger.info("Building BM25 index from vector store...")

        # Extract all texts from vector store metadata
        all_records = []
        for doc_id, metadata in self.vector_store.metadata.items():
            text = metadata.get("text", "")
            if text:
                all_records.append((doc_id, text))

        if not all_records:
            logger.warning("No documents found in vector store for BM25 indexing")
            return

        self.doc_ids, self.documents = zip(*all_records)

        # Tokenize corpus
        tokenized_corpus = [self.tokenize(doc) for doc in self.documents]
        self.bm25_model = BM25Okapi(tokenized_corpus)
        logger.info(f"BM25 index built with {len(self.documents)} documents")

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        metadata_filter: Optional[Dict[str, Any]] = None,
        vector_top_k: int = 20,
    ) -> List[Tuple[int, float, Dict[str, Any], Dict[str, float]]]:
        """
        Perform hybrid search.

        Args:
            query: Query text
            top_k: Number of final results to return
            min_score: Minimum fused score threshold
            metadata_filter: Filter by metadata fields
            vector_top_k: Number of candidates to retrieve from vector search (larger than top_k)

        Returns:
            List of (doc_id, fused_score, metadata, component_scores) tuples
        """
        if self.vector_store.index.ntotal == 0:
            logger.warning("Empty vector store; no search results")
            return []

        # Phase 1: Vector similarity search (broader candidate set)
        vector_results = self.vector_store.search(
            query=query,
            top_k=min(vector_top_k, self.vector_store.index.ntotal),
            min_score=0.0,  # We'll apply min_score after fusion
            metadata_filter=metadata_filter,
        )

        if not vector_results:
            logger.info("Vector search returned no results")
            return []

        # Phase 2: BM25 scoring on vector candidates
        query_tokens = self.tokenize(query)
        candidate_ids = [r[0] for r in vector_results]
        candidate_texts = [self.vector_store.get_document(doc_id)["text"] for doc_id in candidate_ids]

        if self.bm25_model is None:
            # If BM25 not built, skip and just return vector results
            logger.debug("BM25 model not available; using vector-only results")
            return [
                (doc_id, score, self.vector_store.get_document(doc_id), {"vector": score, "bm25": 0.0})
                for doc_id, score, _ in vector_results[:top_k]
            ]

        # Tokenize candidate documents for BM25
        candidate_tokens = [self.tokenize(text) for text in candidate_texts]
        bm25_scores = self.bm25_model.get_scores(query_tokens)

        # Normalize BM25 scores to [0, 1]
        max_bm25 = bm25_scores.max() if bm25_scores.size > 0 else 1.0
        if max_bm25 > 0:
            bm25_scores = bm25_scores / max_bm25

        # Map BM25 scores back to document IDs
        doc_id_to_bm25 = {}
        for tokens_score, doc_id in zip(bm25_scores, self.doc_ids):
            if doc_id in candidate_ids:
                doc_id_to_bm25[doc_id] = float(tokens_score)

        # Phase 3: Score fusion
        fused_results = []
        for doc_id, vector_score, metadata in vector_results:
            bm25_score = doc_id_to_bm25.get(doc_id, 0.0)

            # Weighted sum
            fused_score = (self.vector_weight * vector_score) + (self.bm25_weight * bm25_score)

            if fused_score >= min_score:
                component_scores = {"vector": vector_score, "bm25": bm25_score, "fused": fused_score}
                fused_results.append((doc_id, fused_score, metadata, component_scores))

        # Sort by fused score descending
        fused_results.sort(key=lambda x: x[1], reverse=True)

        logger.info(
            f"Hybrid search: {len(vector_results)} vector candidates → {len(fused_results)} fused results"
        )
        return fused_results[:top_k]

    def keyword_search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        Standalone BM25 keyword search.

        Returns:
            List of (doc_id, bm25_score, metadata) tuples
        """
        if self.bm25_model is None:
            raise RuntimeError("BM25 model not built; call index_documents() first")

        query_tokens = self.tokenize(query)
        scores = self.bm25_model.get_scores(query_tokens)

        # Normalize
        max_score = scores.max()
        if max_score > 0:
            scores = scores / max_score

        # Create (doc_id, score) pairs and filter
        results = []
        for idx, score in enumerate(scores):
            if score < self.min_bm25_score:
                continue
            doc_id = self.doc_ids[idx]
            metadata = self.vector_store.get_document(doc_id)

            if metadata_filter:
                match = all(metadata.get(k) == v for k, v in metadata_filter.items())
                if not match:
                    continue

            results.append((doc_id, float(score), metadata))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
