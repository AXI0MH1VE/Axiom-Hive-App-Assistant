"""
FAISS vector store wrapper for semantic search.
Provides add, search, persist, and load operations.
"""

import os
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import uuid

import numpy as np
import faiss

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class VectorStore:
    """
    FAISS-based vector store for document embeddings.
    Supports adding documents, similarity search, and persistence.
    """

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        index_path: Optional[str] = None,
        metadata_path: Optional[str] = None,
        dimension: int = 384,
    ):
        """
        Initialize vector store.

        Args:
            embedding_model: Name/path of sentence-transformers model
            index_path: Path to existing FAISS index file (optional)
            metadata_path: Path to metadata JSONL file (optional)
            dimension: Embedding dimension (must match model)
        """
        self.embedding_model = SentenceTransformer(embedding_model)
        self.dimension = self.embedding_model.get_sentence_embedding_dimension()

        # FAISS index (inner product = cosine similarity after normalization)
        self.index = faiss.IndexFlatIP(self.dimension)

        # Metadata storage: maps internal_id -> document metadata
        self.metadata: Dict[int, Dict[str, Any]] = {}

        # Counter for next document ID
        self._next_id = 0

        if index_path and os.path.exists(index_path):
            self.load(index_path, metadata_path)
        else:
            logger.info(f"Initialized new vector store (dim={self.dimension})")

    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        batch_size: int = 32,
    ) -> List[int]:
        """
        Add documents to the vector store.

        Args:
            texts: List of text content to embed and index
            metadatas: Optional list of metadata dicts (one per text)
            batch_size: Number of texts to embed simultaneously

        Returns:
            List of assigned document IDs
        """
        if not texts:
            return []

        if metadatas and len(metadatas) != len(texts):
            raise ValueError("metadatas length must match texts length")

        logger.info(f"Adding {len(texts)} documents to vector store")

        # Generate embeddings in batches
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = self.embedding_model.encode(
                batch, convert_to_numpy=True, normalize_embeddings=True
            )
            all_embeddings.append(embeddings)

        embeddings_np = np.vstack(all_embeddings).astype("float32")

        # Add to FAISS index
        start_id = self._next_id
        self.index.add(embeddings_np)

        # Store metadata
        ids = list(range(start_id, start_id + len(texts)))
        for idx, doc_id in enumerate(ids):
            metadata = metadatas[idx] if metadatas else {}
            metadata["_internal_id"] = doc_id
            metadata["text"] = texts[idx]
            metadata["embedding_id"] = idx
            self.metadata[doc_id] = metadata

        self._next_id += len(texts)

        logger.info(f"Added {len(texts)} documents; total: {self.index.ntotal}")
        return ids

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        Search for similar documents.

        Args:
            query: Query text to embed and search
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1)
            metadata_filter: Filter results by metadata fields (e.g., {"source": "wikipedia"})

        Returns:
            List of (doc_id, score, metadata) tuples sorted by descending score
        """
        if self.index.ntotal == 0:
            logger.warning("Search on empty index")
            return []

        # Embed query
        query_embedding = self.embedding_model.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True
        ).astype("float32")

        # Search FAISS
        scores, indices = self.index.search(query_embedding, top_k * 2)  # oversample for filtering

        results = []
        seen_ids = set()

        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for padding
                continue
            if score < min_score:
                continue

            doc_id = int(idx)
            if doc_id in seen_ids:
                continue

            metadata = self.metadata.get(doc_id)
            if metadata is None:
                continue

            # Apply metadata filter
            if metadata_filter:
                match = True
                for key, value in metadata_filter.items():
                    if metadata.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            results.append((doc_id, float(score), metadata))
            seen_ids.add(doc_id)

            if len(results) >= top_k:
                break

        return sorted(results, key=lambda x: x[1], reverse=True)

    def get_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve metadata and text for a specific document ID."""
        return self.metadata.get(doc_id)

    def delete(self, doc_ids: List[int]) -> int:
        """
        Remove documents from the index.
        Note: FAISS does not natively support efficient deletion; rebuilds index.
        This is a placeholder for future batch rebuild.
        """
        raise NotImplementedError("Deletion requires index rebuild; use rebuild_excluding()")

    def save(self, index_path: str, metadata_path: Optional[str] = None):
        """
        Persist index and metadata to disk.

        Args:
            index_path: Path to save FAISS index (.index or .faiss)
            metadata_path: Path to save metadata (JSONL). Defaults to index_path + ".meta.jsonl"
        """
        os.makedirs(os.path.dirname(os.path.abspath(index_path)), exist_ok=True)

        # Save FAISS index
        faiss.write_index(self.index, index_path)
        logger.info(f"Saved FAISS index to {index_path} (ntotal={self.index.ntotal})")

        if metadata_path is None:
            metadata_path = index_path + ".meta.jsonl"

        # Save metadata as JSONL
        import json

        with open(metadata_path, "w", encoding="utf-8") as f:
            for doc_id in sorted(self.metadata.keys()):
                f.write(json.dumps(self.metadata[doc_id], ensure_ascii=False) + "\n")
        logger.info(f"Saved metadata to {metadata_path} ({len(self.metadata)} records)")

    def load(self, index_path: str, metadata_path: Optional[str] = None):
        """
        Load index and metadata from disk.

        Args:
            index_path: Path to FAISS index file
            metadata_path: Path to metadata JSONL file (optional; defaults to index_path + ".meta.jsonl")
        """
        # Load FAISS index
        self.index = faiss.read_index(index_path)
        logger.info(f"Loaded FAISS index from {index_path} (ntotal={self.index.ntotal})")

        # Load metadata
        if metadata_path is None:
            metadata_path = index_path + ".meta.jsonl"

        import json

        self.metadata.clear()
        with open(metadata_path, "r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                doc_id = record.get("_internal_id")
                if doc_id is not None:
                    self.metadata[int(doc_id)] = record

        self._next_id = max(self.metadata.keys(), default=-1) + 1
        logger.info(f"Loaded metadata from {metadata_path} ({len(self.metadata)} records)")

    def __len__(self) -> int:
        return self.index.ntotal

    def clear(self):
        """Remove all documents from the store."""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata.clear()
        self._next_id = 0
        logger.info("Cleared vector store")

    def get_stats(self) -> Dict[str, Any]:
        """Return statistics about the vector store."""
        return {
            "total_documents": self.index.ntotal,
            "dimension": self.dimension,
            "embedding_model": self.embedding_model.model_card_data.base_model
            if hasattr(self.embedding_model, "model_card_data")
            else "unknown",
            "index_type": type(self.index).__name__,
        }
