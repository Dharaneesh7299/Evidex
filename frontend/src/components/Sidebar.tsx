import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  FileSearch,
  BookOpen,
  PlusCircle,
  FileText,
  Settings,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Activity,
  Layers,
  FlaskConical,
} from 'lucide-react';
import { api } from '../services/api';
import { SystemHealth } from '../types';

export const Sidebar: React.FC = () => {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [health, setHealth] = useState<SystemHealth | null>(null);

  useEffect(() => {
    api
      .getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const navItems = [
    { name: 'Overview', path: '/', icon: Activity },
    { name: 'Research Library', path: '/library', icon: BookOpen },
    { name: 'New Investigation', path: '/new', icon: PlusCircle, highlight: true },
    { name: 'Investigations', path: '/investigations', icon: Layers },
    { name: 'Reports', path: '/reports', icon: FileText },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <aside
      className={`bg-white border-r border-[#E5E7EB] flex flex-col transition-all duration-200 select-none z-30 ${
        collapsed ? 'w-16' : 'w-64'
      } shrink-0 min-h-screen sticky top-0`}
    >
      {/* Brand & Wordmark */}
      <div className="h-16 px-4 border-b border-[#E5E7EB] flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 overflow-hidden group">
          <div className="w-8 h-8 rounded-lg bg-[#3156D9] text-white flex items-center justify-center font-bold text-base shadow-xs shrink-0 group-hover:bg-[#2546B8] transition-colors">
            <FlaskConical className="w-4 h-4" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-semibold text-gray-900 tracking-tight text-base leading-tight">
                Evidex
              </span>
              <span className="text-[10px] uppercase font-bold tracking-wider text-[#667085]">
                Research Evidence
              </span>
            </div>
          )}
        </Link>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 py-4 px-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(item.path);

          return (
            <Link
              key={item.name}
              to={item.path}
              title={collapsed ? item.name : undefined}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-blue-50 text-[#3156D9] font-semibold'
                  : item.highlight
                  ? 'text-[#3156D9] hover:bg-blue-50/50'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              <Icon
                className={`w-4 h-4 shrink-0 ${
                  isActive ? 'text-[#3156D9]' : item.highlight ? 'text-[#3156D9]' : 'text-gray-400'
                }`}
              />
              {!collapsed && (
                <span className="truncate flex-1">{item.name}</span>
              )}
              {!collapsed && item.highlight && (
                <span className="w-1.5 h-1.5 rounded-full bg-[#3156D9] shrink-0" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom Health & Status Panel */}
      {!collapsed && (
        <div className="p-3 border-t border-[#E5E7EB] bg-[#F8F9FB]/60 m-3 rounded-lg text-xs space-y-2">
          <div className="flex items-center justify-between text-gray-600">
            <span className="flex items-center gap-1.5 font-medium">
              <ShieldCheck className="w-3.5 h-3.5 text-[#16803C]" />
              Evidence Engine
            </span>
            <span className="text-[11px] font-semibold text-[#16803C] bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
              Active
            </span>
          </div>
          <div className="text-[11px] text-[#667085] leading-relaxed">
            {health?.has_gemini ? (
              <span className="flex items-center gap-1 text-blue-700">
                <Sparkles className="w-3 h-3 text-blue-600" />
                Gemini Orchestrator
              </span>
            ) : (
              <span>Grounded Deterministic Engine</span>
            )}
          </div>
        </div>
      )}
    </aside>
  );
};
