"""
Integration test: end-to-end query → response pipeline.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "backend"))

from core.assistant import VerityAssistant
from retrieval.vector_store import VectorStore
from models.wrapper import LLMWrapper


@pytest.mark.skipif(not Path("knowledge/embeddings/corpus.faiss").exists(),
                    reason="Vector index not built; run scripts/build_index.py")
def test_end_to_end_basic():
    """Test full pipeline with pre-built index."""
    # Load FAISS index
    vs = VectorStore(
        embedding_model="all-MiniLM-L6-v2",
        index_path="knowledge/embeddings/corpus.faiss",
        metadata_path="knowledge/embeddings/corpus.meta.jsonl",
    )

    # Dummy LLM wrapper (use OpenAI or local depending on env)
    llm_config = {
        "default_provider": "openai",
        "openai": {"api_key": None},
        "fallback_enabled": False,
    }
    llm = LLMWrapper(llm_config)

    assistant = VerityAssistant(vs, llm, {
        "thresholds": {"generation": {"max_tokens": 512}},
        "boundaries": {"restricted_claim_types": []},
    })

    # Query (simple factual)
    query = "What is photosynthesis?"
    result = assistant.process_query(query, strict_mode=False, top_k=3)

    assert "answer" in result
    assert "confidence" in result
    assert "sources" in result
    assert len(result["sources"]) >= 1
    print(f"\nQuery: {query}")
    print(f"Answer: {result['answer'][:200]}...")
    print(f"Confidence: {result['confidence']}")
