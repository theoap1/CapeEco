import { useState, useRef, useEffect, useCallback } from 'react';
import { Search, X, MapPin } from 'lucide-react';
import { searchProperties } from '../utils/api';

export default function AddressSearchBar({ onSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);
  const debounceRef = useRef(null);

  const doSearch = useCallback(async (q) => {
    if (q.length < 2) {
      setResults([]);
      setIsOpen(false);
      return;
    }
    setLoading(true);
    try {
      const data = await searchProperties(q);
      setResults(data.results || []);
      setIsOpen(data.results?.length > 0);
      setSelectedIndex(-1);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChange = (e) => {
    const val = e.target.value;
    setQuery(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(val), 300);
  };

  const handleSelect = (result) => {
    setQuery(result.full_address || `ERF ${result.erf_number}, ${result.suburb}`);
    setIsOpen(false);
    onSelect(result);
  };

  const handleKeyDown = (e) => {
    if (!isOpen) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(i => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && selectedIndex >= 0) {
      e.preventDefault();
      handleSelect(results[selectedIndex]);
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target) &&
          inputRef.current && !inputRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const clear = () => {
    setQuery('');
    setResults([]);
    setIsOpen(false);
    inputRef.current?.focus();
  };

  return (
    <div className="relative w-full max-w-lg">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => results.length > 0 && setIsOpen(true)}
          placeholder="Search address or ERF number..."
          className="w-full pl-10 pr-10 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700
                     bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100
                     focus:outline-none focus:ring-2 focus:ring-ocean-500 focus:border-transparent
                     placeholder-gray-400 dark:placeholder-gray-500 text-sm shadow-sm"
        />
        {query && (
          <button onClick={clear} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
            <X className="w-4 h-4" />
          </button>
        )}
        {loading && (
          <div className="absolute right-10 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-ocean-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {isOpen && results.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-[1000] mt-1 w-full bg-white dark:bg-gray-800 rounded-xl shadow-lg
                     border border-gray-200 dark:border-gray-700 max-h-72 overflow-y-auto"
        >
          {results.map((r, i) => (
            <button
              key={r.id}
              onClick={() => handleSelect(r)}
              className={`w-full text-left px-4 py-2.5 flex items-start gap-3 hover:bg-ocean-50 dark:hover:bg-gray-700
                         transition-colors text-sm border-b border-gray-100 dark:border-gray-700 last:border-0
                         ${i === selectedIndex ? 'bg-ocean-50 dark:bg-gray-700' : ''}`}
            >
              <MapPin className="w-4 h-4 mt-0.5 text-ocean-500 shrink-0" />
              <div className="min-w-0">
                <div className="font-medium text-gray-900 dark:text-gray-100 truncate">
                  {r.full_address || `ERF ${r.erf_number}`}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {r.suburb} &middot; ERF {r.erf_number} &middot; {r.area_sqm ? `${Math.round(r.area_sqm)} m²` : ''}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
