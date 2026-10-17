"""Pydantic schemas exposed by the API.

These mirror the database rows and the agent's structured outputs. The
agent is asked to return JSON that conforms to the ``AgentInvestigation``
schema; deterministic services also produce these shapes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ----- evidence relationships -----
EvidenceRelationship = Literal[
    "supported_by_document",
    "partially_supports",
    "unsupported_in_available_document",
    "potentially_conflicting_evidence",
    "insufficient_information",
    "not_directly_comparable",
]


ClaimCategory = Literal[
    "reported_finding",
    "methodology",
    "limitation",
    "result",
    "background",
    "general",
]


# ----- papers -----
class PaperMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[str] = None
    page_count: Optional[int] = None
    confidence: Optional[str] = None
    notes: Optional[str] = None


class PaperOut(BaseModel):
    id: str
    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[str] = None
    original_filename: str
    file_size: int
    page_count: int
    char_count: int
    status: str
    error: Optional[str] = None
    metadata: Optional[PaperMetadata] = None
    created_at: datetime
    updated_at: datetime


class PaperChunk(BaseModel):
    id: str
    paper_id: str
    page_number: int
    chunk_index: int
    text: str
    token_count: int


class PaperUploadResponse(BaseModel):
    paper: PaperOut
    chunks: int


# ----- investigations -----
class InvestigationCreateRequest(BaseModel):
    research_question: str = Field(min_length=8, max_length=2000)
    paper_ids: List[str] = Field(min_length=1, max_length=10)

    @field_validator("research_question")
    @classmethod
    def _trim(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 8:
            raise ValueError("Research question must be at least 8 characters after trimming.")
        return v

    @field_validator("paper_ids")
    @classmethod
    def _unique(cls, v: List[str]) -> List[str]:
        if len(set(v)) != len(v):
            raise ValueError("paper_ids must be unique.")
        return v


class PaperRelevance(BaseModel):
    paper_id: str
    score: float = Field(ge=0.0, le=1.0)
    label: str
    explanation: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    findings: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    id: str
    investigation_id: str
    claim_id: Optional[str] = None
    paper_id: str
    page_number: int
    chunk_id: Optional[str] = None
    passage: str
    relationship: EvidenceRelationship
    explanation: Optional[str] = None
    reference_valid: bool = False
    support_status: str = "supports"
    validated: bool = False


class ClaimOut(BaseModel):
    id: str
    investigation_id: str
    paper_id: Optional[str] = None
    text: str
    category: ClaimCategory
    page_number: Optional[int] = None
    chunk_id: Optional[str] = None
    evidence_relationship: EvidenceRelationship
    support_status: str = "supported"
    explanation: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    paper_id: str
    paper_title: str
    objective: str = "Not reported"
    methodology: str = "Not reported"
    dataset: str = "Not reported"
    metrics: str = "Not reported"
    reported_finding: str = "Not reported"
    evidence_relationship: EvidenceRelationship
    limitations: str = "Not reported"
    primary_evidence_id: Optional[str] = None


class DisagreementItem(BaseModel):
    topic: str
    description: str
    paper_ids: List[str]
    evidence_ids: List[str] = Field(default_factory=list)


class ReportSection(BaseModel):
    heading: str
    content: str
    citations: List[str] = Field(default_factory=list)


class InvestigationReport(BaseModel):
    id: str
    investigation_id: str
    research_question: str
    executive_summary: str
    relevant_papers: List[PaperRelevance]
    main_claims: List[ClaimOut]
    supporting_evidence: List[EvidenceItem]
    cross_paper_comparison: List[ComparisonRow]
    disagreements: List[DisagreementItem]
    methodological_differences: List[str]
    limitations: List[str]
    unresolved_questions: List[str]
    suggested_next_investigations: List[str]
    references: List[Dict[str, Any]]
    sections: List[ReportSection] = Field(default_factory=list)
    markdown: str
    validation_status: Literal["valid", "needs_revision", "invalid"]
    validation_notes: List[str] = Field(default_factory=list)
    created_at: datetime


class InvestigationStatus(BaseModel):
    id: str
    status: str
    stage: str
    progress: int
    error: Optional[str] = None
    updated_at: datetime


class InvestigationSummary(BaseModel):
    id: str
    research_question: str
    status: str
    stage: str
    progress: int
    paper_ids: List[str]
    created_at: datetime
    updated_at: datetime


class InvestigationDetail(InvestigationSummary):
    relevant_papers: List[PaperRelevance] = Field(default_factory=list)
    main_claims: List[ClaimOut] = Field(default_factory=list)
    supporting_evidence: List[EvidenceItem] = Field(default_factory=list)
    cross_paper_comparison: List[ComparisonRow] = Field(default_factory=list)
    disagreements: List[DisagreementItem] = Field(default_factory=list)
    report: Optional[InvestigationReport] = None


class ApiError(BaseModel):
    detail: str
    code: Optional[str] = None
