"""
Document ingestion pipeline: PDF, DOCX, HTML, plain text → extracted text + metadata.
Ensures content provenance with SHA-256 hashing and license tracking.
"""

import logging
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from urllib.parse import urlparse

# Optional imports; gracefully degrade if not installed
try:
    from unstructured.partition.auto import partition
    from unstructured.staging.base import convert_to_dict
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    logging.warning("unstructured library not available; install with: pip install 'unstructured[local]'")

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class DocumentMetadata:
    """Provenance metadata for ingested documents."""
    source_id: str
    file_path: str
    file_hash: str
    content_hash: str
    title: Optional[str] = None
    author: Optional[str] = None
    organization: Optional[str] = None
    date: Optional[str] = None
    license_: Optional[str] = None
    url: Optional[str] = None
    mime_type: Optional[str] = None
    ingestion_timestamp: str = ""
    version: str = "1.0"
    language: str = "en"
    pages: Optional[int] = None


class DocumentLoader:
    """
    Unified document loader supporting PDF, DOCX, HTML, TXT, MD.
    Extracts text and generates rich provenance metadata.
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".html": "text/html",
        ".htm": "text/html",
        ".txt": "text/plain",
        ".md": "text/markdown",
    }

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialize document loader.

        Args:
            chunk_size: Maximum characters per chunk
            chunk_overlap: Overlap between consecutive chunks in characters
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_file(self, file_path: str, metadata_override: Optional[Dict[str, Any]] = None) -> Tuple[List[str], List[DocumentMetadata]]:
        """
        Load a single file and split into chunks.

        Args:
            file_path: Path to document
            metadata_override: Override or extend auto-detected metadata

        Returns:
            (chunks, metadata_dict) where len(chunks) == len(metadata_list)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        extension = path.suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {extension}")

        # Compute file hash for provenance
        file_hash = self._compute_file_hash(file_path)

        # Read raw content
        raw_text = self._extract_text(file_path, extension)

        # Generate content hash for exact deduplication
        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        # Extract/derive metadata
        metadata = DocumentMetadata(
            source_id=path.stem,
            file_path=str(path.absolute()),
            file_hash=file_hash,
            content_hash=content_hash,
            mime_type=self.SUPPORTED_EXTENSIONS[extension],
            ingestion_timestamp=datetime.utcnow().isoformat() + "Z",
        )

        # Apply overrides/enhancements
        if metadata_override:
            for key, value in metadata_override.items():
                if hasattr(metadata, key):
                    setattr(metadata, key, value)

        # Split into overlapping chunks
        chunks = self._chunk_text(raw_text)
        metadata_list = [metadata for _ in chunks]

        logger.info(f"Loaded {file_path}: {len(chunks)} chunks, {len(raw_text)} characters")
        return chunks, metadata_list

    def load_directory(
        self,
        directory: str,
        recursive: bool = True,
        metadata_override: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[str], List[DocumentMetadata]]:
        """
        Load all supported documents from a directory.

        Args:
            directory: Directory path
            recursive: Descend into subdirectories
            metadata_override: Apply to all documents

        Returns:
            Combined list of chunks and metadata across all files
        """
        all_chunks = []
        all_metadata = []

        dir_path = Path(directory)
        pattern = "**/*" if recursive else "*"

        for ext in self.SUPPORTED_EXTENSIONS:
            for file_path in dir_path.glob(f"{pattern}{ext}"):
                try:
                    chunks, metadata_list = self.load_file(str(file_path), metadata_override)
                    all_chunks.extend(chunks)
                    all_metadata.extend(metadata_list)
                except Exception as e:
                    logger.error(f"Failed to load {file_path}: {e}")

        logger.info(f"Directory load complete: {len(all_chunks)} total chunks from {directory}")
        return all_chunks, all_metadata

    def _extract_text(self, file_path: str, extension: str) -> str:
        """Extract raw text from a file based on its extension."""
        path = Path(file_path)

        if extension == ".pdf":
            return self._extract_pdf(path)
        elif extension == ".docx":
            return self._extract_docx(path)
        elif extension in {".html", ".htm"}:
            return self._extract_html(path)
        elif extension in {".txt", ".md"}:
            return self._extract_text_file(path)
        else:
            raise ValueError(f"Unsupported extension: {extension}")

    def _extract_pdf(self, path: Path) -> str:
        """Extract text from PDF using PyMuPDF (fast) or unstructured."""
        if PYMUPDF_AVAILABLE:
            doc = fitz.open(path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        elif UNSTRUCTURED_AVAILABLE:
            elements = partition(str(path))
            return "\n".join([str(el) for el in elements])
        else:
            raise ImportError("Install PyMuPDF or unstructured for PDF support: pip install pymupdf")

    def _extract_docx(self, path: Path) -> str:
        """Extract text from DOCX using python-docx."""
        if not DOCX_AVAILABLE:
            raise ImportError("Install python-docx: pip install python-docx")
        doc = Document(path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])

    def _extract_html(self, path: Path) -> str:
        """Extract text from HTML, stripping tags."""
        from bs4 import BeautifulSoup

        with open(path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        return soup.get_text(separator="\n", strip=True)

    def _extract_text_file(self, path: Path) -> str:
        """Read text file with encoding detection."""
        with open(path, "rb") as f:
            raw = f.read()

        if CHARDET_AVAILABLE:
            detected = chardet.detect(raw)
            encoding = detected["encoding"] or "utf-8"
        else:
            encoding = "utf-8"

        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            # Fallback: decode with errors replaced
            return raw.decode("utf-8", errors="replace")

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks of specified size.
        Chunks respect sentence boundaries where possible.
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break

            # Try to break at sentence boundary
            break_chars = {".", "!", "?", "\n"}
            best_break = -1
            for i in range(end, max(start, end - 200), -1):
                if text[i] in break_chars:
                    best_break = i + 1
                    break

            if best_break == -1:
                # No sentence boundary; break at word
                for i in range(end, max(start, end - 100), -1):
                    if text[i] == " ":
                        best_break = i + 1
                        break

            if best_break == -1:
                best_break = end

            chunks.append(text[start:best_break].strip())
            start = best_break - self.chunk_overlap
            if start < 0:
                start = 0

        return chunks

    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA-256 hash of file contents."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def compute_text_hash(self, text: str) -> str:
        """Compute SHA-256 hash of text content."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_and_split(
    file_paths: List[str],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> Tuple[List[str], List[DocumentMetadata]]:
    """
    Convenience function to load multiple files.

    Returns:
        (all_chunks, all_metadata)
    """
    loader = DocumentLoader(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    all_chunks = []
    all_metadata = []

    for fp in file_paths:
        chunks, metadata = loader.load_file(fp)
        all_chunks.extend(chunks)
        all_metadata.extend(metadata)

    return all_chunks, all_metadata
