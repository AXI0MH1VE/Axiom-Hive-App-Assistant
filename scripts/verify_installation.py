#!/usr/bin/env python3
"""
Verity Assistant — Installation verification & smoke test.
Run after deployment to confirm system health.
"""

import sys
import time
import subprocess
from pathlib import Path
import urllib.request
import json

BASE_URL = "http://localhost:8000"
HEALTH_ENDPOINT = f"{BASE_URL}/health"
READY_ENDPOINT = f"{BASE_URL}/ready"
CHAT_ENDPOINT = f"{BASE_URL}/api/v1/chat"

def check_docker_services():
    """Verify Docker containers are running."""
    print("🔍 Checking Docker services...")
    result = subprocess.run(["docker", "ps", "--filter", "name=verity", "--format", "{{.Names}} {{.Status}}"],
                            capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')
    for line in lines:
        if line:
            name, status = line.split(maxsplit=1)
            print(f"   {name}: {status}")

def check_endpoint(url: str, name: str) -> bool:
    """HTTP GET health check."""
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            if resp.status == 200:
                print(f"✅ {name}: OK")
                return True
    except Exception as e:
        print(f"❌ {name}: {e}")
        return False
    return False

def smoke_test_chat():
    """Send a simple factual query and validate response schema."""
    print("🧪 Running smoke test: sample query...")

    payload = json.dumps({
        "query": "What is the capital of France?",
        "strict": False,
        "top_k": 3
    }).encode()

    req = urllib.request.Request(CHAT_ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            # Validate schema
            required = {"id", "answer", "confidence", "sources", "gaps", "timestamp"}
            if required.issubset(data.keys()):
                print(f"✅ Chat response received — confidence: {data['confidence']}, sources: {len(data['sources'])}")
                print(f"   Answer excerpt: {data['answer'][:120]}...")
                return True
            else:
                print(f"❌ Response missing required fields: {data.keys()}")
                return False
    except Exception as e:
        print(f"❌ Chat failed: {e}")
        return False

def check_corpus():
    """Verify corpus files exist."""
    emb = Path("knowledge/embeddings/corpus.faiss")
    meta = Path("knowledge/embeddings/corpus.meta.jsonl")
    manifest = Path("knowledge/manifest.json")

    if emb.exists() and meta.exists() and manifest.exists():
        print(f"✅ Knowledge corpus present ({emb.stat().st_size // (1024*1024)}MB index)")
        return True
    else:
        print("⚠️  Knowledge corpus missing. Run: python scripts/build_index.py")
        return False

def main():
    print("=" * 60)
    print("Verity Assistant — System Verification")
    print("=" * 60)

    # 1. Docker
    check_docker_services()
    print()

    # 2. Health endpoints
    check_endpoint(HEALTH_ENDPOINT, "Liveness probe")
    check_endpoint(READY_ENDPOINT, "Readiness probe")
    print()

    # 3. Corpus
    corpus_ok = check_corpus()
    print()

    # 4. Smoke test (only if corpus present)
    if corpus_ok:
        chat_ok = smoke_test_chat()
    else:
        print("⏭️  Skipping chat test — no corpus")
        chat_ok = False

    print()
    print("=" * 60)
    if chat_ok:
        print("✅ System is ready.")
        sys.exit(0)
    else:
        print("⚠️  System not fully ready — review messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
