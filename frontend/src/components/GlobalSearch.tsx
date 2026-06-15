import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { API_BASE_URL, getAuthHeaders, handleResponse } from '../hooks/useOntology'

interface Suggestion {
  kind: 'object_type' | 'document'
  id: string
  label: string
  hint: string
}

interface HistoryEntry {
  query: string
  mode: SearchMode
  ts: number
}

type SearchMode = 'keyword' | 'semantic' | 'rag'

const MODE_LABEL: Record<SearchMode, string> = {
  keyword: '关键词',
  semantic: '语义',
  rag: 'RAG',
}

const HISTORY_KEY_PREFIX = 'meatapivot:search-history:'
const HISTORY_MAX = 8
const SUGGEST_DEBOUNCE_MS = 150

const loadHistory = (userId: string | undefined): HistoryEntry[] => {
  if (!userId) return []
  try {
    const raw = localStorage.getItem(HISTORY_KEY_PREFIX + userId)
    if (!raw) return []
    const parsed = JSON.parse(raw) as HistoryEntry[]
    return Array.isArray(parsed) ? parsed.slice(0, HISTORY_MAX) : []
  } catch {
    return []
  }
}

const saveHistory = (userId: string | undefined, entries: HistoryEntry[]): void => {
  if (!userId) return
  try {
    localStorage.setItem(HISTORY_KEY_PREFIX + userId, JSON.stringify(entries))
  } catch {
    // localStorage might be disabled — silently ignore
  }
}

const GlobalSearch = () => {
  const navigate = useNavigate()
  const { user, token } = useAuth()
  const userId = user?.id

  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<SearchMode>('semantic')
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [history, setHistory] = useState<HistoryEntry[]>(() => loadHistory(userId))

  const containerRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<number | null>(null)

  // Reload history when the user logs in / changes
  useEffect(() => {
    setHistory(loadHistory(userId))
  }, [userId])

  // Close dropdown on outside click
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  // Autocomplete: debounced call to /search/suggest
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    if (!query.trim()) {
      setSuggestions([])
      return
    }
    debounceRef.current = window.setTimeout(async () => {
      try {
        const url = `${API_BASE_URL}/ontology/search/suggest?q=${encodeURIComponent(query.trim())}&limit=8&tenant_id=${encodeURIComponent(user?.tenant_id || '')}`
        const res = await fetch(url, { headers: getAuthHeaders(token) })
        const data = await handleResponse<{ suggestions: Suggestion[] }>(res)
        setSuggestions(data.suggestions || [])
      } catch {
        setSuggestions([])
      }
    }, SUGGEST_DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, user?.tenant_id, token])

  const recordHistory = (q: string) => {
    if (!q.trim()) return
    const entry: HistoryEntry = { query: q.trim(), mode, ts: Date.now() }
    // Dedup by query+mode, keep most recent, cap to HISTORY_MAX
    const next = [entry, ...history.filter((h) => !(h.query === entry.query && h.mode === entry.mode))]
      .slice(0, HISTORY_MAX)
    setHistory(next)
    saveHistory(userId, next)
  }

  const submitSearch = (q: string) => {
    const trimmed = q.trim()
    if (!trimmed) return
    recordHistory(trimmed)
    setShowDropdown(false)
    // Route to existing search page with mode + query
    navigate(`/ontology/search?q=${encodeURIComponent(trimmed)}&mode=${mode}`)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    submitSearch(query)
  }

  const onSuggestionClick = (s: Suggestion) => {
    submitSearch(s.label)
  }

  const onHistoryClick = (entry: HistoryEntry) => {
    setMode(entry.mode)
    setQuery(entry.query)
    submitSearch(entry.query)
  }

  const removeHistoryEntry = (idx: number) => {
    const next = history.filter((_, i) => i !== idx)
    setHistory(next)
    saveHistory(userId, next)
  }

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <div className="flex-1 relative">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setShowDropdown(true)
            }}
            onFocus={() => setShowDropdown(true)}
            placeholder="全局搜索..."
            className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg bg-slate-50 dark:bg-slate-700 border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-200 placeholder-slate-400 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
          />
        </div>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as SearchMode)}
          className="text-sm border rounded-lg px-2 py-2 bg-slate-50 dark:bg-slate-700 border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-200 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
          aria-label="搜索模式"
        >
          <option value="keyword">关键词</option>
          <option value="semantic">语义</option>
          <option value="rag">RAG</option>
        </select>
      </form>

      {showDropdown && (query.trim() || history.length > 0) && (
        <div className="absolute z-40 top-full mt-1 w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg overflow-hidden">
          {query.trim() && suggestions.length > 0 && (
            <div className="py-1">
              <p className="px-3 py-1 text-xs uppercase tracking-wider text-slate-400">
                建议
              </p>
              {suggestions.map((s) => (
                <button
                  key={`${s.kind}:${s.id}`}
                  type="button"
                  onClick={() => onSuggestionClick(s)}
                  className="w-full text-left px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center justify-between gap-2"
                >
                  <span className="truncate text-sm text-slate-700 dark:text-slate-200">
                    {s.label}
                  </span>
                  <span className="text-xs text-slate-400 shrink-0">
                    {s.kind === 'object_type' ? '对象类型' : '文档'} · {s.hint}
                  </span>
                </button>
              ))}
            </div>
          )}

          {query.trim() && suggestions.length === 0 && (
            <div className="px-3 py-3 text-xs text-slate-400">
              没有匹配建议 · 按 Enter 用 {MODE_LABEL[mode]} 模式搜索
            </div>
          )}

          {!query.trim() && history.length > 0 && (
            <div className="py-1">
              <p className="px-3 py-1 text-xs uppercase tracking-wider text-slate-400">
                最近搜索
              </p>
              {history.map((h, i) => (
                <div
                  key={`${h.ts}-${h.query}`}
                  className="flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-700"
                >
                  <button
                    type="button"
                    onClick={() => onHistoryClick(h)}
                    className="flex-1 text-left px-3 py-2 text-sm text-slate-700 dark:text-slate-200 truncate"
                  >
                    <span className="mr-2 text-xs text-slate-400">
                      [{MODE_LABEL[h.mode]}]
                    </span>
                    {h.query}
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      removeHistoryEntry(i)
                    }}
                    className="px-2 text-xs text-slate-400 hover:text-rose-500"
                    aria-label="移除历史"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default GlobalSearch
