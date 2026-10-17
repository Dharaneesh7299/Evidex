import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload,
  FileText,
  Trash2,
  Play,
  CheckCircle2,
  Loader2,
  AlertCircle,
  HelpCircle,
  Sparkles,
  BookOpen,
  ArrowRight,
  ShieldCheck,
  Check,
} from 'lucide-react';
import { api } from '../services/api';
import { Paper, InvestigationStatus } from '../types';
import { Header } from '../components/Header';

const PRESET_QUESTIONS = [
  'Does this technique consistently improve classification accuracy across different datasets, and what limitations affect the findings?',
  'How do vision transformer architectures compare with convolutional baselines for medical lesion diagnosis?',
  'What are the primary reported causes of out-of-distribution performance drops across clinical centers?',
  'Does diffusion-based synthetic data augmentation prevent model degradation in low-label histopathology regimes?',
];

const PIPELINE_STAGES = [
  { key: 'queued', label: 'Queued & input validation' },
  { key: 'preparing_documents', label: 'Extracting text & preserving page numbers' },
  { key: 'analyzing_relevance', label: 'Ranking paper relevance & topical overlap' },
  { key: 'extracting_claims', label: 'Extracting reported claims & findings' },
  { key: 'retrieving_evidence', label: 'Retrieving & checking supporting passages' },
  { key: 'comparing_findings', label: 'Comparing cross-paper methods & boundaries' },
  { key: 'validating_report', label: 'Validating citations & compiling report' },
  { key: 'completed', label: 'Investigation report finalized' },
];

export const NewInvestigationPage: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [question, setQuestion] = useState<string>(PRESET_QUESTIONS[0]);
  const [availablePapers, setAvailablePapers] = useState<Paper[]>([]);
  const [selectedPaperIds, setSelectedPaperIds] = useState<string[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<{ name: string; size: number; progress: number }[]>([]);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Investigation Execution State
  const [investigationId, setInvestigationId] = useState<string | null>(null);
  const [invStatus, setInvStatus] = useState<InvestigationStatus | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  useEffect(() => {
    // Load existing papers from library
    api.listPapers().then((papers) => {
      setAvailablePapers(papers);
      // Default select all papers (or up to 3)
      if (papers.length > 0) {
        setSelectedPaperIds(papers.slice(0, 3).map((p) => p.id));
      }
    });
  }, []);

  // Poll investigation status if running
  useEffect(() => {
    if (!investigationId) return;

    const interval = setInterval(async () => {
      try {
        const statusData = await api.getInvestigationStatus(investigationId);
        setInvStatus(statusData);

        if (statusData.status === 'completed') {
          clearInterval(interval);
          setTimeout(() => {
            navigate(`/investigations/${investigationId}`);
          }, 800);
        } else if (statusData.status === 'failed') {
          clearInterval(interval);
          setError(statusData.error || 'Investigation processing failed.');
          setIsSubmitting(false);
        }
      } catch (err: any) {
        console.error('Polling error:', err);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [investigationId, navigate]);

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setError(null);

    const validFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setError('Only PDF documents are supported.');
        return;
      }
      if (file.size > 26 * 1024 * 1024) {
        setError(`File ${file.name} exceeds 25 MB size limit.`);
        return;
      }
      validFiles.push(file);
    }

    // Upload files sequentially
    for (const file of validFiles) {
      setUploadingFiles((prev) => [...prev, { name: file.name, size: file.size, progress: 50 }]);
      try {
        const res = await api.uploadPaper(file);
        setAvailablePapers((prev) => [res.paper, ...prev]);
        setSelectedPaperIds((prev) => [...prev, res.paper.id]);
      } catch (err: any) {
        setError(err.message || `Failed to upload ${file.name}`);
      } finally {
        setUploadingFiles((prev) => prev.filter((f) => f.name !== file.name));
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileUpload(e.dataTransfer.files);
  };

  const togglePaperSelection = (paperId: string) => {
    setSelectedPaperIds((prev) =>
      prev.includes(paperId) ? prev.filter((id) => id !== paperId) : [...prev, paperId]
    );
  };

  const handleDeletePaper = async (paperId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.deletePaper(paperId);
      setAvailablePapers((prev) => prev.filter((p) => p.id !== paperId));
      setSelectedPaperIds((prev) => prev.filter((id) => id !== paperId));
    } catch (err: any) {
      setError(err.message || 'Failed to delete paper');
    }
  };

  const handleStartInvestigation = async () => {
    if (!question.trim() || question.trim().length < 8) {
      setError('Please provide a research question with at least 8 characters.');
      return;
    }
    if (selectedPaperIds.length === 0) {
      setError('Please select or upload at least one research paper.');
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      const summary = await api.createInvestigation({
        research_question: question.trim(),
        paper_ids: selectedPaperIds,
      });
      setInvestigationId(summary.id);
    } catch (err: any) {
      setError(err.message || 'Failed to start investigation');
      setIsSubmitting(false);
    }
  };

  // Find current stage index for progress rendering
  const currentStageIndex = PIPELINE_STAGES.findIndex((s) => s.key === invStatus?.stage);

  return (
    <div className="flex-1 flex flex-col bg-white">
      <Header
        title="New Research Investigation"
        subtitle="Formulate a scientific question and select target papers for evidence extraction."
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-8 py-8 space-y-8">
        {/* Error notification */}
        {error && (
          <div className="p-4 rounded-lg bg-red-50 border border-red-200 flex items-start gap-3 text-red-800 text-sm">
            <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span className="font-semibold">Investigation Notice:</span> {error}
            </div>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
              &times;
            </button>
          </div>
        )}

        {/* Live Execution Modal / Overlay when running */}
        {isSubmitting && (
          <div className="border border-blue-200 bg-blue-50/40 rounded-xl p-6 shadow-sm space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-[#3156D9] text-white flex items-center justify-center">
                  <Loader2 className="w-4 h-4 animate-spin" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-[#202124]">
                    AI Research Orchestrator Investigating...
                  </h3>
                  <p className="text-xs text-[#667085]">
                    {invStatus?.progress || 10}% completed &bull; Status: {invStatus?.status || 'running'}
                  </p>
                </div>
              </div>
              <span className="text-xs font-mono font-medium text-[#3156D9] bg-white px-2.5 py-1 rounded border border-blue-200">
                Stage: {invStatus?.stage || 'queued'}
              </span>
            </div>

            {/* Stage-by-stage Progress List */}
            <div className="space-y-2 border-t border-blue-100 pt-4">
              {PIPELINE_STAGES.map((s, idx) => {
                const isCompleted = idx < currentStageIndex || invStatus?.status === 'completed';
                const isCurrent = idx === currentStageIndex && invStatus?.status !== 'completed';

                return (
                  <div
                    key={s.key}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs transition-colors ${
                      isCurrent
                        ? 'bg-blue-100/60 text-[#3156D9] font-semibold'
                        : isCompleted
                        ? 'text-gray-700 font-medium'
                        : 'text-gray-400'
                    }`}
                  >
                    {isCompleted ? (
                      <CheckCircle2 className="w-4 h-4 text-[#16803C] shrink-0" />
                    ) : isCurrent ? (
                      <Loader2 className="w-4 h-4 text-[#3156D9] animate-spin shrink-0" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-gray-300 flex items-center justify-center text-[10px] text-gray-400 shrink-0">
                        {idx + 1}
                      </div>
                    )}
                    <span>{s.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 1. Research Question Input */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold text-[#202124] flex items-center gap-1.5">
              <span>1. Research Question</span>
              <span className="text-xs font-normal text-[#667085]">(Minimum 8 characters)</span>
            </label>
            <span className="text-xs text-[#667085]">{question.length} / 2000 chars</span>
          </div>

          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={isSubmitting}
            rows={3}
            placeholder="e.g., Does this technique consistently improve classification accuracy across different datasets, and what limitations affect the findings?"
            className="w-full px-4 py-3 text-sm text-[#202124] border border-[#E5E7EB] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#3156D9]/20 focus:border-[#3156D9] transition-all resize-none shadow-2xs"
          />

          {/* Preset Questions Chips */}
          <div className="space-y-1.5">
            <span className="text-xs font-medium text-[#667085] flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-[#3156D9]" />
              Preset Research Inquiries:
            </span>
            <div className="flex flex-wrap gap-2">
              {PRESET_QUESTIONS.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setQuestion(q)}
                  disabled={isSubmitting}
                  className="text-xs text-left px-3 py-1.5 rounded-lg bg-[#F8F9FB] hover:bg-gray-100 text-gray-700 border border-[#E5E7EB] transition-colors cursor-pointer"
                >
                  "{q.slice(0, 75)}..."
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 2. PDF Upload Section */}
        <div className="space-y-3">
          <label className="text-sm font-semibold text-[#202124] block">
            2. Upload Target Research Papers (PDF)
          </label>

          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
              isDragging
                ? 'border-[#3156D9] bg-blue-50/50'
                : 'border-[#E5E7EB] hover:border-gray-400 bg-[#F8F9FB]/30'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              multiple
              className="hidden"
              onChange={(e) => handleFileUpload(e.target.files)}
              disabled={isSubmitting}
            />

            <div className="w-10 h-10 rounded-xl bg-white border border-[#E5E7EB] text-[#3156D9] flex items-center justify-center mx-auto mb-3 shadow-2xs">
              <Upload className="w-5 h-5 stroke-[1.8]" />
            </div>

            <p className="text-sm font-medium text-[#202124]">
              Drag and drop scientific PDFs here, or <span className="text-[#3156D9] underline">browse files</span>
            </p>
            <p className="text-xs text-[#667085] mt-1">
              Accepts text-based PDFs up to 25 MB. Page numbers and coordinates are preserved for citations.
            </p>
          </div>

          {/* Uploading indicator */}
          {uploadingFiles.length > 0 && (
            <div className="space-y-2">
              {uploadingFiles.map((f, i) => (
                <div key={i} className="p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-between text-xs text-blue-900">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-[#3156D9]" />
                    <span className="font-medium">{f.name}</span>
                    <span className="text-blue-600">({Math.round(f.size / 1024)} KB)</span>
                  </div>
                  <span>Extracting text & chunks...</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 3. Paper Selection List */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold text-[#202124] flex items-center gap-2">
              <span>3. Select Papers for Cross-Investigation</span>
              <span className="text-xs font-normal text-[#667085]">
                ({selectedPaperIds.length} of {availablePapers.length} selected)
              </span>
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setSelectedPaperIds(availablePapers.map((p) => p.id))}
                className="text-xs text-[#3156D9] hover:underline"
              >
                Select all
              </button>
              <span className="text-gray-300">|</span>
              <button
                type="button"
                onClick={() => setSelectedPaperIds([])}
                className="text-xs text-[#667085] hover:underline"
              >
                Deselect all
              </button>
            </div>
          </div>

          {availablePapers.length === 0 ? (
            <div className="p-6 border border-[#E5E7EB] rounded-xl text-center text-xs text-[#667085] bg-[#F8F9FB]">
              No papers uploaded yet. Drag and drop PDFs above or use the sample dataset.
            </div>
          ) : (
            <div className="border border-[#E5E7EB] rounded-xl divide-y divide-[#E5E7EB] overflow-hidden bg-white shadow-2xs">
              {availablePapers.map((paper) => {
                const isSelected = selectedPaperIds.includes(paper.id);
                return (
                  <div
                    key={paper.id}
                    onClick={() => togglePaperSelection(paper.id)}
                    className={`p-4 flex items-center justify-between gap-4 cursor-pointer transition-colors ${
                      isSelected ? 'bg-blue-50/30' : 'hover:bg-[#F8F9FB]'
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div
                        className={`w-5 h-5 rounded flex items-center justify-center border transition-colors shrink-0 ${
                          isSelected
                            ? 'bg-[#3156D9] border-[#3156D9] text-white'
                            : 'border-gray-300 bg-white'
                        }`}
                      >
                        {isSelected && <Check className="w-3.5 h-3.5 stroke-[2.5]" />}
                      </div>

                      <div className="min-w-0">
                        <h4 className="text-sm font-medium text-[#202124] truncate">
                          {paper.title || paper.original_filename}
                        </h4>
                        <div className="flex items-center gap-2 text-xs text-[#667085] mt-0.5">
                          <span className="truncate max-w-xs">{paper.authors || 'Authors unlisted'}</span>
                          <span>&bull;</span>
                          <span>{paper.year || 'Year unlisted'}</span>
                          <span>&bull;</span>
                          <span>{paper.page_count} pages</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-xs text-[#667085] font-mono">
                        {Math.round(paper.file_size / 1024)} KB
                      </span>
                      <button
                        type="button"
                        onClick={(e) => handleDeletePaper(paper.id, e)}
                        className="p-1.5 text-gray-400 hover:text-red-600 rounded hover:bg-gray-100 transition-colors"
                        title="Delete paper"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Action Button */}
        <div className="pt-4 border-t border-[#E5E7EB] flex items-center justify-between">
          <p className="text-xs text-[#667085]">
            Every factual conclusion will be checked against extracted source passages.
          </p>

          <button
            onClick={handleStartInvestigation}
            disabled={isSubmitting || selectedPaperIds.length === 0}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-semibold bg-[#3156D9] hover:bg-[#2546B8] disabled:bg-gray-300 text-white shadow-xs transition-colors cursor-pointer"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Processing Investigation...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                Start Investigation
              </>
            )}
          </button>
        </div>
      </main>
    </div>
  );
};
