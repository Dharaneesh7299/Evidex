import React, { useEffect, useState } from 'react';
import {
  Settings,
  ShieldCheck,
  Sparkles,
  Database,
  FileText,
  Lock,
  CheckCircle2,
  AlertTriangle,
  Server,
} from 'lucide-react';
import { api } from '../services/api';
import { SystemHealth } from '../types';
import { Header } from '../components/Header';

export const SettingsPage: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    api
      .getHealth()
      .then(setHealth)
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex-1 flex flex-col bg-white">
      <Header
        title="System Settings & Diagnostics"
        subtitle="Inspect runtime configuration, API integrations, and evidence verification parameters."
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-8 py-8 space-y-8">
        {/* System Diagnostics */}
        <div className="border border-[#E5E7EB] rounded-xl p-6 bg-white shadow-2xs space-y-6">
          <div className="flex items-center gap-3 border-b border-[#E5E7EB] pb-4">
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-[#3156D9] flex items-center justify-center">
              <Server className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#202124] leading-tight">Backend & AI Engine Status</h3>
              <p className="text-xs text-[#667085]">Evidex orchestration service diagnostic report</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="p-4 rounded-lg bg-[#F8F9FB] border border-[#E5E7EB] space-y-1">
              <span className="text-[#667085]">Service Health:</span>
              <div className="flex items-center gap-2 font-semibold text-gray-900">
                <span className="w-2 h-2 rounded-full bg-[#16803C]" />
                {health?.status === 'ok' ? 'Online & Healthy' : 'Initializing'}
              </div>
            </div>

            <div className="p-4 rounded-lg bg-[#F8F9FB] border border-[#E5E7EB] space-y-1">
              <span className="text-[#667085]">Gemini AI Model:</span>
              <div className="flex items-center gap-2 font-semibold text-gray-900">
                {health?.has_gemini ? (
                  <span className="text-blue-700 flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5 text-[#3156D9]" />
                    {health.gemini_model} (Active)
                  </span>
                ) : (
                  <span className="text-gray-700">Deterministic Offline Engine</span>
                )}
              </div>
            </div>

            <div className="p-4 rounded-lg bg-[#F8F9FB] border border-[#E5E7EB] space-y-1">
              <span className="text-[#667085]">Indexed Research Papers:</span>
              <div className="font-semibold text-gray-900 text-sm">
                {health?.papers_count ?? 0} papers
              </div>
            </div>

            <div className="p-4 rounded-lg bg-[#F8F9FB] border border-[#E5E7EB] space-y-1">
              <span className="text-[#667085]">Synthesized Investigations:</span>
              <div className="font-semibold text-gray-900 text-sm">
                {health?.investigations_count ?? 0} completed
              </div>
            </div>
          </div>
        </div>

        {/* Responsible AI & Evidence Policy */}
        <div className="border border-[#E5E7EB] rounded-xl p-6 bg-white shadow-2xs space-y-4">
          <div className="flex items-center gap-3 border-b border-[#E5E7EB] pb-4">
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-[#16803C] flex items-center justify-center">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#202124] leading-tight">Evidence Verification Principles</h3>
              <p className="text-xs text-[#667085]">Strict guidelines enforced during every investigation</p>
            </div>
          </div>

          <div className="space-y-3 text-xs text-gray-700 leading-relaxed">
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-[#16803C] shrink-0 mt-0.5" />
              <p>
                <strong>Zero Hallucinated Citations:</strong> Every factual statement must cite a specific paper and page number. If an unverified assertion is detected, it is marked as unverified or rejected.
              </p>
            </div>

            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-[#16803C] shrink-0 mt-0.5" />
              <p>
                <strong>Untrusted PDF Input:</strong> Uploaded papers are treated as raw untrusted data. Embedded instructions attempting prompt injection or behavior override are strictly ignored.
              </p>
            </div>

            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-[#16803C] shrink-0 mt-0.5" />
              <p>
                <strong>Accurate Uncertainty:</strong> Evidex distinguishes between what a paper reports and scientific truth. Missing mentions are labeled "insufficient information" rather than assumed false.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};
