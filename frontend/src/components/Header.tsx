import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { PlusCircle, Sparkles, BookOpen, Layers } from 'lucide-react';
import { api } from '../services/api';

interface Props {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export const Header: React.FC<Props> = ({ title, subtitle, action }) => {
  const navigate = useNavigate();
  const [loadingSample, setLoadingSample] = React.useState(false);

  const handleOpenSample = async () => {
    setLoadingSample(true);
    try {
      const data = await api.loadSample();
      navigate(`/investigations/${data.investigation_id}`);
    } catch (err) {
      console.error('Failed to load sample:', err);
    } finally {
      setLoadingSample(false);
    }
  };

  return (
    <header className="h-16 border-b border-[#E5E7EB] bg-white px-8 flex items-center justify-between shrink-0 sticky top-0 z-20">
      <div>
        {title && <h1 className="text-lg font-semibold text-[#202124] leading-tight m-0">{title}</h1>}
        {subtitle && <p className="text-xs text-[#667085] leading-normal">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-3">
        {action}
        <button
          onClick={handleOpenSample}
          disabled={loadingSample}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-50 hover:bg-gray-100 text-gray-700 border border-[#E5E7EB] transition-colors cursor-pointer"
          title="Open grounded demo report with 3 research papers"
        >
          <Sparkles className="w-3.5 h-3.5 text-[#3156D9]" />
          {loadingSample ? 'Loading Demo...' : 'Explore Sample Report'}
        </button>

        <Link
          to="/new"
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-[#3156D9] hover:bg-[#2546B8] text-white shadow-xs transition-colors"
        >
          <PlusCircle className="w-3.5 h-3.5" />
          New Investigation
        </Link>
      </div>
    </header>
  );
};
