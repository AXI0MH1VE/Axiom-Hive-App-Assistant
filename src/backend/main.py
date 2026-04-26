"""
FastAPI application entry point.
Provides REST endpoints for chat, documents, admin, and health checks.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Header, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from .core.assistant import VerityAssistant
from .core.auditor import AuditLogger
from .services.knowledge_service import KnowledgeService
from .services.auth_service import AuthService, RateLimiter
from .services.feedback_service import FeedbackService
from .services.update_service import UpdateService
from .utils.cache import Cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Pydantic request/response schemas ─────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096, description="User question")
    strict: bool = Field(default=False, description="Enforce high-confidence-only mode")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of sources to retrieve")
    model: Optional[str] = Field(default=None, description="LLM model override")
    stream: bool = Field(default=False, description="Stream response tokens")


class ChatResponse(BaseModel):
    id: str
    answer: str
    confidence: str
    sources: List[Dict[str, Any]]
    gaps: List[str]
    warnings: List[str]
    model_version: str
    timestamp: str
    processing_time_ms: int
    query_hash: str
    metadata: Dict[str, Any]


class IngestRequest(BaseModel):
    file_path: str = Field(..., description="Absolute path to document file")
    metadata_override: Optional[Dict[str, Any]] = None


class IngestResponse(BaseModel):
    success: bool
    document_ids: List[int]
    message: str


class FeedbackRequest(BaseModel):
    response_id: str
    flag_type: str  # "inaccurate" | "missing_citation" | "poor_attribution" | "other"
    description: str


class AuditQuery(BaseModel):
    event_type: Optional[str] = None
    user_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)


class StatsResponse(BaseModel):
    vector_store: Dict[str, Any]
    cache: Dict[str, Any]
    audit_log: Dict[str, Any]
    feedback: Dict[str, Any]


# ── Application state ─────────────────────────────────────────────────────────

app_state: Dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan: startup and shutdown hooks.
    Initializes assistant, services, and loads configuration.
    """
    logger.info("Starting Verity Assistant backend...")
    try:
        # Load configuration
        import json
        with open("config/thresholds.json", "r") as f:
            thresholds = json.load(f)
        with open("config/boundaries.json", "r") as f:
            boundaries = json.load(f)
        with open("config/llm_config.json", "r") as f:
            llm_config = json.load(f)

        # Initialize cache
        redis_url = None  # from config
        cache = Cache(redis_url=redis_url)

        # Initialize core components
        vector_store = VectorStore(
            embedding_model="all-MiniLM-L6-v2",
            index_path="knowledge/embeddings/corpus.faiss",
        )
        llm_wrapper = LLMWrapper(llm_config)
        assistant = VerityAssistant(vector_store, llm_wrapper, {
            "thresholds": thresholds,
            "boundaries": boundaries,
            "llm": llm_config,
            "audit_db_path": "data/audit/audit.db",
            "knowledge_dir": "knowledge",
        }, cache=cache)
        knowledge_service = KnowledgeService(assistant, cache)

        # Initialize auxiliary services
        rate_limiter = RateLimiter(
            enabled=True,
            requests_per_minute=100,
            burst_limit=10,
        )
        auth_service = AuthService(
            api_key_required=False,  # Set True in production
            rate_limiter=rate_limiter,
        )
        feedback_service = FeedbackService("data/feedback_queue.json")
        update_service = UpdateService()

        # Store in app state
        app_state.update({
            "assistant": assistant,
            "knowledge_service": knowledge_service,
            "auth_service": auth_service,
            "feedback_service": feedback_service,
            "update_service": update_service,
            "cache": cache,
            "start_time": time.time(),
        })

        logger.info("All services initialized successfully")
        yield

    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise

    finally:
        logger.info("Shutting down...")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Verity Assistant API",
    description="Factual AI assistant with zero-tolerance misappropriation guardrails",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Dependency injection ───────────────────────────────────────────────────────

def get_auth_service() -> AuthService:
    return app_state["auth_service"]


def get_knowledge_service() -> KnowledgeService:
    return app_state["knowledge_service"]


def get_feedback_service() -> FeedbackService:
    return app_state["feedback_service"]


# ── Health & readiness endpoints ───────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.get("/ready")
async def readiness_check():
    """Readiness probe—checks if dependencies are up."""
    try:
        vs = app_state["assistant"].vector_store
        # Quick ping: check index exists and accessible
        n = len(vs)
        return {"status": "ready", "vector_store_documents": n}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Dependency unavailable: {e}")


@app.get("/metrics")
async def metrics():
    """Prometheus-style metrics placeholder."""
    uptime = time.time() - app_state.get("start_time", time.time())
    return {
        "uptime_seconds": round(uptime, 2),
        "requests_total": 0,  # Hook with prometheus-fastapi-instrumentator
    }


# ── Chat endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    auth: AuthService = Depends(get_auth_service),
    ks: KnowledgeService = Depends(get_knowledge_service),
):
    """
    Main chat endpoint: process a query and return structured factual response.

    Request headers:
        X-API-Key: <key> (if auth enabled)
        X-Forwarded-For: <client_ip> (for rate limiting)
    """
    # Extract auth headers
    api_key = request.headers.get("X-API-Key")
    client_ip = request.headers.get("X-Forwarded-For", "localhost")

    authorized, reason = auth_service.validate_request(api_key, client_ip)
    if not authorized:
        raise HTTPException(status_code=429, detail=reason)

    try:
        result = ks.query(
            question=request.query,
            strict=request.strict,
            top_k=request.top_k,
            model=request.model,
        )
        return ChatResponse(**result)
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal processing error")


@app.post("/api/v1/chat/stream")
async def chat_stream(
    request: ChatRequest,
    auth: AuthService = Depends(get_auth_service),
):
    """
    Streaming chat endpoint (Server-Sent Events).
    Note: Full streaming implementation pending; currently returns assembled response.
    """
    if request.stream:
        # TODO: Implement true streaming with SSE
        pass
    # Fallback to regular endpoint
    return await chat(request, auth, app_state["knowledge_service"])


# ── Knowledge management endpoints ────────────────────────────────────────────

@app.post("/api/v1/ingest", response_model=IngestResponse)
async def ingest_document(
    ingest: IngestRequest,
    background_tasks: BackgroundTasks,
    ks: KnowledgeService = Depends(get_knowledge_service),
):
    """
    Ingest a new document into the knowledge base.
    Requires file to be accessible on server filesystem.
    """
    try:
        doc_ids = ks.assistant.add_document(ingest.file_path)
        if doc_ids:
            # Background task: rebuild index asynchronously
            background_tasks.add_task(ks.assistant.vector_store.save, "knowledge/embeddings/corpus.faiss")
            return IngestResponse(
                success=True,
                document_ids=doc_ids,
                message=f"Ingested {len(doc_ids)} chunks",
            )
        else:
            return IngestResponse(
                success=False,
                document_ids=[],
                message="No new content added (duplicate or error)",
            )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found on server")
    except Exception as e:
        logger.error(f"Ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/search")
async def search(
    q: str,
    top_k: int = 5,
    ks: KnowledgeService = Depends(get_knowledge_service),
):
    """
    Search-only endpoint: retrieve relevant source excerpts without LLM generation.
    """
    results = ks.search_only(q, top_k=top_k)
    return {"query": q, "results": results, "count": len(results)}


# ── Feedback endpoints ─────────────────────────────────────────────────────────

@app.post("/api/v1/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    feedback: FeedbackService = Depends(get_feedback_service),
    auth: AuthService = Depends(get_auth_service),
):
    """Submit user feedback about a response."""
    feedback_id = feedback.submit(
        response_id=request.response_id,
        query="",  # Not stored in feedback; could lookup from audit
        response="",
        flag_type=request.flag_type,
        description=request.description,
        user_id=None,
    )
    return {"feedback_id": feedback_id, "status": "submitted"}


@app.get("/api/v1/admin/feedback")
async def list_feedback(
    feedback: FeedbackService = Depends(get_feedback_service),
):
    """List all feedback items (admin only)."""
    all_fb = feedback.get_all()
    return {"feedback": [asdict(f) for f in all_fb], "count": len(all_fb)}


@app.post("/api/v1/admin/feedback/{feedback_id}/review")
async def review_feedback(
    feedback_id: str,
    status: str,
    resolution: Optional[str] = None,
    reviewed_by: Optional[str] = None,
    feedback: FeedbackService = Depends(get_feedback_service),
):
    """Update feedback status (admin action)."""
    ok = feedback.review(feedback_id, status, resolution, reviewed_by)
    if not ok:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"status": "ok"}


# ── Admin & audit endpoints ────────────────────────────────────────────────────

@app.get("/api/v1/admin/audit")
async def query_audit(
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    auth: AuthService = Depends(get_auth_service),
):
    """Query audit log entries."""
    auditor = app_state["assistant"].auditor
    entries = auditor.query(event_type, user_id, start_date, end_date, limit)
    return {"entries": entries, "count": len(entries)}


@app.get("/api/v1/admin/audit/export")
async def export_audit(
    format: str = "jsonl",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    auth: AuthService = Depends(get_auth_service),
):
    """Export audit log to file."""
    auditor = app_state["assistant"].auditor
    output_path = f"logs/audit_export_{int(time.time())}.{format}"
    count = auditor.export_for_compliance(output_path, start_date, end_date, format)
    return {"file": output_path, "entries": count}


@app.get("/api/v1/admin/stats")
async def admin_stats():
    """System statistics dashboard."""
    services = app_state
    stats = {
        "knowledge": services["knowledge_service"].get_stats(),
        "audit": services["assistant"].auditor.get_stats(),
        "feedback": services["feedback_service"].get_stats(),
        "uptime_seconds": time.time() - services.get("start_time", time.time()),
    }
    return stats


# ── Document ingestion administration ─────────────────────────────────────────

@app.post("/api/v1/admin/ingest/batch")
async def batch_ingest(
    directory: str = "knowledge/raw",
    background_tasks: BackgroundTasks = None,
    ks: KnowledgeService = Depends(get_knowledge_service),
):
    """Ingest all documents in a directory (async)."""
    def _ingest_task():
        ingest_svc = ks.assistant.retrieval.ingest_service
        # Rebuild from directory
        from retrieval.ingest_service import IngestService
        # (Re-instantiate to avoid controller issues)
        pass

    background_tasks.add_task(_ingest_task)
    return {"status": "queued", "directory": directory}


# ── Main entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "src.backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
