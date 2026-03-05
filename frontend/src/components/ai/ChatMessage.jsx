import { User, Sparkles, Loader2, Search, BarChart3, MapPin, Zap, Shield, AlertTriangle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ToolResultCard from './ToolResultCard';

const TOOL_ICONS = {
  search_property: Search,
  get_property_details: MapPin,
  analyze_biodiversity: Shield,
  analyze_netzero: Zap,
  get_constraint_map: MapPin,
  compare_properties: BarChart3,
  get_crime_stats: AlertTriangle,
  get_loadshedding: Zap,
  get_municipal_health: BarChart3,
};

const TOOL_LABELS = {
  search_property: 'Searching properties',
  get_property_details: 'Loading property details',
  analyze_biodiversity: 'Analyzing biodiversity',
  analyze_netzero: 'Running net zero analysis',
  get_constraint_map: 'Generating constraint map',
  compare_properties: 'Comparing properties',
  get_crime_stats: 'Checking crime stats',
  get_loadshedding: 'Checking load shedding',
  get_municipal_health: 'Checking municipal health',
};

const markdownComponents = {
  p: ({ children }) => <p className="text-sm leading-relaxed text-gray-300 my-1">{children}</p>,
  strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
  em: ({ children }) => <em className="text-gray-200">{children}</em>,
  h1: ({ children }) => <h1 className="text-base font-bold text-white mt-3 mb-1">{children}</h1>,
  h2: ({ children }) => <h2 className="text-sm font-bold text-white mt-3 mb-1">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-semibold text-white mt-3 mb-1">{children}</h3>,
  h4: ({ children }) => <h4 className="text-xs font-semibold text-gray-300 mt-2 mb-1">{children}</h4>,
  ul: ({ children }) => <ul className="space-y-0.5 my-1 ml-1">{children}</ul>,
  ol: ({ children }) => <ol className="space-y-0.5 my-1 ml-1 list-decimal list-inside">{children}</ol>,
  li: ({ children }) => (
    <li className="text-sm text-gray-300 flex gap-1.5">
      <span className="text-ocean-400 mt-1 shrink-0">•</span>
      <span>{children}</span>
    </li>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-2 rounded-lg border border-gray-700/50">
      <table className="w-full text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-gray-800/80">{children}</thead>,
  th: ({ children }) => (
    <th className="text-left px-2 py-1.5 text-gray-400 font-medium text-[10px] uppercase tracking-wider border-b border-gray-700">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-2 py-1.5 text-gray-300 text-xs border-b border-gray-800/50">{children}</td>
  ),
  code: ({ children, className }) => {
    const isBlock = className?.startsWith('language-');
    return isBlock ? (
      <pre className="bg-gray-900 rounded-lg p-3 my-2 overflow-x-auto border border-gray-800">
        <code className="text-xs font-mono text-gray-300">{children}</code>
      </pre>
    ) : (
      <code className="bg-gray-800 px-1 py-0.5 rounded text-xs font-mono text-ocean-300">{children}</code>
    );
  },
  pre: ({ children }) => <>{children}</>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-ocean-500/30 pl-3 my-2 text-gray-400 italic">{children}</blockquote>
  ),
  hr: () => <hr className="border-gray-700/50 my-3" />,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-ocean-400 hover:text-ocean-300 underline">
      {children}
    </a>
  ),
};

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  const isError = message.isError;

  return (
    <div className={`flex gap-3 ${isUser ? '' : 'border-l-2 border-ocean-500/20 pl-3'}`}>
      {/* Avatar */}
      <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
        isUser
          ? 'bg-gray-700'
          : isError
          ? 'bg-red-900/30 border border-red-800/50'
          : 'bg-ocean-600/20 border border-ocean-500/30'
      }`}>
        {isUser ? (
          <User className="w-3.5 h-3.5 text-gray-300" />
        ) : (
          <Sparkles className={`w-3.5 h-3.5 ${isError ? 'text-red-400' : 'text-ocean-400'}`} />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="text-[11px] text-gray-500 mb-1 font-medium">
          {isUser ? 'You' : 'Siteline AI'}
        </div>

        {/* Tool call indicators */}
        {message.toolCalls?.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2 animate-fade-up">
            {message.toolCalls.map((tc, i) => {
              const Icon = TOOL_ICONS[tc.name] || Search;
              const label = TOOL_LABELS[tc.name] || tc.name;
              const isDone = tc.status === 'done';
              return (
                <div
                  key={i}
                  className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium ${
                    isDone
                      ? 'bg-green-900/20 border border-green-800/30 text-green-400'
                      : 'bg-gray-800 border border-gray-700 text-gray-400'
                  }`}
                >
                  {isDone ? (
                    <Icon className="w-3 h-3" />
                  ) : (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  )}
                  {label}
                </div>
              );
            })}
          </div>
        )}

        {/* Inline tool result cards */}
        {message.toolCalls?.some(tc => tc.status === 'done' && tc.result && !tc.result.error) && (
          <div className="space-y-2 mb-2">
            {message.toolCalls
              .filter(tc => tc.status === 'done' && tc.result && !tc.result.error)
              .map((tc, i) => (
                <ToolResultCard key={i} name={tc.name} result={tc.result} />
              ))}
          </div>
        )}

        {/* Message text */}
        {message.content && (
          isUser ? (
            <div className="text-sm leading-relaxed whitespace-pre-wrap text-gray-200">
              {message.content}
            </div>
          ) : (
            <div className={isError ? 'text-red-300' : ''}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {message.content}
              </ReactMarkdown>
            </div>
          )
        )}

        {/* Streaming indicator */}
        {message.isStreaming && !message.content && !message.toolCalls?.length && (
          <div className="flex items-center gap-2 text-gray-500">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span className="text-xs">Thinking...</span>
          </div>
        )}
      </div>
    </div>
  );
}
