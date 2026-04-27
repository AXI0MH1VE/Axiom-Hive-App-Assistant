#!/usr/bin/env python3
"""
Download a small sample Wikipedia corpus for development/demo.
Retrieves 100 random article excerpts from the Wikipedia API.
"""

import json
import time
import requests
from pathlib import Path
from typing import List, Dict

SAMPLE_QUERIES = [
    "photosynthesis", "gravity", "internet", "machine learning",
    "climate change", "photosynthesis", "cells", "evolution",
    "python programming", "electricity", "relativity", "microbiology",
    "world war ii", "democracy", "solar system", "human body",
    "agriculture", "transportation", "renewable energy", "neuroscience"
]

def fetch_wikipedia_excerpt(title: str, lang: str = "en") -> Dict:
    """Fetch extract and metadata from Wikipedia API."""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "title": data.get("title", title),
                "extract": data.get("extract", ""),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "timestamp": data.get("timestamp", ""),
            }
    except Exception as e:
        print(f"Error fetching {title}: {e}")
    return {}

def main():
    output_dir = Path("knowledge/raw")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "wikipedia_sample_100.jsonl"

    articles = []
    print(f"Downloading {len(SAMPLE_QUERIES)} sample Wikipedia articles...")

    for i, query in enumerate(SAMPLE_QUERIES, 1):
        article = fetch_wikipedia_excerpt(query)
        if article:
            articles.append(article)
            print(f"[{i}/{len(SAMPLE_QUERIES)}] Fetched: {article['title']}")
        else:
            print(f"[{i}/{len(SAMPLE_QUERIES)}] Failed: {query}")
        time.sleep(0.5)  # be polite

    # Write JSONL
    with open(output_file, "w", encoding="utf-8") as f:
        for art in articles:
            f.write(json.dumps(art, ensure_ascii=False) + "\n")

    print(f"Saved {len(articles)} articles to {output_file}")
    print("Next: run `python scripts/build_index.py` to create embeddings.")

if __name__ == "__main__":
    main()
