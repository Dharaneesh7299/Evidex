import React, { useEffect, useState } from 'react';
import { X, CheckCircle2, AlertCircle, Copy, Check, FileText, ExternalLink } from 'lucide-react';
import { api } from '../services/api';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  paperId: string;
  paperTitle?: string;
  pageNumber: number;
  highlightPassage?: string;
  validated?: boolean;
}

export const PassageViewerModal: React.FC<Props> = ({
  isOpen,
  onClose,
  paperId,
  paperTitle,
  pageNumber,
  highlightPassage = '',
  validated = true,
}) => {
  const [pageText, setPageText] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen && paperId && pageNumber) {
      setLoading(true);
      setError(null);
      api
        .getPaperPage(paperId, pageNumber)
        .then((data) => {
          setPageText(data.text);
          setLoading(false);
        })
        .catch((err) => {
          setError(err.message || 'Could not load page text');
          setLoading(false);
        });
    }
  }, [isOpen, paperId, pageNumber]);

  if (!isOpen) return null;

  const handleCopy = () => {
    const textToCopy = highlightPassage || pageText;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div
        className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-3xl overflow-hidden flex flex-col max-h-[85vh] animate-in fade-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50/50">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center text-[#3156D9]">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-gray-900 leading-tight">
                Source Document Passage
              </h3>
              <p className="text-xs text-gray-500 truncate max-w-md">
                {paperTitle || paperId} &bull; Page {pageNumber}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {validated ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-800 border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                Reference verified
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
                <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                Reference unverified
              </span>
            )}
            <button
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
              aria-label="Close dialog"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Content */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {/* Highlighted Cited Passage Box */}
          {highlightPassage && (
            <div className="bg-amber-50/50 border border-amber-200/80 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-amber-900">
                  Exact Cited Passage
                </span>
                <button
                  onClick={handleCopy}
                  className="inline-flex items-center gap-1 text-xs text-amber-800 hover:text-amber-950 font-medium cursor-pointer"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? 'Copied' : 'Copy Passage'}
                </button>
              </div>
              <blockquote className="text-sm text-gray-900 leading-relaxed font-serif italic pl-3 border-l-2 border-amber-400">
                "{highlightPassage}"
              </blockquote>
            </div>
          )}

          {/* Full Page Context */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                Full Page {pageNumber} Text Context
              </h4>
              <span className="text-xs text-gray-400">PyMuPDF Extracted</span>
            </div>

            {loading ? (
              <div className="h-48 flex items-center justify-center text-sm text-gray-500 border border-dashed border-gray-200 rounded-lg">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                  Loading document page text...
                </div>
              </div>
            ) : error ? (
              <div className="p-4 bg-red-50 text-red-700 text-sm rounded-lg border border-red-200">
                {error}
              </div>
            ) : (
              <div className="bg-gray-50/80 border border-gray-200 rounded-lg p-4 text-xs font-mono text-gray-800 leading-relaxed whitespace-pre-wrap max-h-72 overflow-y-auto select-text">
                {pageText || 'No text extracted from this page.'}
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-gray-200 bg-gray-50 flex items-center justify-between text-xs text-gray-500">
          <p>
            Evidence citations in Evidex are verified against page text indices.
          </p>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-white border border-gray-300 text-gray-700 rounded-md font-medium hover:bg-gray-50 transition-colors shadow-xs"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
