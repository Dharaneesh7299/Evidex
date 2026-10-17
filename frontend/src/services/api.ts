import {
  Claim,
  ComparisonRow,
  EvidenceItem,
  InvestigationDetail,
  InvestigationReport,
  InvestigationStatus,
  InvestigationSummary,
  Paper,
  PaperUploadResponse,
  SystemHealth,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson && errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export const api = {
  // System Health
  async getHealth(): Promise<SystemHealth> {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse<SystemHealth>(res);
  },

  // Papers
  async listPapers(): Promise<Paper[]> {
    const res = await fetch(`${API_BASE}/papers`);
    return handleResponse<Paper[]>(res);
  },

  async getPaper(paperId: string): Promise<Paper> {
    const res = await fetch(`${API_BASE}/papers/${paperId}`);
    return handleResponse<Paper>(res);
  },

  async getPaperPage(paperId: string, pageNumber: number): Promise<{ paper_id: string; paper_title: string; page_number: number; text: string }> {
    const res = await fetch(`${API_BASE}/papers/${paperId}/page/${pageNumber}`);
    return handleResponse(res);
  },

  async uploadPaper(file: File): Promise<PaperUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/papers/upload`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<PaperUploadResponse>(res);
  },

  async deletePaper(paperId: string): Promise<{ status: string; paper_id: string }> {
    const res = await fetch(`${API_BASE}/papers/${paperId}`, {
      method: 'DELETE',
    });
    return handleResponse(res);
  },

  // Investigations
  async createInvestigation(data: { research_question: string; paper_ids: string[] }): Promise<InvestigationSummary> {
    const res = await fetch(`${API_BASE}/investigations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<InvestigationSummary>(res);
  },

  async listInvestigations(): Promise<InvestigationSummary[]> {
    const res = await fetch(`${API_BASE}/investigations`);
    return handleResponse<InvestigationSummary[]>(res);
  },

  async getInvestigation(id: string): Promise<InvestigationDetail> {
    const res = await fetch(`${API_BASE}/investigations/${id}`);
    return handleResponse<InvestigationDetail>(res);
  },

  async getInvestigationStatus(id: string): Promise<InvestigationStatus> {
    const res = await fetch(`${API_BASE}/investigations/${id}/status`);
    return handleResponse<InvestigationStatus>(res);
  },

  async getInvestigationClaims(id: string): Promise<Claim[]> {
    const res = await fetch(`${API_BASE}/investigations/${id}/claims`);
    return handleResponse<Claim[]>(res);
  },

  async getInvestigationEvidence(id: string): Promise<EvidenceItem[]> {
    const res = await fetch(`${API_BASE}/investigations/${id}/evidence`);
    return handleResponse<EvidenceItem[]>(res);
  },

  async getInvestigationComparison(id: string): Promise<ComparisonRow[]> {
    const res = await fetch(`${API_BASE}/investigations/${id}/comparison`);
    return handleResponse<ComparisonRow[]>(res);
  },

  async getInvestigationReport(id: string): Promise<InvestigationReport> {
    const res = await fetch(`${API_BASE}/investigations/${id}/report`);
    return handleResponse<InvestigationReport>(res);
  },

  async rerunInvestigation(id: string): Promise<{ message: string }> {
    const res = await fetch(`${API_BASE}/investigations/${id}/rerun`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  // Sample data loader
  async loadSample(): Promise<{ investigation_id: string; message: string }> {
    const res = await fetch(`${API_BASE}/sample`);
    return handleResponse(res);
  },
};
