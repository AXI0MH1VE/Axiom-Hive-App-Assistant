"""
Unit tests for vector store.
"""

import pytest
import numpy as np
import tempfile
import os

from src.backend.retrieval.vector_store import VectorStore


@pytest.fixture
def embed_model():
    return "all-MiniLM-L6-v2"


def test_vector_store_initialization(embed_model):
    vs = VectorStore(embedding_model=embed_model)
    assert vs.index.ntotal == 0
    assert len(vs.metadata) == 0


def test_add_and_search(embed_model):
    vs = VectorStore(embedding_model=embed_model)
    texts = [
        "The quick brown fox jumps over the lazy dog.",
        "Artificial intelligence is transforming the world.",
        "Photosynthesis converts sunlight to chemical energy.",
    ]
    ids = vs.add_documents(texts)
    assert len(ids) == 3
    assert vs.index.ntotal == 3

    # Search
    results = vs.search("sunlight energy plants", top_k=2)
    assert len(results) <= 2
    for doc_id, score, meta in results:
        assert score > 0
        assert "text" in meta


def test_save_and_load(embed_model):
    vs = VectorStore(embedding_model=embed_model)
    texts = ["Hello world", "Machine learning models"]
    meta = [{"title": "doc1"}, {"title": "doc2"}]
    vs.add_documents(texts, meta)

    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = os.path.join(tmpdir, "test.index")
        vs.save(index_path)

        vs2 = VectorStore(embedding_model=embed_model)
        vs2.load(index_path)
        assert vs2.index.ntotal == 2
        assert len(vs2.metadata) == 2


def test_similarity_threshold(embed_model):
    vs = VectorStore(embedding_model=embed_model)
    texts = ["Dogs are mammals.", "Cats are mammals.", "Quantum physics is complex."]
    vs.add_documents(texts)

    # Should return only relevant results
    results = vs.search("mammals like dogs", top_k=5, min_score=0.5)
    assert len(results) >= 1
    top_score = results[0][1]
    assert top_score >= 0.5
