"""Unit tests for DocumentLoader."""

import os
import hashlib
from pathlib import Path
import pytest

from backend.knowledge.document_loader import DocumentLoader
from backend.knowledge.document_registry import EXPECTED_DOCUMENTS


def test_all_four_files_load_correctly():
    """Verify that all four official course documents load successfully."""
    loader = DocumentLoader()
    corpus_state = loader.load_corpus()

    assert len(corpus_state.documents) == 4
    for filename in EXPECTED_DOCUMENTS:
        assert filename in corpus_state.documents
        doc = corpus_state.documents[filename]
        assert doc.filename == filename
        assert len(doc.content.strip()) > 0
        assert doc.content_hash == hashlib.sha256(doc.content.encode("utf-8")).hexdigest()
        assert doc.metadata is not None
        assert doc.metadata.filename == filename


def test_missing_file_is_reported_clearly(tmp_path):
    """Verify that a missing document raises FileNotFoundError with explicit details."""
    # Create empty directory with only 1 file
    (tmp_path / "01_course_handbook.txt").write_text("dummy", encoding="utf-8")

    loader = DocumentLoader(course_docs_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load_corpus()

    assert "Required course document missing" in str(exc_info.value)
    assert "02_grading_policy_v1.txt" in str(exc_info.value)


def test_missing_directory_reported():
    """Verify missing directory raises FileNotFoundError."""
    loader = DocumentLoader(course_docs_dir="non_existent_folder_xyz_123")
    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load_corpus()
    assert "Course documents directory not found" in str(exc_info.value)


def test_original_text_files_remain_unchanged():
    """Verify that loading documents never alters the source files or hashes on disk."""
    loader = DocumentLoader()
    docs_dir = loader.docs_dir

    # Compute initial disk hashes
    initial_hashes = {}
    for filename in EXPECTED_DOCUMENTS:
        file_path = docs_dir / filename
        with open(file_path, "rb") as f:
            initial_hashes[filename] = hashlib.sha256(f.read()).hexdigest()

    # Perform load
    corpus_state = loader.load_corpus()

    # Re-verify disk hashes
    for filename in EXPECTED_DOCUMENTS:
        file_path = docs_dir / filename
        with open(file_path, "rb") as f:
            post_load_hash = hashlib.sha256(f.read()).hexdigest()
        assert initial_hashes[filename] == post_load_hash
        assert corpus_state.documents[filename].content_hash == post_load_hash


def test_deterministic_corpus_version_hash():
    """Verify that consecutive loads produce the exact same corpus version hash."""
    loader1 = DocumentLoader()
    state1 = loader1.load_corpus()

    loader2 = DocumentLoader()
    state2 = loader2.load_corpus()

    assert state1.corpus_version_hash == state2.corpus_version_hash
    assert len(state1.corpus_version_hash) == 64
