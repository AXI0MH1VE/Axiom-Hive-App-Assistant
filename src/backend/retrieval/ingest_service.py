"""
Ingest service: batched ingestion, deduplication, and vector store population.
Orchestrates document loading, embedding, and index updates.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import json

from .document_loader import DocumentLoader, DocumentMetadata
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class IngestService:
    """
    Manages corpus ingestion pipeline:
    1. Load documents from configured sources
    2. Deduplicate based on content hash
    3. Generate embeddings
    4. Update vector store
    5. Persist index and metadata
    """

    def __init__(
        self,
        vector_store: VectorStore,
        raw_corpus_dir: str = "knowledge/raw",
        processed_dir: str = "knowledge/processed",
        embeddings_dir: str = "knowledge/embeddings",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """
        Initialize ingest service.

        Args:
            vector_store: Pre-initialized VectorStore instance
            raw_corpus_dir: Directory containing raw documents
            processed_dir: Where to write extracted JSONL chunks
            embeddings_dir: Where to persist FAISS index
            chunk_size: Document chunk size in characters
            chunk_overlap: Overlap between chunks in characters
        """
        self.vector_store = vector_store
        self.raw_corpus_dir = Path(raw_corpus_dir)
        self.processed_dir = Path(processed_dir)
        self.embeddings_dir = Path(embeddings_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.loader = DocumentLoader(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        # Ensure directories exist
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)

        # Track ingested content hashes to prevent duplicates
        self.ingested_hashes: set[str] = set()
        self._load_existing_hashes()

    def _load_existing_hashes(self):
        """Load content hashes from existing vector store metadata."""
        for metadata in self.vector_store.metadata.values():
            content_hash = metadata.get("content_hash")
            if content_hash:
                self.ingested_hashes.add(content_hash)
        logger.info(f"Loaded {len(self.ingested_hashes)} existing content hashes")

    def ingest_file(self, file_path: str, metadata_override: Optional[Dict[str, Any]] = None, persist: bool = False) -> List[int]:
        """
        Ingest a single file into the vector store.

        Args:
            file_path: Path to document file
            metadata_override: Additional metadata fields
            persist: Save index and metadata to disk after ingestion

        Returns:
            List of assigned document IDs
        """
        path = Path(file_path)
        logger.info(f"Ingesting {path.name}")

        # Load and chunk
        chunks, metadatas = self.loader.load_file(file_path, metadata_override)

        # Deduplicate: skip if content already ingested
        new_chunks = []
        new_metadatas = []
        for chunk, meta in zip(chunks, metadatas):
            if meta["content_hash"] not in self.ingested_hashes:
                new_chunks.append(chunk)
                new_metadatas.append(meta)
                self.ingested_hashes.add(meta["content_hash"])

        if not new_chunks:
            logger.info(f"No new content in {path.name}; already ingested or duplicate")
            return []

        # Add to vector store
        doc_ids = self.vector_store.add_documents(new_chunks, new_metadatas)

        # Write processed chunks to disk for audit
        self._write_processed_chunks(path.stem, new_chunks, new_metadatas)

        logger.info(f"Ingested {len(new_chunks)} new chunks from {path.name}")

        if persist:
            index_path = self.embeddings_dir / f"{path.stem}.faiss"
            self.vector_store.save(str(index_path))

        return doc_ids

    def ingest_directory(
        self,
        directory: Optional[str] = None,
        pattern: str = "*",
        recursive: bool = True,
        persist: bool = False,
    ) -> Tuple[int, int]:
        """
        Ingest all supported documents in a directory.

        Args:
            directory: Directory to scan (default: raw_corpus_dir)
            pattern: Glob pattern for file matching
            recursive: Recurse into subdirectories
            persist: Save index after batch completion

        Returns:
            (num_files_processed, total_chunks_added)
        """
        dir_path = Path(directory or self.raw_corpus_dir)
        logger.info(f"Ingesting directory: {dir_path}")

        files_processed = 0
        total_chunks = 0

        for ext in DocumentLoader.SUPPORTED_EXTENSIONS:
            glob_pattern = f"**/*{ext}" if recursive else f"*{ext}"
            for file_path in dir_path.glob(glob_pattern):
                try:
                    doc_ids = self.ingest_file(str(file_path), persist=False)
                    files_processed += 1
                    total_chunks += len(doc_ids)
                except Exception as e:
                    logger.error(f"Ingest failed for {file_path}: {e}")

        if persist and total_chunks > 0:
            index_path = self.embeddings_dir / "corpus.faiss"
            self.vector_store.save(str(index_path))
            logger.info(f"Persisted index to {index_path}")

        logger.info(f"Directory ingest complete: {files_processed} files, {total_chunks} new chunks")
        return files_processed, total_chunks

    def _write_processed_chunks(
        self,
        source_name: str,
        chunks: List[str],
        metadatas: List[Dict[str, Any]],
    ):
        """Write extracted chunks to processed directory as JSONL."""
        output_path = self.processed_dir / f"{source_name}.jsonl"
        with open(output_path, "a", encoding="utf-8") as f:
            for chunk, meta in zip(chunks, metadatas):
                record = {
                    "chunk_id": meta["_internal_id"],
                    "source": source_name,
                    "text": chunk,
                    "metadata": meta,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def build_index_from_directory(
        self,
        corpus_name: str = "corpus",
        force_rebuild: bool = False,
    ) -> str:
        """
        Build vector store from scratch from raw corpus directory.

        Args:
            corpus_name: Name for output index files
            force_rebuild: Clear existing index before rebuilding

        Returns:
            Path to saved FAISS index
        """
        if force_rebuild:
            logger.info("Force rebuilding index; clearing existing data")
            self.vector_store.clear()
            self.ingested_hashes.clear()

        # Ingest all files
        _, total_chunks = self.ingest_directory(persist=False)

        if total_chunks == 0:
            logger.warning("No documents ingested; index is empty")
            return ""

        # Save index
        index_path = self.embeddings_dir / f"{corpus_name}.faiss"
        metadata_path = self.embeddings_dir / f"{corpus_name}.meta.jsonl"
        self.vector_store.save(str(index_path), str(metadata_path))

        logger.info(f"Index built: {total_chunks} chunks in {index_path}")
        return str(index_path)

    def get_stats(self) -> Dict[str, Any]:
        """Return ingestion statistics."""
        return {
            "vector_store": self.vector_store.get_stats(),
            "raw_corpus_dir": str(self.raw_corpus_dir),
            "processed_dir": str(self.processed_dir),
            "embeddings_dir": str(self.embeddings_dir),
            "unique_documents_ingested": len(self.ingested_hashes),
        }
