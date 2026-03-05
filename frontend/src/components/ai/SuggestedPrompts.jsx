import { Search, Shield, Zap, BarChart3, Siren, BatteryCharging } from 'lucide-react';

const PROMPTS = [
  {
    icon: Search,
    title: 'Analyze a property',
    prompt: 'Analyze ERF 901 in Bantry Bay — tell me about biodiversity risk, zoning, and development potential.',
    color: 'ocean',
  },
  {
    icon: Shield,
    title: 'Check biodiversity risk',
    prompt: 'What are the biodiversity constraints for properties in Constantia? Any no-go areas?',
    color: 'green',
  },
  {
    icon: Zap,
    title: 'Solar & net zero',
    prompt: 'What is the solar potential and Green Star rating for a residential property in Sea Point?',
    color: 'amber',
  },
  {
    icon: BarChart3,
    title: 'Compare properties',
    prompt: 'Compare property values within 2km of ERF 100 in Woodstock.',
    color: 'purple',
  },
  {
    icon: Siren,
    title: 'Crime risk analysis',
    prompt: 'What is the crime risk for properties in Observatory? Show me the safety profile.',
    color: 'red',
  },
  {
    icon: BatteryCharging,
    title: 'Load shedding impact',
    prompt: 'How does load shedding affect properties in Claremont? What stage are they in?',
    color: 'yellow',
  },
];

const COLOR_MAP = {
  ocean: 'bg-ocean-600/10 border-ocean-500/20 text-ocean-400 hover:bg-ocean-600/20',
  green: 'bg-green-600/10 border-green-500/20 text-green-400 hover:bg-green-600/20',
  amber: 'bg-amber-600/10 border-amber-500/20 text-amber-400 hover:bg-amber-600/20',
  purple: 'bg-purple-600/10 border-purple-500/20 text-purple-400 hover:bg-purple-600/20',
  red: 'bg-red-600/10 border-red-500/20 text-red-400 hover:bg-red-600/20',
  yellow: 'bg-yellow-600/10 border-yellow-500/20 text-yellow-400 hover:bg-yellow-600/20',
};

export default function SuggestedPrompts({ onSelect }) {
  return (
    <div className="grid grid-cols-3 gap-2 max-w-2xl w-full">
      {PROMPTS.map((p, i) => {
        const Icon = p.icon;
        return (
          <button
            key={i}
            onClick={() => onSelect(p.prompt)}
            className={`flex flex-col items-start gap-1.5 p-3 rounded-xl border text-left transition-all hover:scale-[1.02] hover:shadow-lg hover:shadow-black/20 ${COLOR_MAP[p.color]}`}
          >
            <Icon className="w-4 h-4" />
            <span className="text-xs font-medium text-gray-200">{p.title}</span>
            <span className="text-[11px] text-gray-500 line-clamp-2">{p.prompt}</span>
          </button>
        );
      })}
    </div>
  );
}
