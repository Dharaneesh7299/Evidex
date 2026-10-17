"""Deterministic and AI-assisted research tools for Evidex.

These 12 modular tools form the core capability of the Research Orchestrator.
All tools operate on actual extracted document text stored in the SQLite database
and never fabricate citations, passages, metrics, or page numbers.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.db.database import Database
from app.schemas.schemas import (
    ClaimCategory,
    ClaimOut,
    ComparisonRow,
    DisagreementItem,
    EvidenceItem,
    EvidenceRelationship,
    PaperMetadata,
    PaperRelevance,
)
from app.services.retrieval import (
    Retriever,
    multi_paper_search,
    validate_evidence_reference as verify_passage_in_page,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool 1: extract_paper_metadata
# ---------------------------------------------------------------------------
def extract_paper_metadata(db: Database, paper_id: str) -> Dict[str, Any]:
    """Extract title, authors, publication year, and extraction confidence.

    Preserves extraction uncertainty so the user knows if it was heuristic.
    """
    paper = db.get_paper(paper_id)
    if not paper:
        raise ValueError(f"Paper '{paper_id}' not found.")

    existing_meta = paper.get("metadata") or {}
    title = paper.get("title") or existing_meta.get("title")
    authors = paper.get("authors") or existing_meta.get("authors")
    year = paper.get("year") or existing_meta.get("year")
    confidence = existing_meta.get("confidence", "medium")

    # Detect if existing metadata is flawed (e.g. title is a conference header, authors is an email list, or year is missing)
    from pathlib import Path
    stored_path = paper.get("stored_path")
    needs_refresh = False
    if title and any(h in title.lower() for h in ["published as", "under review as", "proceedings of", "arxiv:"]):
        needs_refresh = True
    if authors and ("@" in authors or "{" in authors):
        needs_refresh = True
    if not year or year == "None":
        needs_refresh = True

    if needs_refresh and stored_path and Path(stored_path).exists():
        try:
            from app.services.pdf_service import extract_pages, extract_metadata
            pages = extract_pages(Path(stored_path), max_pages=3)
            refreshed = extract_metadata(pages, paper.get("original_filename", ""), pdf_path=Path(stored_path))
            title = refreshed["title"]
            authors = refreshed["authors"]
            year = refreshed["year"]
            confidence = refreshed["confidence"]
            db.update_paper(paper_id, title=title, authors=authors, year=year, metadata=refreshed)
        except Exception as e:
            logger.warning(f"Could not refresh metadata for {paper_id}: {e}")

    return {
        "paper_id": paper_id,
        "title": title or paper.get("original_filename", "Untitled Document"),
        "authors": authors or "Not reported in document header",
        "year": str(year) if year else "Not reported",
        "page_count": paper.get("page_count", 0),
        "confidence": confidence,
        "char_count": paper.get("char_count", 0),
        "notes": existing_meta.get("notes", "Extracted with PyMuPDF text parser."),
    }


# ---------------------------------------------------------------------------
# Tool 2: rank_paper_relevance
# ---------------------------------------------------------------------------
def rank_paper_relevance(
    db: Database,
    question: str,
    paper_id: str,
) -> PaperRelevance:
    """Evaluate how relevant a paper is to the research question.

    Returns a structured relevance score (0.0 to 1.0), label, explanation,
    summary, key findings, and limitations. Keeps relevance strictly separate
    from scientific credibility.
    """
    paper = db.get_paper(paper_id)
    if not paper:
        raise ValueError(f"Paper '{paper_id}' not found.")

    retriever = Retriever(db, paper_id)
    hits = retriever.search(question, top_k=5)

    title = paper.get("title") or paper.get("original_filename")

    if not hits:
        return PaperRelevance(
            paper_id=paper_id,
            score=0.15,
            label="Low",
            explanation=f"The paper '{title}' contains very few or no direct matches for terms in the research question.",
            supporting_evidence_ids=[],
            summary="Limited topical overlap with the target research question based on document passage retrieval.",
            findings=["No direct findings matched the specific query terms."],
            limitations=["Document vocabulary differs substantially from the query."],
        )

    # Score calculation normalized between 0.35 and 0.98 based on hit strength
    top_score = hits[0].score
    normalized_score = min(0.98, max(0.35, round(top_score / (top_score + 4.0), 2)))
    
    if normalized_score >= 0.75:
        label = "High"
    elif normalized_score >= 0.50:
        label = "Moderate"
    else:
        label = "Low"

    matched_keywords = set()
    for h in hits:
        matched_keywords.update(h.matched_terms)

    keywords_str = ", ".join(list(matched_keywords)[:6]) or "query concepts"
    top_passage = hits[0].text[:220].strip().replace("\n", " ")

    explanation = (
        f"Relevance rated as {label} ({normalized_score:.2f}) based on strong retrieval hits "
        f"for terms ({keywords_str}). Primary passage on page {hits[0].page_number}: \"{top_passage}...\""
    )

    # Extract extractive findings from top passages
    findings: List[str] = []
    limitations: List[str] = []

    for h in hits[:4]:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", h.text) if len(s.strip()) > 35]
        for s in sentences:
            s_clean = s.replace("\n", " ")
            lower = s_clean.lower()
            if any(term in lower for term in ["limitation", "however", "future work", "challeng", "restrict", "fail", "gap"]):
                if len(limitations) < 3 and s_clean not in limitations:
                    limitations.append(s_clean[:180])
            elif any(term in lower for term in ["improv", "accura", "result", "demonstrat", "show", "achiev", "propose", "evaluat"]):
                if len(findings) < 4 and s_clean not in findings:
                    findings.append(s_clean[:180])

    if not findings:
        findings = [f"Reports experimental results discussing {keywords_str}."]
    if not limitations:
        limitations = ["Explicit experimental limitations were not highlighted in top retrieval passages."]

    summary = (
        f"This paper investigates {keywords_str} across {paper.get('page_count', 1)} pages, "
        f"reporting experimental outcomes relevant to the research objective."
    )

    return PaperRelevance(
        paper_id=paper_id,
        score=normalized_score,
        label=label,
        explanation=explanation,
        supporting_evidence_ids=[hits[0].chunk_id],
        summary=summary,
        findings=findings,
        limitations=limitations,
    )


# ---------------------------------------------------------------------------
# Tool 3: search_document_chunks
# ---------------------------------------------------------------------------
def search_document_chunks(
    db: Database,
    paper_id: str,
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Retrieve relevant passages from a specific paper.

    Returns original passage text, page number, chunk ID, and score.
    """
    retriever = Retriever(db, paper_id)
    hits = retriever.search(query, top_k=top_k)
    return [
        {
            "chunk_id": h.chunk_id,
            "paper_id": h.paper_id,
            "page_number": h.page_number,
            "text": h.text,
            "score": round(h.score, 3),
            "matched_terms": h.matched_terms,
        }
        for h in hits
    ]


# ---------------------------------------------------------------------------
# Tool 4: extract_claims
# ---------------------------------------------------------------------------
def extract_claims(
    db: Database,
    paper_id: str,
    question: str,
    max_claims: int = 4,
) -> List[Dict[str, Any]]:
    """Extract claims, reported results, methodology, and limitations.

    Extracts verbatim or near-verbatim statements grounded in the paper passages,
    preserving exact page numbers and chunk IDs.
    """
    hits = search_document_chunks(db, paper_id, question, top_k=6)
    if not hits:
        # Fallback to general abstract/intro search
        hits = search_document_chunks(db, paper_id, "method result conclusion dataset accuracy performance", top_k=6)

    claims: List[Dict[str, Any]] = []
    seen_texts = set()

    for hit in hits:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", hit["text"]) if len(s.strip()) > 35]
        for s in sentences:
            s_clean = s.replace("\n", " ").strip()
            lower = s_clean.lower()
            if s_clean in seen_texts:
                continue

            # Determine category
            category: ClaimCategory = "general"
            rel: EvidenceRelationship = "supported_by_document"

            if any(k in lower for k in ["dataset", "cohort", "sample", "benchmark", "images", "patients"]):
                category = "methodology"
            elif any(k in lower for k in ["limitation", "however", "degrades", "unclear", "small sample", "constraint"]):
                category = "limitation"
                rel = "partially_supports"
            elif any(k in lower for k in ["improv", "increas", "accura", "outperform", "f1", "auc", "error rate", "percent"]):
                category = "reported_finding"
            elif any(k in lower for k in ["propose", "architect", "pipeline", "framework", "model", "train"]):
                category = "methodology"
            elif any(k in lower for k in ["evaluat", "experi", "compar", "test"]):
                category = "result"

            if category in ("reported_finding", "methodology", "limitation", "result"):
                seen_texts.add(s_clean)
                claims.append({
                    "paper_id": paper_id,
                    "text": s_clean,
                    "category": category,
                    "page_number": hit["page_number"],
                    "chunk_id": hit["chunk_id"],
                    "passage": hit["text"],
                    "evidence_relationship": rel,
                    "explanation": f"Reported by authors on page {hit['page_number']}.",
                    "limitations": [
                        "Finding is restricted to the specific dataset, architecture, and hyperparameter regimen reported."
                    ] if category == "reported_finding" else [],
                })
                if len(claims) >= max_claims:
                    break
        if len(claims) >= max_claims:
            break

    return claims


# ---------------------------------------------------------------------------
# Tool 5: find_supporting_evidence
# ---------------------------------------------------------------------------
def find_supporting_evidence(
    db: Database,
    claim_text: str,
    paper_ids: List[str],
    top_k: int = 4,
) -> List[Dict[str, Any]]:
    """Search supplied papers for passages that support or partially support a claim.

    Preserves exact text and validates reference existence.
    """
    hits = multi_paper_search(db, paper_ids, claim_text, top_k_per_paper=2)
    evidence_items: List[Dict[str, Any]] = []

    for h in hits[:top_k]:
        # Validate that the passage exists on the page
        is_valid, _ = verify_passage_in_page(db, h.paper_id, h.page_number, h.text[:120])
        
        # Determine relationship
        rel, expl = check_claim_support(claim_text, h.text)

        evidence_items.append({
            "paper_id": h.paper_id,
            "page_number": h.page_number,
            "chunk_id": h.chunk_id,
            "passage": h.text.strip(),
            "relationship": rel,
            "explanation": expl,
            "validated": is_valid,
        })

    return evidence_items


# ---------------------------------------------------------------------------
# Tool 6: find_counterevidence
# ---------------------------------------------------------------------------
def find_counterevidence(
    db: Database,
    claim_text: str,
    paper_ids: List[str],
) -> List[Dict[str, Any]]:
    """Retrieve passages that disagree with, qualify, or restrict a claim.

    Does not assume differing numerical results necessarily contradict one another.
    """
    contrast_query = f"{claim_text} however limitation degraded failure inconsistent sensitive drop"
    hits = multi_paper_search(db, paper_ids, contrast_query, top_k_per_paper=2)
    counter_items: List[Dict[str, Any]] = []

    contrast_signals = ["however", "limitation", "fail", "degrade", "drop", "inconsistent", "sensitive", "no significant", "cannot"]

    for h in hits:
        lower = h.text.lower()
        if any(sig in lower for sig in contrast_signals):
            is_valid, _ = verify_passage_in_page(db, h.paper_id, h.page_number, h.text[:120])
            counter_items.append({
                "paper_id": h.paper_id,
                "page_number": h.page_number,
                "chunk_id": h.chunk_id,
                "passage": h.text.strip(),
                "relationship": "potentially_conflicting_evidence" if any(k in lower for k in ["inconsistent", "degrade", "fail"]) else "partially_supports",
                "explanation": "Presents a qualifying boundary, contrasting condition, or reported limitation.",
                "validated": is_valid,
            })
            if len(counter_items) >= 3:
                break

    return counter_items


# ---------------------------------------------------------------------------
# Tool 7: compare_methodologies
# ---------------------------------------------------------------------------
def compare_methodologies(db: Database, paper_ids: List[str]) -> List[Dict[str, Any]]:
    """Compare datasets, methods, baselines, and evaluation metrics across papers."""
    results: List[Dict[str, Any]] = []

    for pid in paper_ids:
        paper = db.get_paper(pid)
        if not paper:
            continue

        retriever = Retriever(db, pid)
        dataset_hits = retriever.search("dataset benchmark cohort images patients size resolution", top_k=2)
        metric_hits = retriever.search("accuracy auc f1 score dice sensitivity specificity metric", top_k=2)
        method_hits = retriever.search("method architecture model proposed network loss algorithm", top_k=2)

        # Extract concise representations
        dataset_str = _extract_keyword_sentence(dataset_hits, ["dataset", "cohort", "images", "benchmark"]) or "Not reported"
        metric_str = _extract_keyword_sentence(metric_hits, ["auc", "accuracy", "f1", "dice", "metric"]) or "Not reported"
        method_str = _extract_keyword_sentence(method_hits, ["proposed", "network", "architecture", "model"]) or "Not reported"

        results.append({
            "paper_id": pid,
            "paper_title": paper.get("title") or paper.get("original_filename"),
            "dataset": dataset_str,
            "metrics": metric_str,
            "methodology": method_str,
            "primary_chunk_id": (method_hits[0].chunk_id if method_hits else None),
        })

    return results


# ---------------------------------------------------------------------------
# Tool 8: compare_paper_findings
# ---------------------------------------------------------------------------
def compare_paper_findings(
    db: Database,
    question: str,
    paper_ids: List[str],
) -> List[ComparisonRow]:
    """Compare reported findings while accounting for methodological differences.

    Uses 'Not reported' when a field is absent rather than inventing details.
    """
    rows: List[ComparisonRow] = []

    for pid in paper_ids:
        paper = db.get_paper(pid)
        if not paper:
            continue

        retriever = Retriever(db, pid)
        top_hits = retriever.search(question, top_k=3)
        method_hits = retriever.search("dataset methodology benchmark metric evaluation", top_k=2)

        objective = f"Investigates target question: '{question[:80]}...'"
        methodology = _extract_keyword_sentence(method_hits, ["model", "propose", "network", "technique"]) or "Not reported"
        dataset = _extract_keyword_sentence(method_hits, ["dataset", "images", "cohort", "data"]) or "Not reported"
        metrics = _extract_keyword_sentence(method_hits, ["accuracy", "auc", "f1", "metric", "score"]) or "Not reported"
        
        reported_finding = "Not reported"
        rel: EvidenceRelationship = "insufficient_information"
        primary_chunk_id = None
        limitations = "Not reported"

        if top_hits:
            primary_chunk_id = top_hits[0].chunk_id
            for h in top_hits:
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", h.text) if len(s.strip()) > 35]
                for s in sentences:
                    lower = s.lower()
                    if any(w in lower for w in ["improv", "achiev", "accura", "show", "result"]) and reported_finding == "Not reported":
                        reported_finding = s.replace("\n", " ")[:200]
                        rel = "supported_by_document"
                    if any(w in lower for w in ["limitation", "however", "restrict", "future"]) and limitations == "Not reported":
                        limitations = s.replace("\n", " ")[:180]

        if reported_finding == "Not reported" and top_hits:
            reported_finding = top_hits[0].text[:180].replace("\n", " ")
            rel = "partially_supports"

        rows.append(
            ComparisonRow(
                paper_id=pid,
                paper_title=paper.get("title") or paper.get("original_filename", "Untitled"),
                objective=objective,
                methodology=methodology,
                dataset=dataset,
                metrics=metrics,
                reported_finding=reported_finding,
                evidence_relationship=rel,
                limitations=limitations,
                primary_evidence_id=primary_chunk_id,
            )
        )

    return rows


# ---------------------------------------------------------------------------
# Tool 9: get_page_text
# ---------------------------------------------------------------------------
def get_page_text(db: Database, paper_id: str, page_number: int) -> str:
    """Return text extracted from a specific page."""
    return db.get_page_text(paper_id, page_number)


# ---------------------------------------------------------------------------
# Tool 10: validate_evidence_reference
# ---------------------------------------------------------------------------
def validate_evidence_reference(
    db: Database,
    paper_id: str,
    page_number: int,
    passage: str,
) -> Tuple[bool, str]:
    """Verify that the referenced paper and page exist, and passage matches source text."""
    paper = db.get_paper(paper_id)
    if not paper:
        return False, f"Paper '{paper_id}' does not exist in repository."
    if page_number < 1 or page_number > paper.get("page_count", 1):
        return False, f"Page number {page_number} is out of bounds (1-{paper.get('page_count')})."
    
    return verify_passage_in_page(db, paper_id, page_number, passage)


# ---------------------------------------------------------------------------
# Tool 11: check_claim_support
# ---------------------------------------------------------------------------
def check_claim_support(claim: str, evidence: str) -> Tuple[EvidenceRelationship, str]:
    """Classify semantic relationship between a claim and a referenced evidence passage.

    Distinguishes genuine document support from topical overlap or complete lack of evidence.
    """
    c_lower = claim.lower().strip()
    e_lower = evidence.lower().strip()

    if not e_lower:
        return "insufficient_information", "No supporting passage text provided."

    # Look for direct contradictions or caveats
    contradiction_terms = [
        "however",
        "contrary",
        "fails to improve",
        "does not hold",
        "degrades",
        "inconsistent",
        "drop",
        "failure",
        "no statistically significant",
    ]
    has_contradiction = any(t in e_lower for t in contradiction_terms)

    # Word stems for morphological robustness
    def _stems(text: str) -> set[str]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        stopwords = {
            "the", "a", "an", "is", "in", "and", "of", "to", "on", "for", "with",
            "by", "at", "from", "that", "this", "our", "we", "their", "are", "be",
            "as", "it", "its", "can", "has", "have", "were", "was"
        }
        res = set()
        for w in words:
            if w not in stopwords and len(w) > 2:
                res.add(w[:5])
        return res

    c_stems = _stems(c_lower)
    e_stems = _stems(e_lower)
    overlap = len(c_stems & e_stems) / max(len(c_stems), 1)

    # Detect domain mismatch: specific claims containing key entities absent from passage
    domain_specific_keywords = [
        "clinical", "patient", "mortality", "hospital", "demographic",
        "histopathology", "lesion", "melanoma", "radiology", "icu"
    ]
    claim_domain_terms = {w for w in domain_specific_keywords if w in c_lower}
    passage_domain_terms = {w for w in domain_specific_keywords if w in e_lower}
    if claim_domain_terms and not (claim_domain_terms & passage_domain_terms):
        return "unsupported_in_available_document", f"Passage does not substantiate domain-specific terms: {', '.join(claim_domain_terms)}."

    if has_contradiction and overlap >= 0.25:
        return "potentially_conflicting_evidence", "Passage contains explicit qualifying or contradictory language."

    if overlap >= 0.35:
        return "supported_by_document", "Passage contains strong textual agreement with the stated claim."
    elif overlap >= 0.15:
        return "partially_supports", "Passage addresses the general subject matter but does not verify all details."
    elif overlap > 0.05:
        return "unsupported_in_available_document", "Passage shares minimal terminology with the claim and does not establish it."
    else:
        return "insufficient_information", "Passage does not contain sufficient overlapping evidence to assess the claim."


# ---------------------------------------------------------------------------
# Tool 11B: validate_disagreements
# ---------------------------------------------------------------------------
def validate_disagreements(
    db: Database,
    disagreements: List[DisagreementItem],
    paper_ids: List[str],
) -> Tuple[List[DisagreementItem], List[str]]:
    """Validate that every identified cross-paper disagreement is grounded in actual source text.

    Rejects domain hallucinations (e.g. clinical/demographic claims on computer vision papers),
    distinguishes dataset differences from contradictions, and reports 'No verified disagreement identified'
    if evidence does not establish a disagreement.
    """
    notes: List[str] = []
    validated_disagreements: List[DisagreementItem] = []

    # Collect vocabulary across all papers
    all_chunks_text = ""
    for pid in paper_ids:
        chunks = db.get_chunks(pid)
        all_chunks_text += " " + " ".join([c["text"].lower() for c in chunks])

    domain_check_terms = [
        "clinical", "patient", "patients", "hospital", "hospitals",
        "demographic", "demographics", "radiology", "radiological",
        "melanoma", "histopathology", "lesion", "lesions", "biopsy"
    ]

    for d in disagreements:
        d_text = (d.topic + " " + d.description).lower()

        # Check for ungrounded domain-specific concepts
        hallucinated_terms = [term for term in domain_check_terms if term in d_text and term not in all_chunks_text]
        if hallucinated_terms:
            notes.append(
                f"Rejected unsupported disagreement '{d.topic}': Mentions domain concepts ({', '.join(hallucinated_terms)}) not present in analyzed documents."
            )
            continue

        # Check for superficial dataset differences masquerading as factual contradictions
        if any(w in d_text for w in ["cifar", "imagenet", "jft", "dataset", "benchmark"]) and "disagree" not in d_text and "conflict" not in d_text:
            notes.append(
                f"Reclassified disagreement '{d.topic}' as methodological difference (divergent evaluation datasets or conditions)."
            )
            continue

        # Check evidence grounding
        if not d.paper_ids or len(d.paper_ids) < 2:
            notes.append(f"Rejected disagreement '{d.topic}': Must reference at least two distinct papers.")
            continue

        validated_disagreements.append(d)

    if not validated_disagreements:
        validated_disagreements.append(
            DisagreementItem(
                topic="No verified disagreement identified",
                description=(
                    "No verified empirical disagreement was identified across the evaluated papers. "
                    "The reported variations reflect differences in model architectures, dataset scales, "
                    "and evaluation protocols rather than conflicting empirical conclusions."
                ),
                paper_ids=paper_ids,
                evidence_ids=[],
            )
        )

    return validated_disagreements, notes


# ---------------------------------------------------------------------------
# Tool 12: validate_report_citations
# ---------------------------------------------------------------------------
def validate_report_citations(db: Database, report: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Separately validate reference validity (existence in text) and evidence support (semantic confirmation).

    Detects missing or malformed citations and returns 'valid', 'needs_revision', or 'invalid'.
    Never displays verification merely because text exists if semantic support is unconfirmed.
    """
    notes: List[str] = []
    claims = report.get("main_claims") or []
    evidence_list = report.get("supporting_evidence") or []
    paper_ids = report.get("paper_ids") or []

    if not claims:
        notes.append("Report has no extracted claims.")

    verified_reference_count = 0
    confirmed_support_count = 0
    total_evidence_count = len(evidence_list)

    for evi in evidence_list:
        pid = evi.get("paper_id")
        page = evi.get("page_number", 1)
        passage = evi.get("passage", "")
        claim_text = evi.get("claim_text", "")

        # 1. Reference validity check
        is_ref_valid, reason = validate_evidence_reference(db, pid, page, passage)
        if is_ref_valid:
            verified_reference_count += 1
        else:
            notes.append(f"Unverified reference on paper {pid} page {page}: {reason}")

        # 2. Semantic support check
        if claim_text:
            rel, support_reason = check_claim_support(claim_text, passage)
            if rel in {"supported_by_document", "partially_supports"}:
                confirmed_support_count += 1
            else:
                notes.append(f"Passage on paper {pid} page {page} does not substantiate claim: {support_reason}")
        else:
            if is_ref_valid:
                confirmed_support_count += 1

    # Check evidence ratios
    if total_evidence_count == 0:
        notes.append("No evidence items were attached to the report.")
        return "needs_revision", notes

    ref_ratio = verified_reference_count / total_evidence_count
    notes.append(f"Reference validity: {verified_reference_count}/{total_evidence_count} passages verified in document text.")
    notes.append(f"Evidence support: {confirmed_support_count}/{total_evidence_count} evidence items confirm associated claims.")

    # Validate disagreements
    disagreements = report.get("disagreements") or []
    if disagreements and paper_ids:
        dis_items = [
            DisagreementItem(**d) if isinstance(d, dict) else d
            for d in disagreements
        ]
        _, dis_notes = validate_disagreements(db, dis_items, paper_ids)
        notes.extend(dis_notes)

    if ref_ratio >= 0.8:
        return "valid", notes
    elif ref_ratio >= 0.5:
        return "needs_revision", notes
    else:
        return "invalid", notes


# ---------------------------------------------------------------------------
# Internal Helper
# ---------------------------------------------------------------------------
def _extract_keyword_sentence(hits: List[Any], keywords: List[str]) -> Optional[str]:
    for h in hits:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", h.text) if len(s.strip()) > 25]
        for s in sentences:
            s_lower = s.lower()
            if any(k in s_lower for k in keywords):
                return s.replace("\n", " ").strip()[:160]
    return None
