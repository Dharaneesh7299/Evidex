export type EvidenceRelationship =
  | 'supported_by_document'
  | 'partially_supports'
  | 'unsupported_in_available_document'
  | 'potentially_conflicting_evidence'
  | 'insufficient_information'
  | 'not_directly_comparable';

export type ClaimCategory =
  | 'reported_finding'
  | 'methodology'
  | 'limitation'
  | 'result'
  | 'background'
  | 'general';

export interface PaperMetadata {
  title?: string;
  authors?: string;
  year?: string;
  page_count?: number;
  confidence?: 'high' | 'medium' | 'low';
  notes?: string;
}

export interface Paper {
  id: string;
  title?: string;
  authors?: string;
  year?: string;
  original_filename: string;
  file_size: number;
  page_count: number;
  char_count: number;
  status: string;
  error?: string;
  metadata?: PaperMetadata;
  created_at: string;
  updated_at: string;
}

export interface PaperUploadResponse {
  paper: Paper;
  chunks: number;
}

export interface PaperRelevance {
  paper_id: string;
  score: number;
  label: string;
  explanation: string;
  supporting_evidence_ids: string[];
  summary?: string;
  findings: string[];
  limitations: string[];
}

export interface EvidenceItem {
  id: string;
  investigation_id: string;
  claim_id?: string;
  paper_id: string;
  page_number: number;
  chunk_id?: string;
  passage: string;
  relationship: EvidenceRelationship;
  explanation?: string;
  reference_valid: boolean;
  support_status?: 'supports' | 'partially_supports' | 'contradicts' | 'unsupported';
  validated: boolean;
}

export interface Claim {
  id: string;
  investigation_id: string;
  paper_id?: string;
  text: string;
  category: ClaimCategory;
  page_number?: number;
  chunk_id?: string;
  evidence_relationship: EvidenceRelationship;
  support_status?: 'supported' | 'partially_supported' | 'contradicted' | 'insufficiently_supported';
  explanation?: string;
  limitations: string[];
  evidence_ids: string[];
}

export interface ComparisonRow {
  paper_id: string;
  paper_title: string;
  objective: string;
  methodology: string;
  dataset: string;
  metrics: string;
  reported_finding: string;
  evidence_relationship: EvidenceRelationship;
  limitations: string;
  primary_evidence_id?: string;
}

export interface DisagreementItem {
  topic: string;
  description: string;
  paper_ids: string[];
  evidence_ids: string[];
}

export interface ReportSection {
  heading: string;
  content: string;
  citations: string[];
}

export interface InvestigationReport {
  id: string;
  investigation_id: string;
  research_question: string;
  executive_summary: string;
  relevant_papers: PaperRelevance[];
  main_claims: Claim[];
  supporting_evidence: EvidenceItem[];
  cross_paper_comparison: ComparisonRow[];
  disagreements: DisagreementItem[];
  methodological_differences: string[];
  limitations: string[];
  unresolved_questions: string[];
  suggested_next_investigations: string[];
  references: Array<{
    paper_id: string;
    title: string;
    authors: string;
    year: string;
    pages: number;
  }>;
  sections: ReportSection[];
  markdown: string;
  validation_status: 'valid' | 'needs_revision' | 'invalid';
  validation_notes: string[];
  created_at: string;
}

export interface InvestigationStatus {
  id: string;
  status: string;
  stage: string;
  progress: number;
  error?: string;
  updated_at: string;
}

export interface InvestigationSummary {
  id: string;
  research_question: string;
  status: string;
  stage: string;
  progress: number;
  paper_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface InvestigationDetail extends InvestigationSummary {
  relevant_papers: PaperRelevance[];
  main_claims: Claim[];
  supporting_evidence: EvidenceItem[];
  cross_paper_comparison: ComparisonRow[];
  disagreements: DisagreementItem[];
  report?: InvestigationReport;
}

export interface SystemHealth {
  status: string;
  service: string;
  version: string;
  has_gemini: boolean;
  gemini_model: string;
  papers_count: number;
  investigations_count: number;
}
