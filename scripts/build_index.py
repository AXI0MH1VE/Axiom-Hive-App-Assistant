#!/usr/bin/env python3
"""
Build FAISS vector index from raw documents in knowledge/ directory.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import List, Dict

from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_jsonl(path: Path) -> List[Dict]:
    records = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            records.append(json.loads(line))
    return records

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks (sentence-aware)."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Try sentence boundary
        if end < len(text):
            boundary = max(text.rfind('. ', start, end),
                          text.rfind('? ', start, end),
                          text.rfind('! ', start, end))
            if boundary != -1:
                end = boundary + 2
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
        if start < 0:
            start = 0
    return chunks

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='knowledge/raw',
                        help='Directory containing JSONL source files')
    parser.add_argument('--output', default='knowledge/embeddings/corpus.faiss',
                        help='Path to write FAISS index')
    parser.add_argument('--model', default='all-MiniLM-L6-v2',
                        help='Sentence-transformers model name')
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load embedding model
    logger.info(f"Loading embedding model: {args.model}")
    model = SentenceTransformer(args.model)
    dim = model.get_sentence_embedding_dimension()

    # Prepare FAISS index
    index = faiss.IndexFlatIP(dim)  # Inner product for cosine similarity after norm
    metadata: List[Dict] = []
    global_id = 0

    # Process all JSONL files
    jsonl_files = list(input_dir.glob('*.jsonl'))
    logger.info(f"Found {len(jsonl_files)} source files")

    for jf in jsonl_files:
        logger.info(f"Processing {jf.name}")
        with open(jf, 'r', encoding='utf-8') as f:
            for line in f:
                record = json.loads(line)
                title = record.get('title', 'Untitled')
                extract = record.get('extract', '')
                url = record.get('url', '')

                if not extract:
                    continue

                chunks = chunk_text(extract)
                for chunk in chunks:
                    # Store metadata
                    meta = {
                        'doc_id': global_id,
                        'title': title,
                        'text': chunk,
                        'url': url,
                        'source_file': jf.name,
                    }
                    metadata.append(meta)
                    global_id += 1

    # Encode all chunks
    logger.info(f"Encoding {len(metadata)} chunks...")
    texts = [m['text'] for m in metadata]
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)
    embeddings = embeddings.astype('float32')

    # Add to index
    index.add(embeddings)
    logger.info(f"Index built: {index.ntotal} vectors")

    # Save index
    faiss.write_index(index, str(output_path))
    logger.info(f"FAISS index saved to {output_path}")

    # Save metadata
    meta_path = output_path.with_suffix('.meta.jsonl')
    with open(meta_path, 'w', encoding='utf-8') as f:
        for m in metadata:
            f.write(json.dumps(m, ensure_ascii=False) + '\n')
    logger.info(f"Metadata saved to {meta_path}")

    # Save manifest entry
    manifest = {
        "corpus_version": "2024.06.1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [{
            "source_id": "wikipedia_sample",
            "file_path": str(output_path),
            "metadata_path": str(meta_path),
            "document_count": len(metadata),
            "embedding_model": args.model,
            "embedding_dim": int(dim),
            "index_type": "Flat",
            "license": "CC-BY-SA-4.0"
        }]
    }
    manifest_path = Path('knowledge/manifest.json')
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info(f"Manifest updated at {manifest_path}")

if __name__ == '__main__':
    main()
