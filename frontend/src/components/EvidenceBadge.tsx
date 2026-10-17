import React from 'react';
import { EvidenceRelationship } from '../types';
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle, ArrowRightLeft, FileCheck } from 'lucide-react';

interface Props {
  relationship: EvidenceRelationship;
  size?: 'sm' | 'md';
  className?: string;
}

export const EvidenceBadge: React.FC<Props> = ({ relationship, size = 'md', className = '' }) => {
  const getBadgeConfig = (rel: EvidenceRelationship) => {
    switch (rel) {
      case 'supported_by_document':
        return {
          label: 'Supported by document',
          bg: 'bg-emerald-50 text-emerald-800 border-emerald-200',
          icon: <CheckCircle2 className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5 text-emerald-600'} />,
        };
      case 'partially_supports':
        return {
          label: 'Partially supported',
          bg: 'bg-amber-50 text-amber-800 border-amber-200',
          icon: <AlertTriangle className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5 text-amber-600'} />,
        };
      case 'potentially_conflicting_evidence':
        return {
          label: 'Potentially conflicting',
          bg: 'bg-rose-50 text-rose-800 border-rose-200',
          icon: <AlertTriangle className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5 text-rose-600'} />,
        };
      case 'unsupported_in_available_document':
        return {
          label: 'Unsupported in document',
          bg: 'bg-red-50 text-red-800 border-red-200',
          icon: <XCircle className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5 text-red-600'} />,
        };
      case 'insufficient_information':
        return {
          label: 'Insufficient information',
          bg: 'bg-slate-50 text-slate-700 border-slate-200',
          icon: <HelpCircle className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5 text-slate-500'} />,
        };
      case 'not_directly_comparable':
        return {
          label: 'Not directly comparable',
          bg: 'bg-stone-50 text-stone-700 border-stone-200',
          icon: <ArrowRightLeft className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5 text-stone-500'} />,
        };
      default:
        return {
          label: rel,
          bg: 'bg-gray-50 text-gray-700 border-gray-200',
          icon: <HelpCircle className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5 text-gray-500'} />,
        };
    }
  };

  const config = getBadgeConfig(relationship);
  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5 gap-1' : 'text-xs px-2.5 py-1 gap-1.5';

  return (
    <span
      className={`inline-flex items-center font-medium border rounded-md ${config.bg} ${sizeClasses} ${className}`}
      title={`Evidence relationship: ${config.label}`}
    >
      {config.icon}
      <span>{config.label}</span>
    </span>
  );
};

export const ReferenceBadge: React.FC<{ valid: boolean; page?: number; size?: 'sm' | 'md' }> = ({
  valid,
  page,
  size = 'md',
}) => {
  const sizeClasses = size === 'sm' ? 'text-[11px] px-2 py-0.5 gap-1' : 'text-xs px-2.5 py-1 gap-1.5';
  if (valid) {
    return (
      <span
        className={`inline-flex items-center font-medium rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200 ${sizeClasses}`}
        title="Passage existence verified against extracted document page text."
      >
        <FileCheck className={size === 'sm' ? 'w-3 h-3 text-emerald-600' : 'w-3.5 h-3.5 text-emerald-600'} />
        <span>Reference verified{page ? ` (p. ${page})` : ''}</span>
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center font-medium rounded-md bg-amber-50 text-amber-800 border border-amber-200 ${sizeClasses}`}
      title="Passage could not be strictly located on specified page."
    >
      <AlertTriangle className={size === 'sm' ? 'w-3 h-3 text-amber-600' : 'w-3.5 h-3.5 text-amber-600'} />
      <span>Reference unverified</span>
    </span>
  );
};

export const SupportBadge: React.FC<{
  status?: 'supports' | 'partially_supports' | 'contradicts' | 'unsupported' | string;
  relationship?: EvidenceRelationship;
  size?: 'sm' | 'md';
}> = ({ status, relationship, size = 'md' }) => {
  const sizeClasses = size === 'sm' ? 'text-[11px] px-2 py-0.5 gap-1' : 'text-xs px-2.5 py-1 gap-1.5';

  const effectiveStatus =
    status ||
    (relationship === 'supported_by_document'
      ? 'supports'
      : relationship === 'partially_supports'
      ? 'partially_supports'
      : relationship === 'potentially_conflicting_evidence'
      ? 'contradicts'
      : 'unsupported');

  switch (effectiveStatus) {
    case 'supports':
    case 'supported':
      return (
        <span
          className={`inline-flex items-center font-medium rounded-md bg-blue-50 text-blue-800 border border-blue-200 ${sizeClasses}`}
          title="Evidence passage semantically confirms the associated claim."
        >
          <CheckCircle2 className={size === 'sm' ? 'w-3 h-3 text-blue-600' : 'w-3.5 h-3.5 text-blue-600'} />
          <span>Support confirmed</span>
        </span>
      );
    case 'partially_supports':
    case 'partially_supported':
      return (
        <span
          className={`inline-flex items-center font-medium rounded-md bg-indigo-50 text-indigo-800 border border-indigo-200 ${sizeClasses}`}
          title="Evidence addresses the general subject matter with partial confirmation."
        >
          <AlertTriangle className={size === 'sm' ? 'w-3 h-3 text-indigo-600' : 'w-3.5 h-3.5 text-indigo-600'} />
          <span>Partially supports</span>
        </span>
      );
    case 'contradicts':
    case 'contradicted':
      return (
        <span
          className={`inline-flex items-center font-medium rounded-md bg-rose-50 text-rose-800 border border-rose-200 ${sizeClasses}`}
          title="Evidence presents contradictory findings or boundary limitations."
        >
          <XCircle className={size === 'sm' ? 'w-3 h-3 text-rose-600' : 'w-3.5 h-3.5 text-rose-600'} />
          <span>Contradicts claim</span>
        </span>
      );
    default:
      return (
        <span
          className={`inline-flex items-center font-medium rounded-md bg-amber-50 text-amber-800 border border-amber-200 ${sizeClasses}`}
          title="Passage does not establish or confirm the associated claim."
        >
          <AlertTriangle className={size === 'sm' ? 'w-3 h-3 text-amber-600' : 'w-3.5 h-3.5 text-amber-600'} />
          <span>Insufficient support</span>
        </span>
      );
  }
};
