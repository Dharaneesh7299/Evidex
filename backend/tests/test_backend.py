"""Automated tests for Evidex backend.

Covers health, PDF ingestion, chunking, retrieval, claim support classification,
citation validation, investigations lifecycle, and error handling.
All external AI calls are deterministic or mocked.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Generator

import fitz
import pytest
from fastapi.testclient import TestClient

from app.db.database import Database, reset_db_for_tests
from app.main import app
from app.services.pdf_service import (
    chunk_pages,
    detect_scanned,
    extract_metadata,
    extract_pages,
)
from app.services.retrieval import (
    Retriever,
    validate_evidence_reference,
)
from app.tools.research_tools import (
    check_claim_support,
    extract_claims,
    extract_paper_metadata,
    rank_paper_relevance,
    validate_report_citations,
)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def test_db(tmp_path: Path) -> Database:
    db_path = tmp_path / "test_evidex.db"
    return Database(db_path)


def _create_sample_pdf(text_pages: list[str]) -> bytes:
    doc = fitz.open()
    for text in text_pages:
        p = doc.new_page()
        p.insert_textbox(fitz.Rect(50, 50, 500, 750), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ---------------------------------------------------------------------------
# 1. Health & System
# ---------------------------------------------------------------------------
def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "Evidex API"
    assert "version" in data
    assert "papers_count" in data


# ---------------------------------------------------------------------------
# 2. PDF Text Extraction & Page-Number Preservation
# ---------------------------------------------------------------------------
def test_pdf_extraction_page_preservation(tmp_path: Path) -> None:
    page1 = "Title: Advanced Clinical Vision Transformers\nAuthors: Jane Doe, John Smith\nAbstract: We evaluate transformers on X-rays."
    page2 = "Methodology: We trained on 5000 chest radiographs with AdamW optimizer."
    page3 = "Results: Test accuracy improved by 5.4% over ResNet-50. Limitations: Evaluated on single center."

    pdf_bytes = _create_sample_pdf([page1, page2, page3])
    pdf_file = tmp_path / "test_paper.pdf"
    pdf_file.write_bytes(pdf_bytes)

    pages = extract_pages(pdf_file)
    assert len(pages) == 3
    assert pages[0].page_number == 1
    assert "Advanced Clinical Vision Transformers" in pages[0].text
    assert pages[1].page_number == 2
    assert "Methodology" in pages[1].text
    assert pages[2].page_number == 3
    assert "Limitations" in pages[2].text
    assert not detect_scanned(pages)


# ---------------------------------------------------------------------------
# 3. Chunk Metadata & Retrieval
# ---------------------------------------------------------------------------
def test_chunk_metadata_and_retrieval(test_db: Database, tmp_path: Path) -> None:
    page1 = "Hierarchical vision transformers capture fine-grained dermoscopic boundaries."
    page2 = "On ISIC-2020 archive, model achieved 89.4% balanced accuracy, outperforming baselines."

    pdf_bytes = _create_sample_pdf([page1, page2])
    pdf_file = tmp_path / "dermoscopy.pdf"
    pdf_file.write_bytes(pdf_bytes)

    pages = extract_pages(pdf_file)
    meta = extract_metadata(pages, "dermoscopy.pdf")
    chunks = chunk_pages("paper_test_01", pages)

    assert len(chunks) >= 2
    assert all(c.paper_id == "paper_test_01" for c in chunks)
    assert all(c.page_number in (1, 2) for c in chunks)

    test_db.create_paper({
        "id": "paper_test_01",
        "title": meta.get("title"),
        "original_filename": "dermoscopy.pdf",
        "stored_path": str(pdf_file),
        "file_size": len(pdf_bytes),
        "page_count": len(pages),
        "char_count": sum(len(p.text) for p in pages),
        "status": "ready",
    })
    test_db.insert_chunks("paper_test_01", [c.__dict__ for c in chunks])

    retriever = Retriever(test_db, "paper_test_01")
    hits = retriever.search("accuracy dermoscopic", top_k=2)
    assert len(hits) > 0
    assert hits[0].paper_id == "paper_test_01"
    assert hits[0].page_number in (1, 2)


# ---------------------------------------------------------------------------
# 4. Evidence Reference Validation
# ---------------------------------------------------------------------------
def test_evidence_reference_validation(test_db: Database, tmp_path: Path) -> None:
    page_text = "On ISIC-2020 archive, model achieved 89.4% balanced accuracy."
    pdf_bytes = _create_sample_pdf([page_text])
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(pdf_bytes)

    pages = extract_pages(pdf_file)
    chunks = chunk_pages("paper_val_01", pages)

    test_db.create_paper({
        "id": "paper_val_01",
        "title": "Sample Paper",
        "original_filename": "sample.pdf",
        "stored_path": str(pdf_file),
        "file_size": len(pdf_bytes),
        "page_count": 1,
        "char_count": len(page_text),
        "status": "ready",
    })
    test_db.insert_chunks("paper_val_01", [c.__dict__ for c in chunks])

    # Valid passage
    is_valid, note = validate_evidence_reference(test_db, "paper_val_01", 1, "model achieved 89.4% balanced accuracy")
    assert is_valid

    # Completely fabricated passage
    is_invalid, fail_note = validate_evidence_reference(test_db, "paper_val_01", 1, "quantum computational entanglement in superconductors")
    assert not is_invalid


# ---------------------------------------------------------------------------
# 5. Claim Support Classification
# ---------------------------------------------------------------------------
def test_claim_support_classification() -> None:
    claim = "The proposed model improves classification accuracy on dermoscopic images."
    
    # Strongly supported
    evidence_sup = "Our multi-scale transformer consistently improved classification accuracy across different lesion subtypes."
    rel_sup, _ = check_claim_support(claim, evidence_sup)
    assert rel_sup in ("supported_by_document", "partially_supports")

    # Conflicting / qualifying
    evidence_conf = "However, classification accuracy degraded by 6.8% and fails to improve on dark skin phenotypes."
    rel_conf, _ = check_claim_support(claim, evidence_conf)
    assert rel_conf == "potentially_conflicting_evidence"

    # Insufficient
    evidence_empty = ""
    rel_empty, _ = check_claim_support(claim, evidence_empty)
    assert rel_empty == "insufficient_information"


# ---------------------------------------------------------------------------
# 6. Report Citation Validation
# ---------------------------------------------------------------------------
def test_report_citation_validation(test_db: Database, tmp_path: Path) -> None:
    page_text = "Evaluation confirmed 91.2% sensitivity for melanoma detection."
    pdf_bytes = _create_sample_pdf([page_text])
    pdf_file = tmp_path / "val_rep.pdf"
    pdf_file.write_bytes(pdf_bytes)

    pages = extract_pages(pdf_file)
    chunks = chunk_pages("paper_rep_01", pages)

    test_db.create_paper({
        "id": "paper_rep_01",
        "title": "Validation Study",
        "original_filename": "val_rep.pdf",
        "stored_path": str(pdf_file),
        "file_size": len(pdf_bytes),
        "page_count": 1,
        "char_count": len(page_text),
        "status": "ready",
    })
    test_db.insert_chunks("paper_rep_01", [c.__dict__ for c in chunks])

    report = {
        "main_claims": [{"text": "Melanoma sensitivity reached 91.2%"}],
        "supporting_evidence": [
            {
                "paper_id": "paper_rep_01",
                "page_number": 1,
                "passage": "Evaluation confirmed 91.2% sensitivity for melanoma detection.",
            }
        ],
    }

    status, notes = validate_report_citations(test_db, report)
    assert status == "valid"


# ---------------------------------------------------------------------------
# 7. Invalid File Handling & API Upload
# ---------------------------------------------------------------------------
def test_invalid_file_upload_rejected(client: TestClient) -> None:
    # Non-PDF extension
    resp = client.post(
        "/api/papers/upload",
        files={"file": ("test.txt", io.BytesIO(b"Hello text"), "text/plain")},
    )
    assert resp.status_code == 400
    assert "Only PDF documents" in resp.json()["detail"]

    # PDF extension but corrupted header
    resp_corrupt = client.post(
        "/api/papers/upload",
        files={"file": ("fake.pdf", io.BytesIO(b"NOT A REAL PDF FILE"), "application/pdf")},
    )
    assert resp_corrupt.status_code == 400
    assert "Invalid PDF format" in resp_corrupt.json()["detail"]


def test_valid_pdf_upload_and_delete(client: TestClient) -> None:
    pdf_bytes = _create_sample_pdf(["Valid PDF page content with sufficient words for testing."])
    resp = client.post(
        "/api/papers/upload",
        files={"file": ("valid_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 201
    data = resp.json()
    paper_id = data["paper"]["id"]
    assert paper_id.startswith("paper_")
    assert data["chunks"] >= 1

    # Verify listing
    list_resp = client.get("/api/papers")
    assert list_resp.status_code == 200
    ids = [p["id"] for p in list_resp.json()]
    assert paper_id in ids

    # Page view
    page_resp = client.get(f"/api/papers/{paper_id}/page/1")
    assert page_resp.status_code == 200
    assert "Valid PDF page content" in page_resp.json()["text"]

    # Delete
    del_resp = client.delete(f"/api/papers/{paper_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"


# ---------------------------------------------------------------------------
# 8. Investigation Creation & Sample Report Access
# ---------------------------------------------------------------------------
def test_sample_investigation_endpoint(client: TestClient) -> None:
    resp = client.get("/api/sample")
    assert resp.status_code == 200
    inv_id = resp.json()["investigation_id"]

    # Check investigation details
    detail_resp = client.get(f"/api/investigations/{inv_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["status"] == "completed"
    assert len(detail["relevant_papers"]) == 3
    assert len(detail["main_claims"]) >= 3
    assert len(detail["supporting_evidence"]) >= 3
    assert detail["report"]["validation_status"] == "valid"

    # Check report endpoint
    rep_resp = client.get(f"/api/investigations/{inv_id}/report")
    assert rep_resp.status_code == 200
    report = rep_resp.json()
    assert "# Evidex Investigation Report" in report["markdown"]
    assert "Executive Summary" in report["markdown"]
