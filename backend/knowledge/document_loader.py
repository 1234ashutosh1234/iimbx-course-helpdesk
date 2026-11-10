"""Document loader for official course documents with integrity verification."""

import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional

from backend.knowledge.schemas import CorpusState, LoadedDocument
from backend.knowledge.document_registry import DOCUMENT_METADATA_REGISTRY, EXPECTED_DOCUMENTS


class DocumentLoader:
    """Safely loads and validates the official course documents from disk."""

    def __init__(self, course_docs_dir: Optional[str] = None):
        """Initialize loader with the path to the course documents directory.
        
        Args:
            course_docs_dir: Optional path string. Defaults to workspace 'course_docs'.
        """
        if course_docs_dir is None:
            # Resolve relative to project root
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.docs_dir = base_dir / "course_docs"
        else:
            self.docs_dir = Path(course_docs_dir)

    def load_corpus(self) -> CorpusState:
        """Load all expected documents, compute checksums, and generate corpus version hash.

        Returns:
            CorpusState: Validated in-memory documents and deterministic corpus hash.

        Raises:
            FileNotFoundError: If any of the required course documents are missing.
            IOError: If a document cannot be read.
        """
        if not self.docs_dir.exists() or not self.docs_dir.is_dir():
            raise FileNotFoundError(f"Course documents directory not found at: {self.docs_dir}")

        loaded_docs: Dict[str, LoadedDocument] = {}
        hasher = hashlib.sha256()

        for filename in sorted(EXPECTED_DOCUMENTS):
            file_path = self.docs_dir / filename
            if not file_path.exists():
                raise FileNotFoundError(
                    f"Required course document missing: {file_path.resolve()}"
                )

            try:
                # Strictly read-only access with utf-8 encoding
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                raise IOError(f"Failed to read course document '{filename}': {e}") from e

            # Compute SHA-256 for individual file
            file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            
            # Incorporate filename and hash into corpus-level digest
            hasher.update(filename.encode("utf-8"))
            hasher.update(file_hash.encode("utf-8"))

            metadata = DOCUMENT_METADATA_REGISTRY.get(filename)
            if not metadata:
                raise ValueError(f"No metadata registered for document: {filename}")

            loaded_docs[filename] = LoadedDocument(
                filename=filename,
                content=content,
                content_hash=file_hash,
                metadata=metadata
            )

        corpus_version_hash = hasher.hexdigest()

        return CorpusState(
            documents=loaded_docs,
            corpus_version_hash=corpus_version_hash
        )
