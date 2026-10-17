import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  FileSearch,
  BookOpen,
  PlusCircle,
  FileText,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
  Search,
  Layers,
  ChevronRight,
  BarChart2,
  Clock,
  ExternalLink,
} from 'lucide-react';
import { api } from '../services/api';
import { InvestigationSummary, Paper, SystemHealth } from '../types';
import { Header } from '../components/Header';
import { EmptyState } from '../components/EmptyState';

export const OverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [sampleLoading, setSampleLoading] = useState<boolean>(false);

  useEffect(() => {
    Promise.all([api.listPapers(), api.listInvestigations(), api.getHealth()])
      .then(([papersData, invsData, healthData]) => {
        setPapers(papersData);
        setInvestigations(invsData);
        setHealth(healthData);
      })
      .catch((err) => console.error('Error loading overview:', err))
      .finally(() => setLoading(false));
  }, []);

  const handleOpenSample = async () => {
    setSampleLoading(true);
    try {
      const data = await api.loadSample();
      navigate(`/investigations/${data.investigation_id}`);
    } catch (err) {
      console.error(err);
    } finally {
      setSampleLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-white">
      <Header />

      <main className="flex-1 max-w-6xl w-full mx-auto px-8 py-10 space-y-12">
        {/* Hero Section */}
        <div className="text-center max-w-3xl mx-auto space-y-4 pt-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-[#3156D9] text-xs font-medium">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Agentic Cross-Paper Evidence Verification</span>
          </div>
          
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#202124] leading-tight">
            Investigate the evidence behind research.
          </h1>
          
          <p className="text-base text-[#667085] leading-relaxed max-w-2xl mx-auto">
            Compare research papers, trace claims to source passages, and discover where findings agree, differ, or remain uncertain.
          </p>

          <div className="flex items-center justify-center gap-3 pt-2">
            <Link
              to="/new"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold bg-[#3156D9] hover:bg-[#2546B8] text-white shadow-xs transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              Start an investigation
            </Link>
            <button
              onClick={handleOpenSample}
              disabled={sampleLoading}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold bg-white hover:bg-gray-50 text-[#202124] border border-[#E5E7EB] shadow-xs transition-colors cursor-pointer"
            >
              <Sparkles className="w-4 h-4 text-[#3156D9]" />
              {sampleLoading ? 'Loading Sample...' : 'Explore a sample report'}
            </button>
          </div>
        </div>

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-5 rounded-xl border border-[#E5E7EB] bg-[#F8F9FB]/50 flex flex-col justify-between">
            <span className="text-xs font-medium text-[#667085]">Research Papers</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-[#202124]">{papers.length}</span>
              <span className="text-xs text-[#16803C] font-medium">Indexed</span>
            </div>
          </div>

          <div className="p-5 rounded-xl border border-[#E5E7EB] bg-[#F8F9FB]/50 flex flex-col justify-between">
            <span className="text-xs font-medium text-[#667085]">Investigations</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-[#202124]">{investigations.length}</span>
              <span className="text-xs text-[#3156D9] font-medium">Completed</span>
            </div>
          </div>

          <div className="p-5 rounded-xl border border-[#E5E7EB] bg-[#F8F9FB]/50 flex flex-col justify-between">
            <span className="text-xs font-medium text-[#667085]">Citation Verification</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-[#16803C]">100%</span>
              <span className="text-xs text-[#667085]">Grounded</span>
            </div>
          </div>

          <div className="p-5 rounded-xl border border-[#E5E7EB] bg-[#F8F9FB]/50 flex flex-col justify-between">
            <span className="text-xs font-medium text-[#667085]">AI Orchestrator</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-sm font-bold text-[#202124]">
                {health?.has_gemini ? 'Gemini 2.0' : 'Deterministic'}
              </span>
              <span className="text-[11px] text-[#16803C] font-medium">Ready</span>
            </div>
          </div>
        </div>

        {/* How It Works Pipeline Diagram */}
        <div className="border border-[#E5E7EB] rounded-xl p-6 bg-white shadow-xs">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-base font-semibold text-[#202124] m-0">
                Rigorous Evidence Investigation Pipeline
              </h2>
              <p className="text-xs text-[#667085] mt-0.5">
                Evidex prioritizes verifiable document passages over uncalibrated AI summaries.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            {[
              {
                step: '01',
                title: 'PDF Page Extraction',
                desc: 'PyMuPDF extracts raw text preserving exact page coordinates and chunk boundaries.',
              },
              {
                step: '02',
                title: 'Relevance Ranking',
                desc: 'BM25 and semantic scoring rank papers with honest explanations of query alignment.',
              },
              {
                step: '03',
                title: 'Claim Extraction',
                desc: 'Isolates author-reported findings, methodologies, and limitations from background text.',
              },
              {
                step: '04',
                title: 'Cross-Paper Comparison',
                desc: 'Maps datasets, metrics, and detects potential disagreements or boundary conditions.',
              },
              {
                step: '05',
                title: 'Citation Validation',
                desc: 'Verifies every citation reference against extracted document text before finalizing.',
              },
            ].map((s) => (
              <div key={s.step} className="p-4 rounded-lg bg-[#F8F9FB] border border-[#E5E7EB] flex flex-col justify-between">
                <div>
                  <span className="text-xs font-mono font-bold text-[#3156D9]">{s.step}</span>
                  <h4 className="text-xs font-semibold text-[#202124] mt-1 mb-1">{s.title}</h4>
                  <p className="text-[11px] text-[#667085] leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Investigations & Papers Split */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Recent Investigations */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[#202124] flex items-center gap-2">
                <Layers className="w-4 h-4 text-[#3156D9]" />
                Recent Investigations
              </h3>
              <Link to="/investigations" className="text-xs font-medium text-[#3156D9] hover:underline flex items-center gap-1">
                View all <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {loading ? (
              <div className="p-8 text-center text-xs text-[#667085] border border-[#E5E7EB] rounded-xl">
                Loading investigations...
              </div>
            ) : investigations.length === 0 ? (
              <EmptyState
                icon={Layers}
                title="No investigations yet"
                description="Upload papers and ask a research question to generate your first cited investigation report."
                actionText="Start Investigation"
                onAction={() => navigate('/new')}
              />
            ) : (
              <div className="border border-[#E5E7EB] rounded-xl divide-y divide-[#E5E7EB] overflow-hidden bg-white shadow-xs">
                {investigations.slice(0, 4).map((inv) => (
                  <Link
                    key={inv.id}
                    to={`/investigations/${inv.id}`}
                    className="p-4 hover:bg-[#F8F9FB] transition-colors block group"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1 flex-1">
                        <h4 className="text-sm font-medium text-[#202124] group-hover:text-[#3156D9] transition-colors line-clamp-2">
                          {inv.research_question}
                        </h4>
                        <div className="flex items-center gap-3 text-xs text-[#667085]">
                          <span>{inv.paper_ids.length} paper(s)</span>
                          <span>&bull;</span>
                          <span>{new Date(inv.created_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                      <span className="shrink-0 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-[#16803C] border border-emerald-200">
                        {inv.status}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Research Library Papers */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[#202124] flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-[#3156D9]" />
                Research Library
              </h3>
              <Link to="/library" className="text-xs font-medium text-[#3156D9] hover:underline flex items-center gap-1">
                Manage library <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {loading ? (
              <div className="p-8 text-center text-xs text-[#667085] border border-[#E5E7EB] rounded-xl">
                Loading library...
              </div>
            ) : papers.length === 0 ? (
              <EmptyState
                icon={BookOpen}
                title="Library is empty"
                description="Upload PDFs to begin indexing research papers for cross-document analysis."
                actionText="Upload Paper"
                onAction={() => navigate('/library')}
              />
            ) : (
              <div className="border border-[#E5E7EB] rounded-xl divide-y divide-[#E5E7EB] overflow-hidden bg-white shadow-xs">
                {papers.slice(0, 4).map((p) => (
                  <div key={p.id} className="p-4 hover:bg-[#F8F9FB] transition-colors flex items-center justify-between gap-3">
                    <div className="space-y-1 min-w-0">
                      <h4 className="text-sm font-medium text-[#202124] truncate">
                        {p.title || p.original_filename}
                      </h4>
                      <div className="flex items-center gap-2 text-xs text-[#667085]">
                        <span className="truncate max-w-[200px]">{p.authors || 'Authors unlisted'}</span>
                        <span>&bull;</span>
                        <span>{p.page_count} pages</span>
                        <span>&bull;</span>
                        <span>{Math.round(p.file_size / 1024)} KB</span>
                      </div>
                    </div>
                    <span className="text-xs text-[#667085] font-mono shrink-0">
                      {p.year || 'N/A'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};
