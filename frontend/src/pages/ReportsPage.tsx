import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  Download,
  Copy,
  ExternalLink,
  ShieldCheck,
  Check,
  Search,
  BookOpen,
} from 'lucide-react';
import { api } from '../services/api';
import { InvestigationSummary } from '../types';
import { Header } from '../components/Header';
import { EmptyState } from '../components/EmptyState';

export const ReportsPage: React.FC = () => {
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    api
      .listInvestigations()
      .then((data) => setInvestigations(data.filter((i) => i.status === 'completed')))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  const handleCopyMarkdown = async (invId: string) => {
    try {
      const rep = await api.getInvestigationReport(invId);
      navigator.clipboard.writeText(rep.markdown);
      setCopiedId(invId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error('Failed to copy report:', err);
    }
  };

  const handleDownloadMarkdown = async (invId: string) => {
    try {
      const rep = await api.getInvestigationReport(invId);
      const blob = new Blob([rep.markdown], { type: 'text/markdown;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `evidex_report_${invId}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download report:', err);
    }
  };

  const filtered = investigations.filter((i) =>
    i.research_question.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex-1 flex flex-col bg-white">
      <Header
        title="Synthesized Research Reports"
        subtitle="Export, print, and share verifiable multi-paper evidence synthesis documents."
      />

      <main className="flex-1 max-w-6xl w-full mx-auto px-8 py-8 space-y-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search reports by question..."
              className="w-full pl-9 pr-4 py-2 text-xs bg-white border border-[#E5E7EB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3156D9]/20 focus:border-[#3156D9]"
            />
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center text-xs text-[#667085] border border-[#E5E7EB] rounded-xl">
            Loading finalized research reports...
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No completed reports yet"
            description="Run an investigation to generate structured, citation-validated reports."
            actionText="Start Investigation"
            onAction={() => (window.location.href = '/new')}
          />
        ) : (
          <div className="border border-[#E5E7EB] rounded-xl divide-y divide-[#E5E7EB] overflow-hidden bg-white shadow-2xs">
            {filtered.map((inv) => (
              <div
                key={inv.id}
                className="p-5 hover:bg-[#F8F9FB]/50 transition-colors flex items-center justify-between gap-4"
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-emerald-50 text-[#16803C] px-2 py-0.5 rounded border border-emerald-200">
                      <ShieldCheck className="w-3.5 h-3.5 text-[#16803C]" />
                      Verified Report
                    </span>
                    <span className="text-gray-300">&bull;</span>
                    <span className="text-xs text-[#667085]">{new Date(inv.created_at).toLocaleDateString()}</span>
                  </div>

                  <Link
                    to={`/investigations/${inv.id}`}
                    className="text-sm font-semibold text-[#202124] hover:text-[#3156D9] transition-colors block line-clamp-1"
                  >
                    {inv.research_question}
                  </Link>

                  <p className="text-xs text-[#667085]">
                    Synthesizes evidence from {inv.paper_ids.length} research paper(s).
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleCopyMarkdown(inv.id)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium border border-[#E5E7EB] bg-white hover:bg-gray-50 rounded-lg text-gray-700 shadow-2xs cursor-pointer"
                    title="Copy Markdown"
                  >
                    {copiedId === inv.id ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                    {copiedId === inv.id ? 'Copied' : 'Copy'}
                  </button>

                  <button
                    onClick={() => handleDownloadMarkdown(inv.id)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium border border-[#E5E7EB] bg-white hover:bg-gray-50 rounded-lg text-gray-700 shadow-2xs cursor-pointer"
                    title="Download .md file"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download .md
                  </button>

                  <Link
                    to={`/investigations/${inv.id}`}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-[#3156D9] hover:bg-[#2546B8] text-white rounded-lg shadow-2xs transition-colors"
                  >
                    View Report <ExternalLink className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};
