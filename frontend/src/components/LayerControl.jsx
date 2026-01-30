import { Layers, Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';
import { CBA_COLORS } from '../utils/constants';

export default function LayerControl({ layers, onToggle }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="absolute bottom-6 right-3 z-[1000]">
      <button
        onClick={() => setOpen(!open)}
        className="w-10 h-10 rounded-xl bg-white/90 dark:bg-gray-800/90 backdrop-blur
                   shadow-md flex items-center justify-center hover:bg-white dark:hover:bg-gray-700 transition-colors"
      >
        <Layers className="w-5 h-5 text-gray-600 dark:text-gray-300" />
      </button>

      {open && (
        <div className="absolute bottom-12 right-0 w-56 bg-white/95 dark:bg-gray-800/95 backdrop-blur
                        rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-3 space-y-1">
          <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
            Overlays
          </div>
          {Object.entries(layers).map(([key, val]) => (
            <button
              key={key}
              onClick={() => onToggle(key)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs
                         hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              {val.active ? (
                <Eye className="w-3.5 h-3.5 text-ocean-500" />
              ) : (
                <EyeOff className="w-3.5 h-3.5 text-gray-400" />
              )}
              <span className={val.active ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400'}>
                {val.label}
              </span>
            </button>
          ))}

          <div className="border-t border-gray-200 dark:border-gray-700 pt-2 mt-2">
            <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
              Legend
            </div>
            {Object.entries(CBA_COLORS).map(([key, val]) => (
              <div key={key} className="flex items-center gap-2 px-2 py-0.5 text-xs text-gray-600 dark:text-gray-400">
                <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: val.fill }} />
                {key}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
