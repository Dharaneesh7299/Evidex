"""Accuracy and regression test suite for Evidex.

Verifies:
1. Vision Transformer paper title is not the ICLR 2021 conference header.
2. DenseNet original publication is identified as CVPR 2017.
3. ResNet authors are parsed as real author names, not email addresses.
4. Unsupported clinical, demographic, or cross-center claims are rejected for vision papers.
5. Reference validity is strictly separated from semantic evidence support.
6. Dataset differences (e.g. ImageNet vs CIFAR) are not classified as contradictory findings.
7. Missing evidence produces explicit uncertainty labels.
"""

from pathlib import Path
import pytest

from app.db.database import Database
from app.services.pdf_service import extract_pages, extract_metadata
from app.tools.research_tools import (
    validate_evidence_reference,
    check_claim_support,
    validate_disagreements,
    validate_report_citations,
)
from app.schemas.schemas import DisagreementItem

BACKEND_DIR = Path(__file__).resolve().parents[1]
UPLOADS_DIR = BACKEND_DIR / "uploads"


@pytest.fixture
def temp_db(tmp_path: Path) -> Database:
    db_file = tmp_path / "test_audit.db"
    return Database(db_file)


# ---------------------------------------------------------------------------
# Test 1: Vision Transformer Paper Title Extraction
# ---------------------------------------------------------------------------
def test_vit_title_not_conference_header():
    vit_pdf = UPLOADS_DIR / "paper_dbe3a9508c6f_2010_11929v2.pdf"
    assert vit_pdf.exists(), f"ViT PDF missing at {vit_pdf}"

    pages = extract_pages(vit_pdf, max_pages=3)
    meta = extract_metadata(pages, vit_pdf.name, pdf_path=vit_pdf)

    # Must NOT use the ICLR conference header as title
    assert "published as a conference paper at iclr 2021" not in meta["title"].lower()
    assert meta["title"] != "Published as a conference paper at ICLR 2021"

    # Must extract the true title
    assert "image is worth 16x16 words" in meta["title"].lower()
    assert meta["year"] == "2021"


# ---------------------------------------------------------------------------
# Test 2: DenseNet Publication Year CVPR 2017
# ---------------------------------------------------------------------------
def test_densenet_publication_identified_as_cvpr_2017():
    dense_pdf = UPLOADS_DIR / "paper_0606a733a8aa_Densely_Connected_Convolutional_Networks_CVPR_2017.pdf"
    assert dense_pdf.exists(), f"DenseNet PDF missing at {dense_pdf}"

    pages = extract_pages(dense_pdf, max_pages=3)
    meta = extract_metadata(pages, dense_pdf.name, pdf_path=dense_pdf)

    assert meta["year"] == "2017"
    assert "densely connected convolutional networks" in meta["title"].lower()
    assert "Gao Huang" in meta["authors"]


# ---------------------------------------------------------------------------
# Test 3: ResNet Authors Cleanly Extracted (Not Email List)
# ---------------------------------------------------------------------------
def test_resnet_authors_not_email():
    resnet_pdf = UPLOADS_DIR / "paper_1b0f34250d2d_1512.03385.pdf"
    assert resnet_pdf.exists(), f"ResNet PDF missing at {resnet_pdf}"

    pages = extract_pages(resnet_pdf, max_pages=3)
    meta = extract_metadata(pages, resnet_pdf.name, pdf_path=resnet_pdf)

    # Must not contain email delimiters
    assert "@" not in meta["authors"]
    assert "{" not in meta["authors"]
    assert "Kaiming He" in meta["authors"]
    assert "Jian Sun" in meta["authors"]
    assert meta["year"] == "2015"


# ---------------------------------------------------------------------------
# Test 4: Rejection of Unsupported Clinical/Demographic Claims
# ---------------------------------------------------------------------------
def test_rejection_of_unsupported_clinical_claims(temp_db: Database):
    # Setup two mock vision papers with only computer vision terminology
    pid1 = "paper_vision_a"
    pid2 = "paper_vision_b"
    temp_db.create_paper({
        "id": pid1,
        "title": "Residual Networks for ImageNet",
        "original_filename": "resnet.pdf",
        "file_size": 1000,
        "page_count": 2,
        "char_count": 500,
        "status": "ready",
    })
    temp_db.create_paper({
        "id": pid2,
        "title": "Dense Convolutional Networks",
        "original_filename": "densenet.pdf",
        "file_size": 1000,
        "page_count": 2,
        "char_count": 500,
        "status": "ready",
    })
    temp_db.insert_chunks(pid1, [{
        "id": "c1",
        "paper_id": pid1,
        "page_number": 1,
        "chunk_index": 0,
        "text": "Deep residual learning eases training on ImageNet classification benchmarks.",
        "token_count": 10,
    }])
    temp_db.insert_chunks(pid2, [{
        "id": "c2",
        "paper_id": pid2,
        "page_number": 1,
        "chunk_index": 0,
        "text": "Dense connectivity improves gradient flow across convolutional feature maps on CIFAR-10.",
        "token_count": 12,
    }])

    # Disagreement claiming unsupported clinical/demographic sensitivity
    spurious_disagreement = DisagreementItem(
        topic="Cross-center demographic degradation",
        description="The method fails across demographic cohorts and clinical scanner hardware manufacturers.",
        paper_ids=[pid1, pid2],
        evidence_ids=["c1"],
    )

    validated_disagreements, notes = validate_disagreements(
        temp_db, [spurious_disagreement], [pid1, pid2]
    )

    # Must reject the ungrounded clinical disagreement
    assert any("Rejected unsupported disagreement" in note for note in notes)
    # Must fallback to explicit honest label
    assert validated_disagreements[0].topic == "No verified disagreement identified"


# ---------------------------------------------------------------------------
# Test 5: Reference Validity is Separated from Semantic Evidence Support
# ---------------------------------------------------------------------------
def test_reference_validity_separated_from_evidence_support(temp_db: Database):
    pid = "paper_resnet_test"
    temp_db.create_paper({
        "id": pid,
        "title": "Deep Residual Learning for Image Recognition",
        "original_filename": "resnet.pdf",
        "file_size": 1000,
        "page_count": 1,
        "char_count": 400,
        "status": "ready",
    })
    passage_text = "Deep convolutional neural networks have led to a series of breakthroughs for image classification."
    temp_db.insert_chunks(pid, [{
        "id": "c_rn_1",
        "paper_id": pid,
        "page_number": 1,
        "chunk_index": 0,
        "text": passage_text,
        "token_count": 14,
    }])

    # 1. Reference validity check: The passage DOES exist on page 1 of this paper
    is_ref_valid, reason = validate_evidence_reference(temp_db, pid, 1, passage_text)
    assert is_ref_valid is True

    # 2. Semantic support check: The passage is tested against an unrelated / false claim
    false_claim = "The model reduced 30-day patient ICU mortality by 42% across clinical trials."
    rel, sup_reason = check_claim_support(false_claim, passage_text)

    # Passage exists (reference valid), but FAILS to support the claim
    assert rel == "unsupported_in_available_document"
    assert "does not substantiate domain-specific terms" in sup_reason.lower() or "minimal" in sup_reason.lower()


# ---------------------------------------------------------------------------
# Test 6: Dataset Differences Not Classified as Contradictions
# ---------------------------------------------------------------------------
def test_dataset_differences_not_classified_as_contradictions(temp_db: Database):
    pid1 = "paper_p1"
    pid2 = "paper_p2"
    temp_db.create_paper({
        "id": pid1,
        "title": "Paper One",
        "original_filename": "p1.pdf",
        "file_size": 100,
        "page_count": 1,
        "char_count": 100,
        "status": "ready",
    })
    temp_db.create_paper({
        "id": pid2,
        "title": "Paper Two",
        "original_filename": "p2.pdf",
        "file_size": 100,
        "page_count": 1,
        "char_count": 100,
        "status": "ready",
    })
    temp_db.insert_chunks(pid1, [{"id": "chk1", "paper_id": pid1, "page_number": 1, "chunk_index": 0, "text": "ImageNet results.", "token_count": 2}])
    temp_db.insert_chunks(pid2, [{"id": "chk2", "paper_id": pid2, "page_number": 1, "chunk_index": 0, "text": "CIFAR-10 results.", "token_count": 2}])

    dataset_variance_item = DisagreementItem(
        topic="CIFAR vs ImageNet benchmark datasets",
        description="Paper A was evaluated on ImageNet benchmark while Paper B was evaluated on CIFAR dataset.",
        paper_ids=[pid1, pid2],
        evidence_ids=["chk1"],
    )

    validated_items, notes = validate_disagreements(temp_db, [dataset_variance_item], [pid1, pid2])
    # Must reclassify dataset difference rather than treating it as an empirical contradiction
    assert any("Reclassified disagreement" in note for note in notes)
    assert validated_items[0].topic == "No verified disagreement identified"


# ---------------------------------------------------------------------------
# Test 7: Missing Evidence Produces Explicit Uncertainty Label
# ---------------------------------------------------------------------------
def test_missing_evidence_produces_explicit_uncertainty_label(temp_db: Database):
    # Empty evidence provided to check_claim_support
    rel, reason = check_claim_support("Deeper networks achieve lower classification error", "")
    assert rel == "insufficient_information"
    assert "No supporting passage text provided" in reason

    # Empty disagreements provided to validate_disagreements
    validated, notes = validate_disagreements(temp_db, [], ["paper_a", "paper_b"])
    assert len(validated) == 1
    assert validated[0].topic == "No verified disagreement identified"
    assert "No verified empirical disagreement was identified" in validated[0].description
