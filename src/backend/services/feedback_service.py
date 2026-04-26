"""
Feedback Service: Captures user-reported issues, flags, and review queue.
Integrates with audit logs for traceability.
"""

import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Feedback:
    """User-submitted feedback report."""
    feedback_id: str
    response_id: str
    user_id: Optional[str]
    query: str
    response: str
    flag_type: str  # "inaccurate", "missing_citation", "poor_attribution", "other"
    description: str
    submitted_at: str
    status: str = "pending"  # "pending", "reviewed", "resolved", "dismissed"
    resolution: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None


class FeedbackService:
    """
    Stores and manages user feedback queue.
    Provides API for submission, review, and resolution.
    """

    def __init__(
        self,
        storage_path: str = "data/feedback_queue.json",
    ):
        """
        Args:
            storage_path: Path to JSON feedback file
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing feedback
        self.feedback: Dict[str, Feedback] = {}
        self._load()

        logger.info(f"FeedbackService initialized at {storage_path}")

    def _load(self):
        """Load feedback from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for fb_dict in raw:
                    fb = Feedback(**fb_dict)
                    self.feedback[fb.feedback_id] = fb
            except Exception as e:
                logger.error(f"Failed to load feedback: {e}")

    def _save(self):
        """Persist feedback to disk."""
        raw = [asdict(fb) for fb in self.feedback.values()]
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")

    def submit(
        self,
        response_id: str,
        query: str,
        response: str,
        flag_type: str,
        description: str,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Submit a feedback report.

        Returns:
            feedback_id
        """
        feedback_id = str(uuid.uuid4())

        fb = Feedback(
            feedback_id=feedback_id,
            response_id=response_id,
            user_id=user_id,
            query=query,
            response=response,
            flag_type=flag_type,
            description=description,
            submitted_at=datetime.utcnow().isoformat() + "Z",
        )
        self.feedback[feedback_id] = fb
        self._save()

        logger.info(f"Feedback submitted: {flag_type} — {description[:50]}")
        return feedback_id

    def get_pending(self) -> List[Feedback]:
        """Retrieve all pending feedback for admin review."""
        return [fb for fb in self.feedback.values() if fb.status == "pending"]

    def get_all(self, limit: int = 100) -> List[Feedback]:
        """Retrieve all feedback (most recent first)."""
        sorted_fb = sorted(self.feedback.values(), key=lambda f: f.submitted_at, reverse=True)
        return sorted_fb[:limit]

    def review(
        self,
        feedback_id: str,
        status: str,
        resolution: Optional[str] = None,
        reviewed_by: Optional[str] = None,
    ) -> bool:
        """
        Admin: Update feedback status.

        Args:
            feedback_id: ID to update
            status: One of "resolved", "dismissed", "reviewed"
            resolution: Explanation of outcome
            reviewed_by: Admin user ID
        """
        fb = self.feedback.get(feedback_id)
        if not fb:
            return False

        fb.status = status
        fb.resolution = resolution
        fb.reviewed_by = reviewed_by
        fb.reviewed_at = datetime.utcnow().isoformat() + "Z"

        self._save()
        logger.info(f"Feedback {feedback_id} marked {status} by {reviewed_by}")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Return feedback statistics."""
        total = len(self.feedback)
        by_status: Dict[str, int] = {}
        by_flag: Dict[str, int] = {}

        for fb in self.feedback.values():
            by_status[fb.status] = by_status.get(fb.status, 0) + 1
            by_flag[fb.flag_type] = by_flag.get(fb.flag_type, 0) + 1

        return {
            "total": total,
            "by_status": by_status,
            "by_flag_type": by_flag,
            "pending": len([f for f in self.feedback.values() if f.status == "pending"]),
        }
