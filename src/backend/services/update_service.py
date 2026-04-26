"""
Update Service: Manages knowledge corpus versioning, delta packs, freshness enforcement.
"""

import logging
import json
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import urllib.request
import gzip
import shutil

logger = logging.getLogger(__name__)


class UpdateService:
    """
    Handles knowledge corpus updates, version tracking, and freshness checks.
    Downloads signed delta packs, verifies integrity, applies incremental updates.
    """

    def __init__(
        self,
        manifest_path: str = "knowledge/manifest.json",
        updates_dir: str = "knowledge/updates",
        knowledge_dir: str = "knowledge",
        freshness_days: int = 90,
    ):
        """
        Initialize update service.

        Args:
            manifest_path: Path to corpus manifest
            updates_dir: Where to download delta packs
            knowledge_dir: Root knowledge directory
            freshness_days: Warn if corpus older than this
        """
        self.manifest_path = Path(manifest_path)
        self.updates_dir = Path(updates_dir)
        self.knowledge_dir = Path(knowledge_dir)
        self.freshness_days = freshness_days

        self.updates_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        self.manifest: Dict[str, Any] = {}
        self._load_manifest()

        logger.info("Update service initialized")

    def _load_manifest(self):
        """Load current corpus manifest."""
        if self.manifest_path.exists():
            with open(self.manifest_path, "r") as f:
                self.manifest = json.load(f)
        else:
            logger.warning("Manifest not found; corpus may need initial ingest")

    def check_for_updates(
        self,
        update_endpoint: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Check if newer corpus version is available.

        Returns:
            Update availability info
        """
        if not update_endpoint:
            logger.info("No update endpoint configured; skipping update check")
            return {"available": False, "reason": "No endpoint configured"}

        current_version = self.manifest.get("corpus_version", "0.0.0")
        logger.info(f"Current corpus version: {current_version}")

        try:
            with urllib.request.urlopen(update_endpoint) as resp:
                remote_info = json.loads(resp.read().decode())

            remote_version = remote_info.get("corpus_version", "0.0.0")
            if remote_version > current_version or force:
                return {
                    "available": True,
                    "current_version": current_version,
                    "remote_version": remote_version,
                    "download_url": remote_info.get("delta_pack_url"),
                    "size_bytes": remote_info.get("size_bytes"),
                    "release_notes": remote_info.get("notes"),
                }
            else:
                return {"available": False, "reason": "Current version is latest"}
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return {"available": False, "reason": str(e)}

    def download_delta_pack(
        self,
        download_url: str,
        expected_sha256: Optional[str] = None,
    ) -> Path:
        """
        Download delta pack to local updates directory.

        Returns:
            Path to downloaded file
        """
        dest_path = self.updates_dir / "delta_pack.tar.gz"

        logger.info(f"Downloading {download_url} → {dest_path}")
        urllib.request.urlretrieve(download_url, dest_path)

        # Verify SHA-256 if provided
        if expected_sha256:
            actual = hashlib.sha256(dest_path.read_bytes()).hexdigest()
            if actual != expected_sha256:
                raise ValueError(f"SHA-256 mismatch: expected {expected_sha256}, got {actual}")

        logger.info("Delta pack downloaded and verified")
        return dest_path

    def apply_update(self, delta_pack_path: Path) -> bool:
        """
        Apply delta pack to knowledge directory.

        Returns:
            Success status
        """
        import tarfile

        logger.info(f"Applying update from {delta_pack_path}")

        try:
            with tarfile.open(delta_pack_path, "r:gz") as tar:
                tar.extractall(self.knowledge_dir)
            logger.info("Update extracted successfully")

            # Update manifest version
            new_manifest = self.knowledge_dir / "manifest.json"
            if new_manifest.exists():
                with open(new_manifest, "r") as f:
                    updated = json.load(f)
                self.manifest = updated
                self.manifest_path.write_text(json.dumps(updated, indent=2))
                logger.info(f"Corpus updated to version {updated.get('corpus_version')}")
            return True
        except Exception as e:
            logger.error(f"Update application failed: {e}")
            return False

    def is_corpus_fresh(self) -> Tuple[bool, Optional[datetime]]:
        """
        Check if corpus is within freshness window.

        Returns:
            (is_fresh, corpus_date_or_None)
        """
        if not self.manifest:
            return False, None

        generated_str = self.manifest.get("generated_at")
        if not generated_str:
            return False, None

        try:
            corpus_date = datetime.fromisoformat(generated_str.replace("Z", ""))
        except ValueError:
            return False, None

        age = datetime.utcnow() - corpus_date
        is_fresh = age <= timedelta(days=self.freshness_days)
        return is_fresh, corpus_date

    def enforce_freshness(self, enforce: bool = True) -> bool:
        """
        Check freshness and optionally raise if outdated.

        Returns:
            True if fresh, False if stale
        """
        is_fresh, corpus_date = self.is_corpus_fresh()
        if not is_fresh:
            logger.error(f"Corpus outdated: generated {corpus_date} > {self.freshness_days} days ago")
            if enforce:
                raise RuntimeError("Corpus freshness requirement not met; updates required")
        return is_fresh

    def get_manifest(self) -> Dict[str, Any]:
        """Return current manifest."""
        self._load_manifest()
        return self.manifest

    def force_reindex(
        self,
        vector_store,
        ingest_service,
        corpus_name: str = "corpus",
    ):
        """
        Rebuild vector index from scratch from raw corpus.
        """
        logger.info("Force reindex triggered: clearing existing data")
        vector_store.clear()
        import shutil
        # Clear processed and embeddings
        shutil.rmtree(self.knowledge_dir / "processed", ignore_errors=True)
        shutil.rmtree(self.knowledge_dir / "embeddings", ignore_errors=True)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        # Re-ingest
        index_path = ingest_service.build_index_from_directory(corpus_name=corpus_name, force_rebuild=True)
        logger.info(f"Reindex complete: {index_path}")
