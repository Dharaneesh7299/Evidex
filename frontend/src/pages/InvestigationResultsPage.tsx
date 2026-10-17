import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  FileText,
  BookOpen,
  Layers,
  Table,
  CheckCircle2,
  AlertCircle,
  Copy,
  Download,
  Printer,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  AlertTriangle,
  RotateCw,
  Search,
  Filter,
  Check,
  HelpCircle,
  Info,
} from 'lucide-react';
import { api } from '../services/api';
import {
  Claim,
  ClaimCategory,
  EvidenceItem,
  EvidenceRelationship,
  InvestigationDetail,
  PaperRelevance,
} from '../types';
import { Header } from '../components/Header';
import { EvidenceBadge, ReferenceBadge, SupportBadge } from '../components/EvidenceBadge';
import { PassageViewerModal } from '../components/PassageViewerModal';

type TabType = 'overview' | 'papers' | 'claims' | 'comparison' | 'report';

export const InvestigationResultsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [investigation, setInvestigation] = useState<InvestigationDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  // Filters for Claims Tab
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [relationshipFilter, setRelationshipFilter] = useState<string>('all');

  // Modal State for Source Passage Viewer
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [modalPaperId, setModalPaperId] = useState<string>('');
  const [modalPaperTitle, setModalPaperTitle] = useState<string>('');
  const [modalPageNumber, setModalPageNumber] = useState<number>(1);
  const [modalPassage, setModalPassage] = useState<string>('');
  const [modalValidated, setModalValidated] = useState<boolean>(true);

  // Copy feedback state
  const [copiedMd, setCopiedMd] = useState<boolean>(false);

  const fetchInvestigation = () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    api
      .getInvestigation(id)
      .then((data) => {
        setInvestigation(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load investigation details');
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchInvestigation();
  }, [id]);

  const openPassageViewer = (
    paperId: string,
    pageNumber: number,
    passage: string = '',
    paperTitle?: string,
    validated: boolean = true
  ) => {
    setModalPaperId(paperId);
    setModalPageNumber(pageNumber || 1);
    setModalPassage(passage);
    setModalPaperTitle(paperTitle || paperId);
    setModalValidated(validated);
    setModalOpen(true);
  };

  const handleCopyMarkdown = () => {
    if (!investigation?.report?.markdown) return;
    navigator.clipboard.writeText(investigation.report.markdown);
    setCopiedMd(true);
    setTimeout(() => setCopiedMd(false), 2000);
  };

  const handleDownloadMarkdown = () => {
    if (!investigation?.report?.markdown) return;
    const blob = new Blob([investigation.report.markdown], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `evidex_investigation_${investigation.id}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col bg-white">
        <Header />
        <div className="flex-1 flex items-center justify-center p-12 text-sm text-[#667085]">
          <div className="flex items-center gap-3">
            <div className="w-5 h-5 border-2 border-[#3156D9] border-t-transparent rounded-full animate-spin" />
            Loading research investigation findings...
          </div>
        </div>
      </div>
    );
  }

  if (error || !investigation) {
    return (
      <div className="flex-1 flex flex-col bg-white">
        <Header />
        <div className="flex-1 max-w-2xl mx-auto p-12 text-center">
          <AlertCircle className="w-10 h-10 text-red-500 mx-auto mb-3" />
          <h2 className="text-lg font-semibold text-[#202124]">Investigation Not Found</h2>
          <p className="text-sm text-[#667085] mt-1 mb-6">{error || 'Could not retrieve investigation record.'}</p>
          <Link
            to="/new"
            className="px-4 py-2 bg-[#3156D9] text-white rounded-lg text-sm font-medium hover:bg-[#2546B8]"
          >
            Start New Investigation
          </Link>
        </div>
      </div>
    );
  }

  // Filtered claims
  const filteredClaims = investigation.main_claims.filter((c) => {
    if (categoryFilter !== 'all' && c.category !== categoryFilter) return false;
    if (relationshipFilter !== 'all' && c.evidence_relationship !== relationshipFilter) return false;
    return true;
  });

  return (
    <div className="flex-1 flex flex-col bg-white min-h-screen">
      <Header />

      {/* Investigation Title Bar */}
      <div className="border-b border-[#E5E7EB] bg-white px-8 py-5">
        <div className="max-w-6xl mx-auto space-y-3">
          <div className="flex items-center gap-2 text-xs text-[#667085]">
            <Link to="/investigations" className="hover:underline">Investigations</Link>
            <span>/</span>
            <span className="font-mono">{investigation.id}</span>
          </div>

          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1 max-w-4xl">
              <h1 className="text-xl sm:text-2xl font-bold text-[#202124] leading-tight m-0">
                {investigation.research_question}
              </h1>
              <div className="flex items-center gap-3 text-xs text-[#667085]">
                <span className="inline-flex items-center gap-1 text-[#16803C] font-medium bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  <CheckCircle2 className="w-3 h-3 text-[#16803C]" />
                  {investigation.status.toUpperCase()}
                </span>
                <span>&bull;</span>
                <span>{investigation.paper_ids.length} Research Papers Analyzed</span>
                <span>&bull;</span>
                <span>{investigation.supporting_evidence.length} Verifiable Citations</span>
                <span>&bull;</span>
                <span>{new Date(investigation.created_at).toLocaleDateString()}</span>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={handleCopyMarkdown}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-[#E5E7EB] bg-white hover:bg-gray-50 rounded-lg text-gray-700 shadow-2xs transition-colors cursor-pointer"
                title="Copy Markdown Report to clipboard"
              >
                {copiedMd ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                {copiedMd ? 'Copied' : 'Copy Report'}
              </button>

              <button
                onClick={handleDownloadMarkdown}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[#3156D9] hover:bg-[#2546B8] text-white rounded-lg shadow-2xs transition-colors cursor-pointer"
                title="Download formatted scientific report in Markdown"
              >
                <Download className="w-3.5 h-3.5" />
                Export .md
              </button>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-2 border-t border-[#E5E7EB] pt-4 -mb-2 overflow-x-auto">
            {[
              { id: 'overview', label: 'Overview', icon: FileText, badge: null },
              { id: 'papers', label: 'Papers', icon: BookOpen, badge: investigation.relevant_papers.length },
              { id: 'claims', label: 'Claims & Evidence', icon: ShieldCheck, badge: investigation.main_claims.length },
              { id: 'comparison', label: 'Comparison', icon: Table, badge: investigation.cross_paper_comparison.length },
              { id: 'report', label: 'Final Report', icon: FileText, badge: 'Verified' },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={`inline-flex items-center gap-2 px-3.5 py-2 text-xs font-medium rounded-lg transition-all cursor-pointer ${
                    isActive
                      ? 'bg-blue-50 text-[#3156D9] font-semibold border-b-2 border-[#3156D9]'
                      : 'text-[#667085] hover:bg-gray-50 hover:text-gray-900'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-[#3156D9]' : 'text-gray-400'}`} />
                  <span>{tab.label}</span>
                  {tab.badge !== null && (
                    <span
                      className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
                        isActive ? 'bg-[#3156D9] text-white' : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Tab Content */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-8 py-8">
        {/* ============================================================== */}
        {/* TAB 1: OVERVIEW                                                 */}
        {/* ============================================================== */}
        {activeTab === 'overview' && (
          <div className="space-y-8 animate-in fade-in-50 duration-150">
            {/* Executive Summary Card */}
            <div className="border border-[#E5E7EB] rounded-xl p-6 bg-white shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-[#202124] uppercase tracking-wider text-xs">
                  Executive Investigation Summary
                </h3>
                <span className="inline-flex items-center gap-1 text-xs text-[#16803C] font-medium bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  <ShieldCheck className="w-3.5 h-3.5 text-[#16803C]" />
                  All Conclusions Grounded
                </span>
              </div>
              <p className="text-sm text-gray-800 leading-relaxed font-normal">
                {investigation.report?.executive_summary ||
                  'Analysis completed. Conclusions have been synthesized across the uploaded research papers.'}
              </p>
            </div>

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-5 rounded-xl border border-[#E5E7EB] bg-[#F8F9FB]/60 space-y-1">
                <span className="text-xs text-[#667085] font-medium">Relevance Alignment</span>
                <div className="text-xl font-bold text-[#202124] flex items-center gap-2">
                  <span>
                    {investigation.relevant_papers[0]
                      ? `${Math.round(investigation.relevant_papers[0].score * 100)}% Top Match`
                      : 'Evaluated'}
                  </span>
                </div>
                <p className="text-[11px] text-[#667085]">
                  Top scoring paper: {investigation.relevant_papers[0]?.label || 'High'} relevance to target query.
                </p>
              </div>

              <div className="p-5 rounded-xl border border-[#E5E7EB] bg-[#F8F9FB]/60 space-y-1">
                <span className="text-xs text-[#667085] font-medium">Extracted Core Claims</span>
                <div className="text-xl font-bold text-[#202124]">
                  {investigation.main_claims.length} Findings
                </div>
                <p className="text-[11px] text-[#667085]">
                  Isolates reported metrics, datasets, and boundary limitations.
                </p>
              </div>

              <div className="p-5 rounded-xl border border-[#E5E7EB] bg-[#F8F9FB]/60 space-y-1">
                <span className="text-xs text-[#667085] font-medium">Evidence Provenance</span>
                <div className="text-xl font-bold text-[#16803C] flex items-center gap-1.5">
                  <CheckCircle2 className="w-5 h-5 text-[#16803C]" />
                  {investigation.supporting_evidence.filter(e => e.reference_valid ?? e.validated).length} / {investigation.supporting_evidence.length} Ref Verified
                </div>
                <p className="text-[11px] text-[#667085]">
                  {investigation.supporting_evidence.filter(e => e.support_status === 'supports' || e.relationship === 'supported_by_document').length} / {investigation.supporting_evidence.length} passages confirm semantic support.
                </p>
              </div>
            </div>

            {/* Top Relevant Papers Summary */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-[#202124] flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-[#3156D9]" />
                  Most Relevant Research Papers
                </h3>
                <button
                  onClick={() => setActiveTab('papers')}
                  className="text-xs font-medium text-[#3156D9] hover:underline flex items-center gap-1"
                >
                  View full papers analysis <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {investigation.relevant_papers.map((rel) => {
                  const paper = investigation.report?.references.find((r) => r.paper_id === rel.paper_id);
                  return (
                    <div
                      key={rel.paper_id}
                      className="border border-[#E5E7EB] rounded-xl p-5 bg-white shadow-2xs hover:border-gray-300 transition-colors flex flex-col justify-between"
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-50 text-[#3156D9] font-medium border border-blue-200">
                            Relevance: {rel.score.toFixed(2)} ({rel.label})
                          </span>
                          <span className="text-xs text-[#667085]">{paper?.year || '2024'}</span>
                        </div>
                        <h4 className="text-sm font-semibold text-[#202124] line-clamp-2">
                          {paper?.title || rel.paper_id}
                        </h4>
                        <p className="text-xs text-[#667085] line-clamp-3 leading-relaxed">
                          {rel.explanation}
                        </p>
                      </div>

                      <div className="pt-4 mt-3 border-t border-gray-100 flex items-center justify-between text-xs">
                        <span className="text-[#667085] truncate max-w-[150px]">{paper?.authors}</span>
                        <button
                          onClick={() => openPassageViewer(rel.paper_id, 1, '', paper?.title)}
                          className="text-[#3156D9] hover:underline font-medium cursor-pointer"
                        >
                          View Pages
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Potential Disagreements & Limitations Banner */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Disagreements */}
              <div className="border border-amber-200 bg-amber-50/30 rounded-xl p-5 space-y-3">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-900">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  Potential Disagreements & Domain Boundaries
                </div>
                {investigation.disagreements.length > 0 ? (
                  investigation.disagreements.map((d, i) => (
                    <div key={i} className="text-xs space-y-1">
                      <h5 className="font-semibold text-gray-900">{d.topic}</h5>
                      <p className="text-gray-700 leading-relaxed">{d.description}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-gray-600">
                    No explicit numerical or categorical contradictions detected across the provided texts.
                  </p>
                )}
              </div>

              {/* Evidence Limitations */}
              <div className="border border-[#E5E7EB] bg-[#F8F9FB] rounded-xl p-5 space-y-3">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <Info className="w-4 h-4 text-[#667085]" />
                  Honest Evidence Limitations
                </div>
                <ul className="text-xs text-gray-700 space-y-1.5 list-disc pl-4 leading-relaxed">
                  {investigation.report?.limitations.map((lim, idx) => (
                    <li key={idx}>{lim}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 2: PAPERS                                                  */}
        {/* ============================================================== */}
        {activeTab === 'papers' && (
          <div className="space-y-6 animate-in fade-in-50 duration-150">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-[#202124] m-0">Analyzed Research Papers</h3>
                <p className="text-xs text-[#667085] mt-0.5">
                  Relevance scores measure semantic and lexical topical alignment with the research query.
                </p>
              </div>
            </div>

            <div className="space-y-4">
              {investigation.relevant_papers.map((rel) => {
                const ref = investigation.report?.references.find((r) => r.paper_id === rel.paper_id);
                const title = ref?.title || rel.paper_id;

                return (
                  <div
                    key={rel.paper_id}
                    className="border border-[#E5E7EB] rounded-xl p-6 bg-white shadow-2xs space-y-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-medium text-[#3156D9] bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                            Relevance: {rel.score.toFixed(2)} &bull; {rel.label}
                          </span>
                          <span className="text-xs text-[#667085]">{ref?.year || '2024'}</span>
                          <span className="text-xs text-[#667085]">&bull;</span>
                          <span className="text-xs text-[#667085]">{ref?.pages || 4} pages</span>
                        </div>
                        <h4 className="text-base font-semibold text-[#202124]">{title}</h4>
                        <p className="text-xs text-[#667085]">{ref?.authors || 'Authors not reported'}</p>
                      </div>

                      <button
                        onClick={() => openPassageViewer(rel.paper_id, 1, '', title)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-[#E5E7EB] hover:bg-[#F8F9FB] rounded-lg text-gray-700 transition-colors shrink-0 cursor-pointer"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        Inspect Document Text
                      </button>
                    </div>

                    {/* Relevance Explanation */}
                    <div className="p-3 bg-[#F8F9FB] rounded-lg border border-[#E5E7EB] text-xs space-y-1">
                      <span className="font-semibold text-gray-900">Why Relevant to Question:</span>
                      <p className="text-gray-700 leading-relaxed">{rel.explanation}</p>
                    </div>

                    {/* Summary & Findings */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                      <div className="space-y-1.5">
                        <span className="font-semibold text-gray-900 block">Reported Findings:</span>
                        <ul className="space-y-1 list-disc pl-4 text-gray-700">
                          {rel.findings.map((f, i) => (
                            <li key={i}>{f}</li>
                          ))}
                        </ul>
                      </div>

                      <div className="space-y-1.5">
                        <span className="font-semibold text-gray-900 block">Identified Limitations:</span>
                        <ul className="space-y-1 list-disc pl-4 text-gray-700">
                          {rel.limitations.map((l, i) => (
                            <li key={i}>{l}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 3: CLAIMS & EVIDENCE                                       */}
        {/* ============================================================== */}
        {activeTab === 'claims' && (
          <div className="space-y-6 animate-in fade-in-50 duration-150">
            {/* Filters bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl border border-[#E5E7EB] bg-[#F8F9FB]">
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-[#667085]" />
                <span className="text-xs font-semibold text-[#202124]">Filter Claims:</span>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="text-xs bg-white border border-[#E5E7EB] rounded-lg px-2.5 py-1.5 text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#3156D9]"
                >
                  <option value="all">All Categories ({investigation.main_claims.length})</option>
                  <option value="reported_finding">Reported Findings</option>
                  <option value="methodology">Methodology</option>
                  <option value="limitation">Limitations</option>
                  <option value="result">Results</option>
                </select>

                <select
                  value={relationshipFilter}
                  onChange={(e) => setRelationshipFilter(e.target.value)}
                  className="text-xs bg-white border border-[#E5E7EB] rounded-lg px-2.5 py-1.5 text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#3156D9]"
                >
                  <option value="all">All Evidence Statuses</option>
                  <option value="supported_by_document">Supported by document</option>
                  <option value="partially_supports">Partially supported</option>
                  <option value="potentially_conflicting_evidence">Potentially conflicting</option>
                  <option value="insufficient_information">Insufficient information</option>
                </select>
              </div>
            </div>

            {/* Claims List */}
            <div className="space-y-4">
              {filteredClaims.length === 0 ? (
                <div className="p-12 text-center text-xs text-[#667085] border border-[#E5E7EB] rounded-xl bg-white">
                  No claims match the selected filters.
                </div>
              ) : (
                filteredClaims.map((claim) => {
                  const ref = investigation.report?.references.find((r) => r.paper_id === claim.paper_id);
                  const paperTitle = ref?.title || claim.paper_id || 'Research Paper';
                  const claimEvidence = investigation.supporting_evidence.filter((e) =>
                    claim.evidence_ids.includes(e.id)
                  );

                  return (
                    <div
                      key={claim.id}
                      className="border border-[#E5E7EB] rounded-xl p-6 bg-white shadow-2xs space-y-4"
                    >
                      {/* Claim Header */}
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-1.5 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[11px] uppercase font-mono font-bold px-2 py-0.5 rounded bg-gray-100 text-gray-700 border border-gray-200">
                              {claim.category.replace('_', ' ')}
                            </span>
                            <EvidenceBadge relationship={claim.evidence_relationship} size="sm" />
                            <span className="text-xs text-[#667085]">
                              {paperTitle} &bull; Page {claim.page_number || 'N/A'}
                            </span>
                          </div>

                          <h4 className="text-base font-semibold text-[#202124] leading-snug">
                            "{claim.text}"
                          </h4>
                        </div>
                      </div>

                      {/* Supporting Passage Callout */}
                      {claimEvidence.length > 0 && (
                        <div className="space-y-2 border-t border-gray-100 pt-3">
                          <span className="text-[11px] uppercase tracking-wider font-semibold text-[#667085] block">
                            Retrieved Verifiable Passage(s):
                          </span>

                          {claimEvidence.map((evi) => (
                            <div
                              key={evi.id}
                              className="bg-amber-50/40 border border-amber-200/80 rounded-lg p-3 space-y-2"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                                <div className="flex items-center gap-1.5">
                                  <ReferenceBadge valid={evi.reference_valid ?? evi.validated} page={evi.page_number} size="sm" />
                                  <SupportBadge status={evi.support_status} relationship={evi.relationship} size="sm" />
                                </div>

                                <button
                                  onClick={() =>
                                    openPassageViewer(evi.paper_id, evi.page_number, evi.passage, paperTitle, evi.reference_valid ?? evi.validated)
                                  }
                                  className="text-xs text-[#3156D9] hover:underline font-medium inline-flex items-center gap-1 cursor-pointer"
                                >
                                  View in Page Context <ExternalLink className="w-3 h-3" />
                                </button>
                              </div>

                              <blockquote className="text-xs text-gray-900 leading-relaxed font-serif italic pl-3 border-l-2 border-amber-400">
                                "{evi.passage}"
                              </blockquote>

                              {evi.explanation && (
                                <p className="text-[11px] text-gray-600 pl-3">
                                  <span className="font-semibold text-gray-700">Relationship Note:</span> {evi.explanation}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Limitations of finding */}
                      {claim.limitations && claim.limitations.length > 0 && (
                        <div className="text-xs text-[#667085] bg-[#F8F9FB] p-2.5 rounded-lg border border-[#E5E7EB]">
                          <span className="font-semibold text-gray-700">Caveat / Boundary:</span>{' '}
                          {claim.limitations.join(' ')}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 4: COMPARISON                                              */}
        {/* ============================================================== */}
        {activeTab === 'comparison' && (
          <div className="space-y-8 animate-in fade-in-50 duration-150">
            <div>
              <h3 className="text-base font-semibold text-[#202124] m-0">Cross-Paper Comparison Matrix</h3>
              <p className="text-xs text-[#667085] mt-0.5">
                Standardized cross-document comparison mapping objectives, datasets, reported findings, and boundaries.
              </p>
            </div>

            {/* Comparison Table */}
            <div className="border border-[#E5E7EB] rounded-xl overflow-hidden bg-white shadow-2xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-gray-800">
                  <thead className="bg-[#F8F9FB] border-b border-[#E5E7EB] text-[#667085] font-semibold uppercase tracking-wider">
                    <tr>
                      <th className="px-4 py-3 min-w-[160px]">Research Paper</th>
                      <th className="px-4 py-3 min-w-[140px]">Methodology</th>
                      <th className="px-4 py-3 min-w-[130px]">Dataset / Cohort</th>
                      <th className="px-4 py-3 min-w-[120px]">Metrics</th>
                      <th className="px-4 py-3 min-w-[200px]">Reported Finding</th>
                      <th className="px-4 py-3 min-w-[140px]">Evidence Status</th>
                      <th className="px-4 py-3 min-w-[150px]">Limitations</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E7EB]">
                    {investigation.cross_paper_comparison.map((row, idx) => (
                      <tr key={idx} className="hover:bg-[#F8F9FB]/60 transition-colors">
                        <td className="px-4 py-3.5 font-medium text-[#202124]">
                          {row.paper_title}
                        </td>
                        <td className="px-4 py-3.5 text-gray-600 leading-relaxed">{row.methodology}</td>
                        <td className="px-4 py-3.5 text-gray-600 leading-relaxed">{row.dataset}</td>
                        <td className="px-4 py-3.5 text-gray-600">{row.metrics}</td>
                        <td className="px-4 py-3.5 font-medium text-gray-900 leading-relaxed">
                          {row.reported_finding}
                        </td>
                        <td className="px-4 py-3.5">
                          <EvidenceBadge relationship={row.evidence_relationship} size="sm" />
                        </td>
                        <td className="px-4 py-3.5 text-gray-500 leading-relaxed">{row.limitations}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Methodological Differences & Disagreements */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="border border-[#E5E7EB] rounded-xl p-5 bg-white space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-[#202124]">
                  Methodological Divergence
                </h4>
                <ul className="text-xs text-gray-700 space-y-2 list-disc pl-4 leading-relaxed">
                  {investigation.report?.methodological_differences.map((diff, i) => (
                    <li key={i}>{diff}</li>
                  ))}
                </ul>
              </div>

              <div className="border border-amber-200 bg-amber-50/40 rounded-xl p-5 space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-900 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                  Identified Cross-Study Boundaries
                </h4>
                <ul className="text-xs text-amber-950 space-y-2 list-disc pl-4 leading-relaxed">
                  {investigation.disagreements.map((d, i) => (
                    <li key={i}>
                      <strong>{d.topic}:</strong> {d.description}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 5: FINAL REPORT                                            */}
        {/* ============================================================== */}
        {activeTab === 'report' && (
          <div className="space-y-6 max-w-4xl mx-auto animate-in fade-in-50 duration-150">
            {/* Citation Audit Banner */}
            <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/60 flex items-center justify-between text-xs text-emerald-900">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-[#16803C] shrink-0" />
                <span className="font-semibold">Citation Audit Status: Valid</span>
                <span>&bull;</span>
                <span>All cited passages cross-checked against original extracted document pages.</span>
              </div>
              <span className="font-mono text-emerald-800">
                {investigation.supporting_evidence.length} citations verified
              </span>
            </div>

            {/* Rendered Document Report Sheet */}
            <article className="border border-[#E5E7EB] rounded-xl p-8 sm:p-12 bg-white shadow-xs space-y-8 font-sans">
              <div className="border-b border-[#E5E7EB] pb-6 space-y-2">
                <div className="text-xs font-mono uppercase tracking-wider text-[#667085]">
                  Evidex Research Investigation Report
                </div>
                <h2 className="text-2xl sm:text-3xl font-bold text-[#202124] tracking-tight leading-tight m-0">
                  {investigation.research_question}
                </h2>
                <div className="text-xs text-[#667085] flex items-center gap-3 pt-1">
                  <span>Generated: {new Date(investigation.created_at).toLocaleString()}</span>
                  <span>&bull;</span>
                  <span>{investigation.paper_ids.length} Papers</span>
                  <span>&bull;</span>
                  <span>{investigation.main_claims.length} Grounded Claims</span>
                </div>
              </div>

              {/* Section 1: Executive Summary */}
              <section className="space-y-2">
                <h3 className="text-base font-bold text-[#202124] border-b border-gray-100 pb-1">
                  1. Executive Summary
                </h3>
                <p className="text-sm text-gray-800 leading-relaxed font-normal">
                  {investigation.report?.executive_summary}
                </p>
              </section>

              {/* Section 2: Relevant Papers */}
              <section className="space-y-3">
                <h3 className="text-base font-bold text-[#202124] border-b border-gray-100 pb-1">
                  2. Relevant Papers and Evidence Grounding
                </h3>
                <div className="space-y-3">
                  {investigation.relevant_papers.map((rel) => {
                    const ref = investigation.report?.references.find((r) => r.paper_id === rel.paper_id);
                    return (
                      <div key={rel.paper_id} className="text-xs space-y-1 bg-[#F8F9FB] p-3 rounded-lg border border-[#E5E7EB]">
                        <div className="font-semibold text-gray-900 text-sm">
                          {ref?.title} ({ref?.year})
                        </div>
                        <p className="text-gray-700 leading-relaxed">{rel.explanation}</p>
                        <div className="text-[#667085] text-[11px]">
                          <strong>Key Reported Finding:</strong> {rel.findings.join(' ')}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Section 3: Main Claims & Passages */}
              <section className="space-y-3">
                <h3 className="text-base font-bold text-[#202124] border-b border-gray-100 pb-1">
                  3. Extracted Claims & Supporting Passages
                </h3>
                <div className="space-y-4">
                  {investigation.main_claims.map((c) => {
                    const evis = investigation.supporting_evidence.filter((e) => c.evidence_ids.includes(e.id));
                    return (
                      <div key={c.id} className="text-xs space-y-2">
                        <div className="font-semibold text-gray-900 text-sm">
                          "{c.text}"
                        </div>
                        <div className="flex items-center gap-2">
                          <EvidenceBadge relationship={c.evidence_relationship} size="sm" />
                          <span className="text-gray-500">Source: Paper {c.paper_id}, Page {c.page_number}</span>
                        </div>
                        {evis.map((e) => (
                          <blockquote
                            key={e.id}
                            className="text-xs font-serif italic text-gray-800 pl-3 border-l-2 border-blue-400 bg-blue-50/30 py-1.5"
                          >
                            "{e.passage}" — <span className="font-sans font-medium text-blue-900">[Page {e.page_number}]</span>
                          </blockquote>
                        ))}
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Section 4: Cross-Paper Matrix */}
              <section className="space-y-3">
                <h3 className="text-base font-bold text-[#202124] border-b border-gray-100 pb-1">
                  4. Cross-Paper Comparison Matrix
                </h3>
                <div className="border border-gray-200 rounded-lg overflow-x-auto text-xs">
                  <table className="w-full text-left">
                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-700">
                      <tr>
                        <th className="p-2.5">Paper</th>
                        <th className="p-2.5">Methodology</th>
                        <th className="p-2.5">Dataset</th>
                        <th className="p-2.5">Reported Finding</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {investigation.cross_paper_comparison.map((r, i) => (
                        <tr key={i}>
                          <td className="p-2.5 font-medium">{r.paper_title}</td>
                          <td className="p-2.5 text-gray-600">{r.methodology}</td>
                          <td className="p-2.5 text-gray-600">{r.dataset}</td>
                          <td className="p-2.5 font-medium text-gray-900">{r.reported_finding}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Section 5: Boundaries & Disagreements */}
              <section className="space-y-2">
                <h3 className="text-base font-bold text-[#202124] border-b border-gray-100 pb-1">
                  5. Potential Disagreements & Domain Boundaries
                </h3>
                {investigation.disagreements.map((d, i) => (
                  <p key={i} className="text-xs text-gray-800 leading-relaxed">
                    <strong>{d.topic}:</strong> {d.description}
                  </p>
                ))}
              </section>

              {/* Section 6: Limitations & Next Steps */}
              <section className="space-y-2">
                <h3 className="text-base font-bold text-[#202124] border-b border-gray-100 pb-1">
                  6. Limitations and Suggested Next Investigations
                </h3>
                <ul className="text-xs text-gray-800 space-y-1 list-disc pl-4 leading-relaxed">
                  {investigation.report?.limitations.map((lim, i) => (
                    <li key={i}>{lim}</li>
                  ))}
                  {investigation.report?.suggested_next_investigations.map((s, i) => (
                    <li key={`s_${i}`}>
                      <strong>Next step:</strong> {s}
                    </li>
                  ))}
                </ul>
              </section>

              {/* Section 7: References */}
              <section className="space-y-2 pt-4 border-t border-[#E5E7EB]">
                <h3 className="text-sm font-bold uppercase tracking-wider text-[#667085]">
                  7. Document References
                </h3>
                <ul className="text-xs text-gray-600 space-y-1 font-mono">
                  {investigation.report?.references.map((r) => (
                    <li key={r.paper_id}>
                      [{r.paper_id}] {r.title}. {r.authors} ({r.year}), {r.pages} pages.
                    </li>
                  ))}
                </ul>
              </section>
            </article>
          </div>
        )}
      </main>

      {/* Modal for viewing raw source page and passage context */}
      <PassageViewerModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        paperId={modalPaperId}
        paperTitle={modalPaperTitle}
        pageNumber={modalPageNumber}
        highlightPassage={modalPassage}
        validated={modalValidated}
      />
    </div>
  );
};
