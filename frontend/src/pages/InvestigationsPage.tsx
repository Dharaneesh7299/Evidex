import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Layers,
  PlusCircle,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Calendar,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { api } from '../services/api';
import { InvestigationSummary } from '../types';
import { Header } from '../components/Header';
import { EmptyState } from '../components/EmptyState';

export const InvestigationsPage: React.FC = () => {
  const navigate = useNavigate();
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    api
      .listInvestigations()
      .then(setInvestigations)
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex-1 flex flex-col bg-white">
      <Header
        title="Research Investigations"
        subtitle="Chronological archive of all multi-document research inquiries and evidence reports."
      />

      <main className="flex-1 max-w-6xl w-full mx-auto px-8 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-[#202124] m-0">All Investigations</h2>
            <p className="text-xs text-[#667085] mt-0.5">
              Review conclusions, verify citations, or start a new inquiry.
            </p>
          </div>

          <Link
            to="/new"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#3156D9] hover:bg-[#2546B8] text-white text-xs font-medium rounded-lg shadow-2xs transition-colors"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            New Investigation
          </Link>
        </div>

        {loading ? (
          <div className="p-12 text-center text-xs text-[#667085] border border-[#E5E7EB] rounded-xl">
            Loading investigations history...
          </div>
        ) : investigations.length === 0 ? (
          <EmptyState
            icon={Layers}
            title="No investigations conducted yet"
            description="Start by formulating a research question across your uploaded PDF papers."
            actionText="Start Investigation"
            onAction={() => navigate('/new')}
          />
        ) : (
          <div className="border border-[#E5E7EB] rounded-xl divide-y divide-[#E5E7EB] overflow-hidden bg-white shadow-2xs">
            {investigations.map((inv) => (
              <Link
                key={inv.id}
                to={`/investigations/${inv.id}`}
                className="p-5 hover:bg-[#F8F9FB] transition-colors flex items-center justify-between gap-4 group block"
              >
                <div className="space-y-1.5 min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-[#667085]">{inv.id}</span>
                    <span className="text-gray-300">&bull;</span>
                    <span className="text-xs text-[#667085]">
                      {new Date(inv.created_at).toLocaleDateString()} at{' '}
                      {new Date(inv.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>

                  <h3 className="text-sm font-semibold text-[#202124] group-hover:text-[#3156D9] transition-colors line-clamp-2">
                    {inv.research_question}
                  </h3>

                  <div className="flex items-center gap-3 text-xs text-[#667085]">
                    <span>{inv.paper_ids.length} Research Paper(s)</span>
                    <span>&bull;</span>
                    <span>Stage: {inv.stage}</span>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <span
                    className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${
                      inv.status === 'completed'
                        ? 'bg-emerald-50 text-[#16803C] border-emerald-200'
                        : inv.status === 'failed'
                        ? 'bg-red-50 text-[#B42318] border-red-200'
                        : 'bg-blue-50 text-[#3156D9] border-blue-200'
                    }`}
                  >
                    {inv.status === 'completed' ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-[#16803C]" />
                    ) : (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    )}
                    {inv.status.toUpperCase()}
                  </span>

                  <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-gray-600 group-hover:translate-x-0.5 transition-all" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};
