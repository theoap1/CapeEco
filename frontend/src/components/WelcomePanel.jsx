import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Database, Layers, MapPin, Globe, Search, Sparkles,
  Shield, Leaf, TreePine, Landmark, Building2, Siren,
  Banknote, ChevronRight, Zap, Activity,
} from 'lucide-react';
import api from '../utils/api';

const STATS = [
  { key: 'properties', label: 'PARCELS', icon: Database, color: 'ocean' },
  { key: 'layers', label: 'LAYERS', icon: Layers, color: 'fynbos' },
  { key: 'coverage', label: 'COVERAGE', icon: MapPin, color: 'protea' },
  { key: 'source', label: 'SOURCE', icon: Globe, color: 'emerald' },
];

const ACTIONS = [
  {
    title: 'AI Property Analysis',
    desc: 'Query any property with natural language',
    icon: Sparkles,
    color: 'protea',
    path: '/ai',
  },
  {
    title: 'Biodiversity Risk',
    desc: 'CBA/ESA constraints & offset requirements',
    icon: Leaf,
    color: 'green',
    path: '/ai',
  },
  {
    title: 'Crime Intelligence',
    desc: 'SAPS precinct data & risk scoring',
    icon: Siren,
    color: 'red',
    path: '/ai',
  },
];

const DATA_SOURCES = [
  { name: 'BioNet CBA/ESA', records: '23,473', icon: Leaf, status: true },
  { name: 'Ecosystem Types', records: '4,553', icon: TreePine, status: true },
  { name: 'Heritage Registry', records: '98,648', icon: Landmark, status: true },
  { name: 'Urban Edge', records: '53', icon: Building2, status: true },
  { name: 'SAPS Crime', records: '1,154', icon: Siren, status: true },
  { name: 'Municipal Finance', records: 'CCT', icon: Banknote, status: true },
];

export default function WelcomePanel() {
  const navigate = useNavigate();
  const [propertyCount, setPropertyCount] = useState(null);

  useEffect(() => {
    api.get('/v1/health')
      .then(r => setPropertyCount(r.data.property_count))
      .catch(() => setPropertyCount(834959));
  }, []);

  const statValues = {
    properties: propertyCount ? propertyCount.toLocaleString() : '···',
    layers: '7',
    coverage: 'CPT',
    source: 'GOV',
  };

  return (
    <div className="w-[420px] h-full flex flex-col shrink-0 bg-gray-950 border-l border-gray-800/60 overflow-hidden">
      {/* Header with subtle gradient */}
      <div className="relative px-5 pt-6 pb-5 border-b border-gray-800/60 overflow-hidden">
        <div
          className="absolute inset-0 opacity-40"
          style={{
            background: 'radial-gradient(ellipse 80% 100% at 70% 0%, rgb(37 121 234 / 0.08), transparent 60%)',
          }}
        />
        <div className="relative">
          <div className="flex items-center gap-2.5 mb-1 animate-fade-up delay-1">
            <div className="w-2 h-2 rounded-full bg-ocean-400 animate-pulse-risk" />
            <span className="text-[10px] font-semibold text-ocean-400 uppercase tracking-[0.2em] font-data">
              LIVE
            </span>
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight animate-fade-up delay-2">
            Siteline
          </h2>
          <p className="text-xs text-gray-500 mt-1 animate-fade-up delay-3">
            Cape Town Property Intelligence
          </p>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto sidebar-scroll">
        {/* Stats Grid */}
        <div className="p-4 grid grid-cols-2 gap-2.5 animate-fade-up delay-3">
          {STATS.map((stat) => {
            const Icon = stat.icon;
            return (
              <div
                key={stat.key}
                className="bg-gray-900/80 border border-gray-800/50 rounded-lg p-3 group hover:border-gray-700/50 transition-colors"
              >
                <div className="flex items-center gap-1.5 mb-2">
                  <Icon className="w-3 h-3 text-gray-600" />
                  <span className="text-[9px] font-semibold text-gray-600 uppercase tracking-[0.15em] font-data">
                    {stat.label}
                  </span>
                </div>
                <div className="text-lg font-bold text-white font-data tracking-tight">
                  {statValues[stat.key]}
                </div>
              </div>
            );
          })}
        </div>

        {/* Divider */}
        <div className="mx-4 h-px bg-gradient-to-r from-transparent via-gray-800 to-transparent" />

        {/* Quick Actions */}
        <div className="p-4 space-y-2 animate-fade-up delay-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-3 h-3 text-gray-600" />
            <span className="text-[9px] font-semibold text-gray-600 uppercase tracking-[0.15em] font-data">
              QUICK ACTIONS
            </span>
          </div>
          {ACTIONS.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.title}
                onClick={() => action.path && navigate(action.path)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-gray-900/50 border border-gray-800/40
                           hover:bg-gray-800/60 hover:border-gray-700/50 transition-all group text-left"
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                  action.color === 'protea' ? 'bg-protea-500/10 text-protea-400' :
                  action.color === 'green' ? 'bg-green-500/10 text-green-400' :
                  'bg-red-500/10 text-red-400'
                }`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-gray-200 group-hover:text-white transition-colors">
                    {action.title}
                  </div>
                  <div className="text-[11px] text-gray-600 truncate">
                    {action.desc}
                  </div>
                </div>
                <ChevronRight className="w-3.5 h-3.5 text-gray-700 group-hover:text-gray-500 transition-colors shrink-0" />
              </button>
            );
          })}
        </div>

        {/* Divider */}
        <div className="mx-4 h-px bg-gradient-to-r from-transparent via-gray-800 to-transparent" />

        {/* Data Sources */}
        <div className="p-4 animate-fade-up delay-5">
          <div className="flex items-center gap-2 mb-3">
            <Database className="w-3 h-3 text-gray-600" />
            <span className="text-[9px] font-semibold text-gray-600 uppercase tracking-[0.15em] font-data">
              DATA SOURCES
            </span>
          </div>
          <div className="space-y-1">
            {DATA_SOURCES.map((source) => {
              const Icon = source.icon;
              return (
                <div
                  key={source.name}
                  className="flex items-center gap-2.5 px-2.5 py-2 rounded-md hover:bg-gray-900/50 transition-colors"
                >
                  <Icon className="w-3.5 h-3.5 text-gray-600 shrink-0" />
                  <span className="text-xs text-gray-400 flex-1 truncate">{source.name}</span>
                  <span className="text-[10px] text-gray-600 font-data shrink-0">{source.records}</span>
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${source.status ? 'bg-green-500' : 'bg-gray-700'}`} />
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer hint */}
        <div className="px-4 pb-6 animate-fade-up delay-6">
          <div className="bg-ocean-500/5 border border-ocean-500/10 rounded-lg px-4 py-3">
            <div className="flex items-start gap-2.5">
              <Search className="w-3.5 h-3.5 text-ocean-500/60 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-gray-400">
                  Search for a property above to see full analysis — biodiversity, crime risk, solar potential, and more.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
