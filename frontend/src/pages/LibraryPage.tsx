import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BookOpen,
  Upload,
  Search,
  Trash2,
  ExternalLink,
  PlusCircle,
  FileText,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Calendar,
  Layers,
} from 'lucide-react';
import { api } from '../services/api';
import { Paper } from '../types';
import { Header } from '../components/Header';
import { EmptyState } from '../components/EmptyState';
import { PassageViewerModal } from '../components/PassageViewerModal';

export const LibraryPage: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);

  // Modal State
  const [viewerOpen, setViewerOpen] = useState<boolean>(false);
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null);

  const loadPapers = () => {
    setLoading(true);
    api
      .listPapers()
      .then(setPapers)
      .catch((err) => setError(err.message || 'Failed to load papers'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadPapers();
  }, []);

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setError(null);
    setUploading(true);

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setError('Only PDF documents are supported.');
        setUploading(false);
        return;
      }
      try {
        await api.uploadPaper(file);
      } catch (err: any) {
        setError(err.message || `Failed to upload ${file.name}`);
      }
    }

    setUploading(false);
    loadPapers();
  };

  const handleDeletePaper = async (paperId: string) => {
    if (!window.confirm('Are you sure you want to delete this paper and its extracted chunks?')) return;
    try {
      await api.deletePaper(paperId);
      setPapers((prev) => prev.filter((p) => p.id !== paperId));
    } catch (err: any) {
      setError(err.message || 'Failed to delete paper');
    }
  };

  const handleOpenPageViewer = (paper: Paper) => {
    setSelectedPaper(paper);
    setViewerOpen(true);
  };

  const filteredPapers = papers.filter((p) => {
    const q = searchQuery.toLowerCase();
    const titleMatch = (p.title || p.original_filename).toLowerCase().includes(q);
    const authorMatch = (p.authors || '').toLowerCase().includes(q);
    return titleMatch || authorMatch;
  });

  return (
    <div className="flex-1 flex flex-col bg-white">
      <Header
        title="Research Document Library"
        subtitle="Manage indexed papers, verify extracted page text, and inspect bibliographic metadata."
      />

      <main className="flex-1 max-w-6xl w-full mx-auto px-8 py-8 space-y-6">
        {/* Alerts */}
        {error && (
          <div className="p-4 rounded-lg bg-red-50 border border-red-200 flex items-center justify-between text-red-800 text-sm">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
              &times;
            </button>
          </div>
        )}

        {/* Action & Search Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by title, author, or keyword..."
              className="w-full pl-9 pr-4 py-2 text-xs bg-white border border-[#E5E7EB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3156D9]/20 focus:border-[#3156D9]"
            />
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={(e) => handleFileUpload(e.target.files)}
            />

            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-white hover:bg-gray-50 border border-[#E5E7EB] text-gray-700 text-xs font-medium rounded-lg shadow-2xs transition-colors cursor-pointer"
            >
              {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin text-[#3156D9]" /> : <Upload className="w-3.5 h-3.5" />}
              {uploading ? 'Processing PDF...' : 'Upload PDF'}
            </button>

            <button
              onClick={() => navigate('/new')}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#3156D9] hover:bg-[#2546B8] text-white text-xs font-medium rounded-lg shadow-2xs transition-colors cursor-pointer"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              Investigate Papers
            </button>
          </div>
        </div>

        {/* Papers Table */}
        {loading ? (
          <div className="p-12 text-center text-xs text-[#667085] border border-[#E5E7EB] rounded-xl">
            Loading research papers...
          </div>
        ) : filteredPapers.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title={searchQuery ? 'No papers matched your search' : 'No research papers uploaded'}
            description={
              searchQuery
                ? 'Try adjusting your search terms or view all documents.'
                : 'Upload PDFs to extract text, preserve page numbers, and index content for investigations.'
            }
            actionText="Upload First Paper"
            onAction={() => fileInputRef.current?.click()}
          />
        ) : (
          <div className="border border-[#E5E7EB] rounded-xl overflow-hidden bg-white shadow-2xs">
            <table className="w-full text-left text-xs text-gray-800">
              <thead className="bg-[#F8F9FB] border-b border-[#E5E7EB] text-[#667085] font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3">Paper Title & Authors</th>
                  <th className="px-4 py-3">Year</th>
                  <th className="px-4 py-3">Pages</th>
                  <th className="px-4 py-3">Size</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E7EB]">
                {filteredPapers.map((paper) => (
                  <tr key={paper.id} className="hover:bg-[#F8F9FB]/50 transition-colors">
                    <td className="px-5 py-3.5 max-w-md">
                      <div className="font-semibold text-[#202124] text-xs">
                        {paper.title || paper.original_filename}
                      </div>
                      <div className="text-[11px] text-[#667085] truncate mt-0.5">
                        {paper.authors || 'Authors not identified in header'}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-gray-600">{paper.year || 'N/A'}</td>
                    <td className="px-4 py-3.5 text-gray-600">{paper.page_count} pages</td>
                    <td className="px-4 py-3.5 font-mono text-gray-600">
                      {Math.round(paper.file_size / 1024)} KB
                    </td>
                    <td className="px-4 py-3.5">
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-emerald-50 text-[#16803C] px-2 py-0.5 rounded border border-emerald-200">
                        <CheckCircle2 className="w-3 h-3 text-[#16803C]" />
                        Ready
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-right space-x-2">
                      <button
                        onClick={() => handleOpenPageViewer(paper)}
                        className="p-1.5 text-[#3156D9] hover:bg-blue-50 rounded transition-colors cursor-pointer inline-flex items-center gap-1"
                        title="View extracted page text"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        <span className="text-xs">View</span>
                      </button>

                      <button
                        onClick={() => handleDeletePaper(paper.id)}
                        className="p-1.5 text-gray-400 hover:text-red-600 rounded transition-colors cursor-pointer"
                        title="Delete paper"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {/* Page Viewer Modal */}
      {selectedPaper && (
        <PassageViewerModal
          isOpen={viewerOpen}
          onClose={() => setViewerOpen(false)}
          paperId={selectedPaper.id}
          paperTitle={selectedPaper.title || selectedPaper.original_filename}
          pageNumber={1}
          highlightPassage=""
          validated={true}
        />
      )}
    </div>
  );
};
