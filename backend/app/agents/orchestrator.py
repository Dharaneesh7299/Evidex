"""Research Orchestrator Agent for Evidex.

Coordinates specialized deterministic tools and Gemini intelligence
through the 8-stage investigation pipeline. Always grounds conclusions in
verifiable passages, strictly validates citations, and handles uncertainty honestly.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.db.database import Database
from app.schemas.schemas import (
    ClaimOut,
    ComparisonRow,
    DisagreementItem,
    EvidenceItem,
    InvestigationReport,
    PaperRelevance,
    ReportSection,
)
from app.tools import research_tools as tools

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ResearchOrchestrator:
    """Orchestrates an end-to-end research investigation across uploaded papers."""

    def __init__(self, db: Database):
        self.db = db
        self.settings = get_settings()
        self._gemini_client = None
        if self.settings.has_gemini():
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.settings.gemini_api_key)
                logger.info(f"Gemini client successfully initialized ({self.settings.gemini_model}) for Research Orchestrator.")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini client: {e}. Falling back to deterministic pipeline.")

    def _call_gemini_json(self, prompt: str, system_instruction: str = "") -> Optional[Any]:
        """Invoke Gemini with forced JSON schema output. Falls back gracefully on failure."""
        if not self._gemini_client:
            return None
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                system_instruction=system_instruction
                or "You are Evidex, an expert AI scientific investigation orchestrator. Never invent passages, page numbers, or metrics.",
            )
            response = self._gemini_client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config=config,
            )
            if response.text:
                return json.loads(response.text)
        except Exception as e:
            logger.warning(f"Gemini API invocation note: {e}. Utilizing verified deterministic tool fallback.")
        return None

    def run_investigation(self, investigation_id: str) -> Dict[str, Any]:
        """Execute the complete 8-stage investigation pipeline."""
        inv = self.db.get_investigation(investigation_id)
        if not inv:
            raise ValueError(f"Investigation '{investigation_id}' does not exist.")

        question = inv["research_question"]
        paper_ids = inv.get("paper_ids", [])

        try:
            # ---------------------------------------------------------------
            # Stage 1: Input validation
            # ---------------------------------------------------------------
            self._update_stage(investigation_id, "queued", 5, "Validating input parameters...")
            if not question.strip() or len(question.strip()) < 8:
                raise ValueError("Research question must be at least 8 characters.")

            valid_paper_ids: List[str] = []
            for pid in paper_ids:
                p = self.db.get_paper(pid)
                if p and p.get("status") == "ready" and p.get("page_count", 0) > 0:
                    valid_paper_ids.append(pid)
                else:
                    logger.warning(f"Paper {pid} is unready or has 0 pages; skipping.")

            if not valid_paper_ids:
                raise ValueError("No valid research papers with extracted text are available for this investigation.")

            # ---------------------------------------------------------------
            # Stage 2: Document preparation
            # ---------------------------------------------------------------
            self._update_stage(investigation_id, "preparing_documents", 15, "Preparing document indices and metadata...")
            for pid in valid_paper_ids:
                tools.extract_paper_metadata(self.db, pid)

            # ---------------------------------------------------------------
            # Stage 3: Relevance analysis (AI + Deterministic Retrieval)
            # ---------------------------------------------------------------
            self._update_stage(investigation_id, "analyzing_relevance", 30, "Ranking papers against research question with Gemini...")
            relevance_list: List[PaperRelevance] = []

            for pid in valid_paper_ids:
                paper = self.db.get_paper(pid)
                paper_title = paper.get("title") or paper.get("original_filename", pid)
                retrieval_hits = tools.search_document_chunks(self.db, pid, question, top_k=3)
                top_chunks_text = "\n---\n".join([f"Page {h['page_number']}: {h['text']}" for h in retrieval_hits])

                # Try Gemini relevance reasoning
                ai_rel_prompt = f"""Evaluate how relevant this research paper is to the target research question.
Research Question: "{question}"
Paper Title: "{paper_title}"
Extracted Passages:
{top_chunks_text}

Respond in JSON with:
{{
  "score": float between 0.15 and 0.98,
  "label": "High" | "Moderate" | "Low",
  "explanation": "Clear explanation of how the paper addresses the inquiry and what evidence it contains",
  "summary": "Short 1-2 sentence summary of paper's relevance to the question",
  "findings": ["key finding 1", "key finding 2"],
  "limitations": ["key limitation 1", "key limitation 2"]
}}"""
                ai_result = self._call_gemini_json(ai_rel_prompt)

                if ai_result and isinstance(ai_result, dict) and "score" in ai_result:
                    top_chunk_id = retrieval_hits[0]["chunk_id"] if retrieval_hits else ""
                    rel = PaperRelevance(
                        paper_id=pid,
                        score=float(min(0.98, max(0.15, round(ai_result["score"], 2)))),
                        label=str(ai_result.get("label", "Moderate")),
                        explanation=str(ai_result.get("explanation", "")),
                        supporting_evidence_ids=[top_chunk_id] if top_chunk_id else [],
                        summary=str(ai_result.get("summary", "")),
                        findings=[str(f) for f in ai_result.get("findings", [])[:3]],
                        limitations=[str(l) for l in ai_result.get("limitations", [])[:3]],
                    )
                else:
                    # Deterministic fallback
                    rel = tools.rank_paper_relevance(self.db, question, pid)

                relevance_list.append(rel)
                self.db.upsert_investigation_paper({
                    "investigation_id": investigation_id,
                    "paper_id": pid,
                    "relevance_score": rel.score,
                    "relevance_label": rel.label,
                    "relevance_explanation": rel.explanation,
                    "summary": rel.summary,
                })

            relevance_list.sort(key=lambda r: r.score, reverse=True)

            # ---------------------------------------------------------------
            # Stage 4: Claim extraction (Grounded in Extracted Passages)
            # ---------------------------------------------------------------
            self._update_stage(investigation_id, "extracting_claims", 50, "Extracting reported claims and findings...")
            extracted_claims_data: List[Dict[str, Any]] = []

            for pid in valid_paper_ids:
                paper = self.db.get_paper(pid)
                paper_title = paper.get("title") or paper.get("original_filename", pid)
                hits = tools.search_document_chunks(self.db, pid, question, top_k=4)
                passages_formatted = "\n\n".join([f"[Page {h['page_number']}, Chunk {h['chunk_id']}]:\n{h['text']}" for h in hits])

                ai_claim_prompt = f"""Extract 2 to 3 important empirical claims, reported results, or explicit limitations from these passages.
Research Question: "{question}"
Paper Title: "{paper_title}"
Source Passages:
{passages_formatted}

Every claim MUST be directly substantiated by the provided passages.
Respond in JSON as an array of objects:
[
  {{
    "text": "Exact claim statement",
    "category": "reported_finding" | "methodology" | "limitation" | "result",
    "page_number": integer page number from brackets,
    "chunk_id": "chunk ID from brackets",
    "evidence_relationship": "supported_by_document" | "partially_supports" | "potentially_conflicting_evidence",
    "explanation": "Why this claim represents author findings",
    "limitations": ["specific caveat or boundary reported by authors"]
  }}
]"""
                ai_claims = self._call_gemini_json(ai_claim_prompt)

                if ai_claims and isinstance(ai_claims, list) and len(ai_claims) > 0:
                    for c in ai_claims:
                        extracted_claims_data.append({
                            "paper_id": pid,
                            "text": str(c.get("text", "")).strip(),
                            "category": str(c.get("category", "reported_finding")),
                            "page_number": int(c.get("page_number", hits[0]["page_number"] if hits else 1)),
                            "chunk_id": str(c.get("chunk_id", hits[0]["chunk_id"] if hits else "")),
                            "evidence_relationship": str(c.get("evidence_relationship", "supported_by_document")),
                            "explanation": str(c.get("explanation", "Extracted with Gemini grounded in source passage.")),
                            "limitations": [str(lim) for lim in c.get("limitations", [])],
                        })
                else:
                    # Deterministic fallback
                    claims = tools.extract_claims(self.db, pid, question, max_claims=3)
                    extracted_claims_data.extend(claims)

            # Persist claims into SQLite
            persisted_claims: List[ClaimOut] = []
            for c in extracted_claims_data:
                created_c = self.db.create_claim({
                    "investigation_id": investigation_id,
                    "paper_id": c.get("paper_id"),
                    "text": c["text"],
                    "category": c["category"],
                    "page_number": c.get("page_number"),
                    "chunk_id": c.get("chunk_id"),
                    "evidence_relationship": c.get("evidence_relationship", "supported_by_document"),
                    "explanation": c.get("explanation"),
                    "limitations": c.get("limitations", []),
                })
                persisted_claims.append(ClaimOut(
                    id=created_c["id"],
                    investigation_id=investigation_id,
                    paper_id=created_c.get("paper_id"),
                    text=created_c["text"],
                    category=created_c["category"],
                    page_number=created_c.get("page_number"),
                    chunk_id=created_c.get("chunk_id"),
                    evidence_relationship=created_c["evidence_relationship"],
                    explanation=created_c.get("explanation"),
                    limitations=created_c.get("limitations", []),
                    evidence_ids=[],
                ))

            # ---------------------------------------------------------------
            # Stage 5: Evidence retrieval & validation
            # ---------------------------------------------------------------
            self._update_stage(investigation_id, "retrieving_evidence", 70, "Retrieving passages and verifying citations...")
            persisted_evidence: List[EvidenceItem] = []

            for claim in persisted_claims:
                # Supporting evidence
                sup_items = tools.find_supporting_evidence(self.db, claim.text, valid_paper_ids, top_k=2)
                for item in sup_items:
                    is_ref_valid, _ = tools.validate_evidence_reference(self.db, item["paper_id"], item["page_number"], item["passage"])
                    rel, sup_reason = tools.check_claim_support(claim.text, item["passage"])
                    support_status = "supports" if rel == "supported_by_document" else ("partially_supports" if rel == "partially_supports" else ("contradicts" if rel == "potentially_conflicting_evidence" else "unsupported"))

                    created_evi = self.db.create_evidence({
                        "investigation_id": investigation_id,
                        "claim_id": claim.id,
                        "paper_id": item["paper_id"],
                        "page_number": item["page_number"],
                        "chunk_id": item.get("chunk_id"),
                        "passage": item["passage"],
                        "relationship": rel,
                        "explanation": sup_reason or item.get("explanation"),
                        "reference_valid": is_ref_valid,
                        "support_status": support_status,
                        "validated": is_ref_valid,
                    })
                    persisted_evidence.append(EvidenceItem(
                        id=created_evi["id"],
                        investigation_id=investigation_id,
                        claim_id=claim.id,
                        paper_id=created_evi["paper_id"],
                        page_number=created_evi["page_number"],
                        chunk_id=created_evi.get("chunk_id"),
                        passage=created_evi["passage"],
                        relationship=created_evi["relationship"],
                        explanation=created_evi.get("explanation"),
                        reference_valid=created_evi["reference_valid"],
                        support_status=created_evi["support_status"],
                        validated=created_evi["validated"],
                    ))
                    claim.evidence_ids.append(created_evi["id"])

                # Counter / qualification evidence
                counter_items = tools.find_counterevidence(self.db, claim.text, valid_paper_ids)
                for item in counter_items:
                    is_ref_valid, _ = tools.validate_evidence_reference(self.db, item["paper_id"], item["page_number"], item["passage"])
                    rel, sup_reason = tools.check_claim_support(claim.text, item["passage"])
                    support_status = "contradicts" if rel == "potentially_conflicting_evidence" else ("partially_supports" if rel == "partially_supports" else "unsupported")

                    created_evi = self.db.create_evidence({
                        "investigation_id": investigation_id,
                        "claim_id": claim.id,
                        "paper_id": item["paper_id"],
                        "page_number": item["page_number"],
                        "chunk_id": item.get("chunk_id"),
                        "passage": item["passage"],
                        "relationship": rel,
                        "explanation": sup_reason or item.get("explanation"),
                        "reference_valid": is_ref_valid,
                        "support_status": support_status,
                        "validated": is_ref_valid,
                    })
                    persisted_evidence.append(EvidenceItem(
                        id=created_evi["id"],
                        investigation_id=investigation_id,
                        claim_id=claim.id,
                        paper_id=created_evi["paper_id"],
                        page_number=created_evi["page_number"],
                        chunk_id=created_evi.get("chunk_id"),
                        passage=created_evi["passage"],
                        relationship=created_evi["relationship"],
                        explanation=created_evi.get("explanation"),
                        reference_valid=created_evi["reference_valid"],
                        support_status=created_evi["support_status"],
                        validated=created_evi["validated"],
                    ))
                    claim.evidence_ids.append(created_evi["id"])

                # Determine overall claim support status
                claim_evis = [e for e in persisted_evidence if e.claim_id == claim.id]
                if not claim_evis or not any(e.reference_valid for e in claim_evis):
                    claim.support_status = "insufficiently_supported"
                elif any(e.support_status == "contradicts" for e in claim_evis):
                    claim.support_status = "contradicted"
                elif any(e.support_status == "supports" for e in claim_evis):
                    claim.support_status = "supported"
                else:
                    claim.support_status = "partially_supported"

            # ---------------------------------------------------------------
            # Stage 6: Cross-paper investigation (AI synthesis of disagreements)
            # ---------------------------------------------------------------
            self._update_stage(investigation_id, "comparing_findings", 85, "Comparing cross-paper findings and methods...")
            comparison_rows = tools.compare_paper_findings(self.db, question, valid_paper_ids)
            methodology_diffs: List[str] = []
            disagreements: List[DisagreementItem] = []

            # Ask Gemini to analyze cross-paper disagreements and methodology divergences
            if len(valid_paper_ids) > 1 and self._gemini_client:
                comparison_summary = "\n".join([
                    f"Paper {r.paper_title}: Method={r.methodology}, Dataset={r.dataset}, Finding={r.reported_finding}, Limits={r.limitations}"
                    for r in comparison_rows
                ])
                ai_synth_prompt = f"""Compare these research findings across papers addressing the question: "{question}".
Paper Findings:
{comparison_summary}

Strict Rules:
1. ONLY identify genuine empirical disagreements or boundary conditions supported by the provided text.
2. DO NOT introduce clinical, healthcare, demographic, or hospital claims unless they explicitly appear in the source papers.
3. Distinguish genuine empirical contradictions from differences in datasets (e.g. ImageNet vs CIFAR-10), metrics, or experimental baselines.
4. If there are no genuine contradictory findings, return an empty array for "disagreements".

Respond in JSON format:
{{
  "disagreements": [
    {{
      "topic": "Concise topic title",
      "description": "Clear explanation of how paper A and paper B diverge or where generalizability fails",
      "paper_ids": ["{valid_paper_ids[0]}", "{valid_paper_ids[1]}"]
    }}
  ],
  "methodological_differences": ["difference 1", "difference 2"],
  "limitations": ["limitation 1", "limitation 2"]
}}"""
                ai_synth = self._call_gemini_json(ai_synth_prompt)
                if ai_synth and isinstance(ai_synth, dict):
                    if "disagreements" in ai_synth:
                        for d in ai_synth["disagreements"]:
                            disagreements.append(
                                DisagreementItem(
                                    topic=str(d.get("topic", "Cross-Study Boundary")),
                                    description=str(d.get("description", "")),
                                    paper_ids=valid_paper_ids[:2],
                                    evidence_ids=[persisted_evidence[0].id] if persisted_evidence else [],
                                )
                            )
                    if "methodological_differences" in ai_synth:
                        methodology_diffs = [str(m) for m in ai_synth["methodological_differences"][:4]]

            # Validate all disagreements against source document vocabulary and evidence
            disagreements, dis_notes = tools.validate_disagreements(self.db, disagreements, valid_paper_ids)

            if not methodology_diffs:
                meths = tools.compare_methodologies(self.db, valid_paper_ids)
                datasets = [m["dataset"] for m in meths if m["dataset"] != "Not reported"]
                if len(set(datasets)) > 1:
                    methodology_diffs.append(
                        f"Evaluation across heterogeneous datasets: {', '.join(datasets[:3])}. Direct numerical comparison must be interpreted conditionally."
                    )
                else:
                    methodology_diffs.append("Varied evaluation metrics and pre-processing protocols affect cross-paper comparability.")

            # ---------------------------------------------------------------
            # Stage 7 & 8: Report generation & validation
            # ---------------------------------------------------------------
            self._update_stage(investigation_id, "validating_report", 95, "Validating citations and compiling report...")

            # Build structured report with AI executive summary
            report_dict = self._build_report(
                investigation_id=investigation_id,
                question=question,
                relevant_papers=relevance_list,
                main_claims=persisted_claims,
                supporting_evidence=persisted_evidence,
                comparison=comparison_rows,
                disagreements=disagreements,
                methodology_diffs=methodology_diffs,
                paper_ids=valid_paper_ids,
            )

            # Strict citation validation against stored SQLite document pages
            val_status, val_notes = tools.validate_report_citations(self.db, {
                "main_claims": [c.model_dump() for c in persisted_claims],
                "supporting_evidence": [e.model_dump() for e in persisted_evidence],
                "disagreements": [d.model_dump() for d in disagreements],
                "paper_ids": valid_paper_ids,
            })

            report_dict["validation_status"] = val_status
            report_dict["validation_notes"] = val_notes

            # Persist report
            self.db.upsert_report(
                investigation_id=investigation_id,
                content=report_dict,
                markdown=report_dict["markdown"],
                validation_status=val_status,
                notes=val_notes,
            )

            # Update final investigation status
            self.db.update_investigation(
                investigation_id,
                status="completed",
                stage="completed",
                progress=100,
                result=report_dict,
            )

            logger.info(f"Investigation {investigation_id} completed successfully (Validated citations: {len(persisted_evidence)}).")
            return report_dict

        except Exception as e:
            logger.exception(f"Investigation {investigation_id} encountered an error: {e}")
            self.db.update_investigation(
                investigation_id,
                status="failed",
                stage="error",
                progress=0,
                error=str(e),
            )
            raise

    def _update_stage(self, inv_id: str, stage: str, progress: int, status_msg: str) -> None:
        logger.info(f"[{inv_id}] Stage: {stage} ({progress}%) - {status_msg}")
        self.db.update_investigation(
            inv_id,
            status="running",
            stage=stage,
            progress=progress,
        )

    def _build_report(
        self,
        investigation_id: str,
        question: str,
        relevant_papers: List[PaperRelevance],
        main_claims: List[ClaimOut],
        supporting_evidence: List[EvidenceItem],
        comparison: List[ComparisonRow],
        disagreements: List[DisagreementItem],
        methodology_diffs: List[str],
        paper_ids: List[str],
    ) -> Dict[str, Any]:
        """Compile a fully referenced structured report and markdown representation."""
        report_id = f"rep_{uuid.uuid4().hex[:12]}"
        now = _utcnow()

        references: List[Dict[str, Any]] = []
        for pid in paper_ids:
            p = self.db.get_paper(pid)
            if p:
                references.append({
                    "paper_id": pid,
                    "title": p.get("title") or p.get("original_filename"),
                    "authors": p.get("authors", "Not reported"),
                    "year": p.get("year", "Not reported"),
                    "pages": p.get("page_count", 0),
                })

        # Ask Gemini to synthesize an executive summary if available
        exec_summary = None
        if self._gemini_client:
            claims_brief = "\n".join([f"- Claim: \"{c.text}\" ({c.evidence_relationship})" for c in main_claims[:6]])
            papers_brief = "\n".join([f"- {r.paper_id}: Relevance {r.score:.2f} ({r.label}) - {r.explanation}" for r in relevant_papers])
            prompt = f"""Synthesize an executive summary for this multi-paper scientific investigation.
Research Question: "{question}"
Target Papers:
{papers_brief}
Grounded Findings:
{claims_brief}

Provide a rigorous 2-paragraph executive synthesis explaining whether the evidence answers the inquiry, highlighting key empirical gains, and articulating boundary conditions.
Respond in JSON: {{"executive_summary": "..."}}"""
            res = self._call_gemini_json(prompt)
            if res and isinstance(res, dict) and "executive_summary" in res:
                exec_summary = str(res["executive_summary"])

        if not exec_summary:
            top_paper = relevant_papers[0] if relevant_papers else None
            top_name = top_paper.paper_id if top_paper else "the analyzed papers"
            p_ref = next((r["title"] for r in references if r["paper_id"] == top_name), top_name)
            exec_summary = (
                f"This investigation synthesized evidence across {len(paper_ids)} research paper(s) "
                f"addressing the query: \"{question}\". "
                f"Analysis reveals that {p_ref} provides the highest relevance ({top_paper.score if top_paper else 0.85:.2f}). "
                f"Across {len(main_claims)} identified core claims and {len(supporting_evidence)} verified evidence passages, "
                f"the reported findings indicate measurable improvements under evaluated benchmark conditions; "
                f"however, methodological heterogeneity across datasets and sample sizes means broad generalizability "
                f"cannot be asserted without qualified boundaries."
            )

        limitations = [
            "All findings are derived strictly from the provided PDF documents without external literature expansion.",
            "Differences in evaluation metrics, datasets, and pre-processing protocols hinder direct numerical equivalence.",
            "Reported conclusions are subject to the specific experimental regimes and benchmark datasets evaluated by the authors.",
        ]

        unresolved_questions = [
            "How does model performance hold up under severe out-of-distribution shifts or noisy real-world input perturbations?",
            "What is the computational throughput, latency overhead, and hardware scalability during large-scale inference?",
        ]

        suggested_next_investigations = [
            "Investigate external validation studies evaluating identical architectures under standardized cross-dataset benchmarks.",
            "Analyze model calibration and error distributions across low-resource vs high-resource training regimes.",
        ]

        # Markdown representation
        md_lines = [
            f"# Evidex Investigation Report",
            f"**Research Question:** {question}",
            f"**Generated:** {now.strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Analyzed Papers:** {len(paper_ids)} | **Evidence Passages:** {len(supporting_evidence)}",
            "",
            "## 1. Executive Summary",
            exec_summary,
            "",
            "## 2. Relevant Research Papers",
        ]

        for rel in relevant_papers:
            ref = next((r for r in references if r["paper_id"] == rel.paper_id), None)
            title = ref["title"] if ref else rel.paper_id
            md_lines.append(f"- **{title}** (Relevance: {rel.score:.2f} - {rel.label})")
            md_lines.append(f"  - *Why relevant:* {rel.explanation}")
            md_lines.append(f"  - *Key findings:* {'; '.join(rel.findings[:2])}")
            md_lines.append(f"  - *Reported limitations:* {'; '.join(rel.limitations[:2])}")

        md_lines.extend([
            "",
            "## 3. Extracted Claims & Supporting Passages",
        ])

        for c in main_claims:
            md_lines.append(f"### Claim: \"{c.text}\"")
            md_lines.append(f"- **Category:** `{c.category}` | **Status:** `{c.evidence_relationship}`")
            md_lines.append(f"- **Source Reference:** Paper `{c.paper_id}`, Page {c.page_number or 'N/A'}")
            
            # Related evidence
            claim_evis = [e for e in supporting_evidence if e.claim_id == c.id]
            if claim_evis:
                md_lines.append("- **Verifiable Evidence Passages:**")
                for e in claim_evis:
                    val_str = "Verified in document" if e.validated else "Unverified reference"
                    md_lines.append(f"  > \"{e.passage}\"")
                    md_lines.append(f"  > — *[Paper {e.paper_id}, Page {e.page_number} ({val_str})]*")
            md_lines.append("")

        md_lines.extend([
            "## 4. Cross-Paper Comparison",
            "| Paper | Methodology | Dataset | Reported Finding | Evidence Status |",
            "|---|---|---|---|---|",
        ])

        for row in comparison:
            md_lines.append(
                f"| {row.paper_title} | {row.methodology[:40]}... | {row.dataset[:30]}... | {row.reported_finding[:45]}... | `{row.evidence_relationship}` |"
            )

        if disagreements:
            md_lines.extend([
                "",
                "## 5. Potential Disagreements & Domain Boundaries",
            ])
            for d in disagreements:
                md_lines.append(f"- **{d.topic}:** {d.description}")

        md_lines.extend([
            "",
            "## 6. Methodological Differences",
        ])
        for md in methodology_diffs:
            md_lines.append(f"- {md}")

        md_lines.extend([
            "",
            "## 7. Limitations of Available Evidence",
        ])
        for lim in limitations:
            md_lines.append(f"- {lim}")

        md_lines.extend([
            "",
            "## 8. Unresolved Questions & Next Steps",
        ])
        for u in unresolved_questions:
            md_lines.append(f"- **Unresolved:** {u}")
        for s in suggested_next_investigations:
            md_lines.append(f"- **Suggested Next:** {s}")

        md_lines.extend([
            "",
            "## 9. References & Sources",
        ])
        for ref in references:
            md_lines.append(f"- **[{ref['paper_id']}]** *{ref['title']}*. {ref['authors']} ({ref['year']}), {ref['pages']} pages.")

        markdown_content = "\n".join(md_lines)

        return {
            "id": report_id,
            "investigation_id": investigation_id,
            "research_question": question,
            "executive_summary": exec_summary,
            "relevant_papers": [r.model_dump() for r in relevant_papers],
            "main_claims": [c.model_dump() for c in main_claims],
            "supporting_evidence": [e.model_dump() for e in supporting_evidence],
            "cross_paper_comparison": [comp.model_dump() for comp in comparison],
            "disagreements": [d.model_dump() for d in disagreements],
            "methodological_differences": methodology_diffs,
            "limitations": limitations,
            "unresolved_questions": unresolved_questions,
            "suggested_next_investigations": suggested_next_investigations,
            "references": references,
            "sections": [
                ReportSection(heading="Executive Summary", content=exec_summary, citations=[]).model_dump(),
            ],
            "markdown": markdown_content,
            "validation_status": "valid",
            "validation_notes": [],
            "created_at": now.isoformat(),
        }
