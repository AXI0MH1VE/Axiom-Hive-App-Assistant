#!/usr/bin/env python3
"""
Batch ingest documents from knowledge/raw into vector store.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.retrieval.vector_store import VectorStore
from src.backend.retrieval.ingest_service import IngestService

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='knowledge/raw',
                        help='Directory containing documents')
    parser.add_argument('--index-path', default='knowledge/embeddings/corpus.faiss',
                        help='FAISS index output path')
    parser.add_argument('--rebuild', action='store_true',
                        help='Wipe and rebuild from scratch')
    parser.add_argument('--persist', action='store_true',
                        help='Save index after ingestion')
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Directory not found: {data_dir}")
        print("Please download sample corpus first:")
        print("  python scripts/download_sample_corpus.py")
        sys.exit(1)

    # Initialize vector store (load existing if present)
    index_path = Path(args.index_path)
    vector_store = VectorStore(index_path=str(index_path)) if index_path.exists() else VectorStore()

    # Ingest service
    ingest = IngestService(
        vector_store=vector_store,
        raw_corpus_dir=str(data_dir),
        processed_dir='knowledge/processed',
        embeddings_dir='knowledge/embeddings',
    )

    if args.rebuild:
        print("Rebuilding index from scratch...")
        index_file = ingest.build_index_from_directory(corpus_name="corpus", force_rebuild=True)
        print(f"Index built: {index_file}")
    else:
        print("Ingesting new documents incrementally...")
        files, chunks = ingest.ingest_directory(persist=args.persist)
        print(f"Ingested {files} files, {chunks} new chunks")

    stats = ingest.get_stats()
    print(f"Vector store: {stats['vector_store']['total_documents']} documents indexed")

if __name__ == '__main__':
    main()
