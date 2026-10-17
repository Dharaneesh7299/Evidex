"""FastAPI REST router for Evidex."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from app.agents.orchestrator import ResearchOrchestrator
from app.core.config import Settings, get_settings
from app.db.database import Database, get_db
from app.schemas.schemas import (
    ClaimOut,
    ComparisonRow,
    EvidenceItem,
    InvestigationCreateRequest,
    InvestigationDetail,
    InvestigationReport,
    InvestigationStatus,
    InvestigationSummary,
    PaperOut,
    PaperRelevance,
    PaperUploadResponse,
)
from app.services.pdf_service import (
    chunk_pages,
    detect_scanned,
    extract_metadata,
    extract_pages,
    generate_paper_id,
    safe_filename,
)
from app.services.sample_service import SAMPLE_INVESTIGATION_ID, seed_sample_data

logger = logging.getLogger(__name__)

api_router = APIRouter()


# ---------------------------------------------------------------------------
# Health & Overview
# ---------------------------------------------------------------------------
@api_router.get("/health", tags=["System"])
def get_health(
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_db),
) -> Dict[str, Any]:
    """System health check and diagnostic overview."""
    papers = db.list_papers()
    invs = db.list_investigations()
    return {
        "status": "ok",
        "service": "Evidex API",
        "version": "1.0.0",
        "has_gemini": settings.has_gemini(),
        "gemini_model": settings.gemini_model,
        "papers_count": len(papers),
        "investigations_count": len(invs),
    }


# ---------------------------------------------------------------------------
# Papers Management
# ---------------------------------------------------------------------------
@api_router.post(
    "/papers/upload",
    response_model=PaperUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Papers"],
)
async def upload_paper(
    file: UploadFile = File(...),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PaperUploadResponse:
    """Upload and process a research PDF document."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents (.pdf) are supported.",
        )

    # Generate identifiers and safe destination
    paper_id = generate_paper_id()
    clean_name = safe_filename(file.filename)
    stored_path = settings.upload_dir / f"{paper_id}_{clean_name}"

    try:
        # Stream file to disk while enforcing max upload size
        total_bytes = 0
        with open(stored_path, "wb") as buffer:
            while chunk := await file.read(1024 * 64):
                total_bytes += len(chunk)
                if total_bytes > settings.max_upload_bytes:
                    stored_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum size of {settings.max_upload_bytes // (1024 * 1024)} MB.",
                    )
                buffer.write(chunk)

        # Validate PDF header magic bytes
        with open(stored_path, "rb") as f:
            header = f.read(5)
            if header != b"%PDF-":
                stored_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid PDF format: Missing %PDF- header.",
                )

        # Extract pages with PyMuPDF
        try:
            pages = extract_pages(stored_path)
        except Exception as e:
            stored_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not parse PDF content: {e}",
            )

        if not pages:
            stored_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="PDF contains no extractable pages.",
            )

        is_scanned = detect_scanned(pages)
        char_count = sum(len(p.text) for p in pages)
        meta = extract_metadata(pages, file.filename, pdf_path=stored_path)

        if is_scanned:
            meta["notes"] = "Scanned/image-only document detected. Optical Character Recognition (OCR) may be required."

        # Chunk pages
        chunks = chunk_pages(paper_id, pages)

        # Persist paper record
        paper_record = db.create_paper({
            "id": paper_id,
            "title": meta.get("title") or file.filename,
            "authors": meta.get("authors"),
            "year": meta.get("year"),
            "original_filename": file.filename,
            "stored_path": str(stored_path),
            "file_size": total_bytes,
            "page_count": len(pages),
            "char_count": char_count,
            "status": "ready",
            "metadata": meta,
        })

        # Insert chunks
        db.insert_chunks(paper_id, [c.__dict__ for c in chunks])

        return PaperUploadResponse(
            paper=PaperOut(**paper_record),
            chunks=len(chunks),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to process upload for '{file.filename}': {e}")
        stored_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing paper: {str(e)}",
        )


@api_router.get("/papers", response_model=List[PaperOut], tags=["Papers"])
def list_papers(db: Database = Depends(get_db)) -> List[PaperOut]:
    """Retrieve all uploaded research papers."""
    papers = db.list_papers()
    return [PaperOut(**p) for p in papers]


@api_router.get("/papers/{paper_id}", response_model=PaperOut, tags=["Papers"])
def get_paper(paper_id: str, db: Database = Depends(get_db)) -> PaperOut:
    """Retrieve details for a specific research paper."""
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Paper '{paper_id}' not found.")
    return PaperOut(**paper)


@api_router.get("/papers/{paper_id}/page/{page_number}", tags=["Papers"])
def get_paper_page(paper_id: str, page_number: int, db: Database = Depends(get_db)) -> Dict[str, Any]:
    """Get raw extracted text for a specific page to verify citations."""
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Paper '{paper_id}' not found.")
    if page_number < 1 or page_number > paper.get("page_count", 1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Page number {page_number} is out of bounds (1-{paper.get('page_count')}).",
        )
    text = db.get_page_text(paper_id, page_number)
    return {
        "paper_id": paper_id,
        "paper_title": paper.get("title") or paper.get("original_filename"),
        "page_number": page_number,
        "text": text,
    }


@api_router.delete("/papers/{paper_id}", tags=["Papers"])
def delete_paper(paper_id: str, db: Database = Depends(get_db)) -> Dict[str, Any]:
    """Delete a paper, its chunks, and stored file from disk."""
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Paper '{paper_id}' not found.")
    
    # Remove file from disk
    stored = paper.get("stored_path")
    if stored:
        try:
            Path(stored).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Could not delete physical file '{stored}': {e}")

    db.delete_paper(paper_id)
    return {"status": "deleted", "paper_id": paper_id}


# ---------------------------------------------------------------------------
# Investigations
# ---------------------------------------------------------------------------
def _run_investigation_task(investigation_id: str) -> None:
    """Background task runner for orchestrator."""
    db = get_db()
    orchestrator = ResearchOrchestrator(db)
    try:
        orchestrator.run_investigation(investigation_id)
    except Exception as e:
        logger.error(f"Background investigation {investigation_id} failed: {e}")


@api_router.post(
    "/investigations",
    response_model=InvestigationSummary,
    status_code=status.HTTP_201_CREATED,
    tags=["Investigations"],
)
def create_investigation(
    req: InvestigationCreateRequest,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db),
) -> InvestigationSummary:
    """Create and start a cross-paper research investigation."""
    for pid in req.paper_ids:
        paper = db.get_paper(pid)
        if not paper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Paper '{pid}' does not exist.",
            )

    inv = db.create_investigation(
        research_question=req.research_question,
        paper_ids=req.paper_ids,
    )

    # Enqueue background execution
    background_tasks.add_task(_run_investigation_task, inv["id"])

    return InvestigationSummary(
        id=inv["id"],
        research_question=inv["research_question"],
        status=inv["status"],
        stage=inv["stage"],
        progress=inv["progress"],
        paper_ids=inv["paper_ids"],
        created_at=inv["created_at"],
        updated_at=inv["updated_at"],
    )


@api_router.get("/investigations", response_model=List[InvestigationSummary], tags=["Investigations"])
def list_investigations(db: Database = Depends(get_db)) -> List[InvestigationSummary]:
    """List all investigations."""
    invs = db.list_investigations()
    return [
        InvestigationSummary(
            id=i["id"],
            research_question=i["research_question"],
            status=i["status"],
            stage=i["stage"],
            progress=i["progress"],
            paper_ids=i.get("paper_ids", []),
            created_at=i["created_at"],
            updated_at=i["updated_at"],
        )
        for i in invs
    ]


@api_router.get("/investigations/{investigation_id}/status", response_model=InvestigationStatus, tags=["Investigations"])
def get_investigation_status(investigation_id: str, db: Database = Depends(get_db)) -> InvestigationStatus:
    """Poll investigation execution status and current stage."""
    inv = db.get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")
    return InvestigationStatus(
        id=inv["id"],
        status=inv["status"],
        stage=inv["stage"],
        progress=inv["progress"],
        error=inv.get("error"),
        updated_at=inv["updated_at"],
    )


@api_router.get("/investigations/{investigation_id}", response_model=InvestigationDetail, tags=["Investigations"])
def get_investigation_detail(investigation_id: str, db: Database = Depends(get_db)) -> InvestigationDetail:
    """Retrieve full investigation details including papers, claims, evidence, and report."""
    inv = db.get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    # Fetch related records
    raw_papers = db.get_investigation_papers(investigation_id)
    raw_claims = db.list_claims(investigation_id)
    raw_evidence = db.list_evidence(investigation_id)
    raw_report = db.get_report(investigation_id)

    # Format relevant papers
    relevant_papers: List[PaperRelevance] = []
    for rp in raw_papers:
        relevant_papers.append(
            PaperRelevance(
                paper_id=rp["paper_id"],
                score=rp.get("relevance_score", 0.0),
                label=rp.get("relevance_label", "Moderate"),
                explanation=rp.get("relevance_explanation", ""),
                summary=rp.get("summary"),
            )
        )

    # Format evidence items
    evidence_items = [EvidenceItem(**e) for e in raw_evidence]

    # Format claims with attached evidence IDs
    claims_out: List[ClaimOut] = []
    for c in raw_claims:
        linked_evi = [e.id for e in evidence_items if e.claim_id == c["id"]]
        claims_out.append(
            ClaimOut(
                id=c["id"],
                investigation_id=c["investigation_id"],
                paper_id=c.get("paper_id"),
                text=c["text"],
                category=c["category"],
                page_number=c.get("page_number"),
                chunk_id=c.get("chunk_id"),
                evidence_relationship=c["evidence_relationship"],
                explanation=c.get("explanation"),
                limitations=c.get("limitations", []),
                evidence_ids=linked_evi,
            )
        )

    # Extract comparison and disagreements from report JSON if available
    comparison_rows: List[ComparisonRow] = []
    disagreements = []
    report_out: Optional[InvestigationReport] = None

    if raw_report and raw_report.get("content"):
        content = raw_report["content"]
        if "cross_paper_comparison" in content:
            comparison_rows = [ComparisonRow(**row) for row in content["cross_paper_comparison"]]
        if "disagreements" in content:
            disagreements = content["disagreements"]
        try:
            report_out = InvestigationReport(**content)
        except Exception as e:
            logger.warning(f"Could not parse full report schema: {e}")

    return InvestigationDetail(
        id=inv["id"],
        research_question=inv["research_question"],
        status=inv["status"],
        stage=inv["stage"],
        progress=inv["progress"],
        paper_ids=inv.get("paper_ids", []),
        created_at=inv["created_at"],
        updated_at=inv["updated_at"],
        relevant_papers=relevant_papers,
        main_claims=claims_out,
        supporting_evidence=evidence_items,
        cross_paper_comparison=comparison_rows,
        disagreements=disagreements,
        report=report_out,
    )


@api_router.get("/investigations/{investigation_id}/claims", response_model=List[ClaimOut], tags=["Investigations"])
def get_investigation_claims(investigation_id: str, db: Database = Depends(get_db)) -> List[ClaimOut]:
    """Retrieve claims extracted for this investigation."""
    claims = db.list_claims(investigation_id)
    evidence = db.list_evidence(investigation_id)
    res = []
    for c in claims:
        linked = [e["id"] for e in evidence if e.get("claim_id") == c["id"]]
        res.append(
            ClaimOut(
                id=c["id"],
                investigation_id=c["investigation_id"],
                paper_id=c.get("paper_id"),
                text=c["text"],
                category=c["category"],
                page_number=c.get("page_number"),
                chunk_id=c.get("chunk_id"),
                evidence_relationship=c["evidence_relationship"],
                explanation=c.get("explanation"),
                limitations=c.get("limitations", []),
                evidence_ids=linked,
            )
        )
    return res


@api_router.get("/investigations/{investigation_id}/evidence", response_model=List[EvidenceItem], tags=["Investigations"])
def get_investigation_evidence(investigation_id: str, db: Database = Depends(get_db)) -> List[EvidenceItem]:
    """Retrieve all evidence passages retrieved for this investigation."""
    evidence = db.list_evidence(investigation_id)
    return [EvidenceItem(**e) for e in evidence]


@api_router.get("/investigations/{investigation_id}/comparison", response_model=List[ComparisonRow], tags=["Investigations"])
def get_investigation_comparison(investigation_id: str, db: Database = Depends(get_db)) -> List[ComparisonRow]:
    """Retrieve the cross-paper comparison table rows."""
    report = db.get_report(investigation_id)
    if not report or not report.get("content"):
        return []
    rows = report["content"].get("cross_paper_comparison", [])
    return [ComparisonRow(**r) for r in rows]


@api_router.get("/investigations/{investigation_id}/report", response_model=InvestigationReport, tags=["Investigations"])
def get_investigation_report(investigation_id: str, db: Database = Depends(get_db)) -> InvestigationReport:
    """Retrieve the validated structured research report and markdown representation."""
    report = db.get_report(investigation_id)
    if not report or not report.get("content"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report for investigation '{investigation_id}' is not yet available.",
        )
    return InvestigationReport(**report["content"])


@api_router.post("/investigations/{investigation_id}/rerun", status_code=status.HTTP_202_ACCEPTED, tags=["Investigations"])
def rerun_investigation(
    investigation_id: str,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db),
) -> Dict[str, str]:
    """Rerun an existing investigation."""
    inv = db.get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")
    
    db.update_investigation(investigation_id, status="pending", stage="queued", progress=0, error=None)
    background_tasks.add_task(_run_investigation_task, investigation_id)
    return {"message": "Investigation execution enqueued."}


# ---------------------------------------------------------------------------
# Sample Report Seeder
# ---------------------------------------------------------------------------
@api_router.get("/sample", tags=["Sample"])
@api_router.post("/sample/seed", tags=["Sample"])
def load_sample_report(db: Database = Depends(get_db)) -> Dict[str, Any]:
    """Seed or fetch the canonical sample investigation with 3 grounded papers."""
    sample_id = seed_sample_data(db)
    return {
        "investigation_id": sample_id,
        "message": "Sample investigation ready.",
    }
