import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useSearch, useObjectTypes } from '../../hooks/useOntology'
import { useAuth } from '../../hooks/useAuth'
import type { SearchResultItem } from '../../types/ontology'

const SEARCH_MODES = [
  { value: 'hybrid', label: '混合', desc: '向量 + 图谱' },
  { value: 'vector', label: '向量', desc: '语义相似度' },
  { value: 'graph', label: '图谱', desc: '关系邻居' },
  { value: 'keyword', label: '关键词', desc: '精确匹配' },
]

const SOURCE_BADGES: Record<string, { label: string; color: string }> = {
  vector: { label: '向量', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  graph: { label: '图谱', color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  hybrid: { label: '混合', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
  keyword: { label: '关键词', color: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300' },
}

export default function SemanticSearch() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id || ''
  const [searchParams] = useSearchParams()

  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [mode, setMode] = useState('hybrid')
  const [filterType, setFilterType] = useState('')
  const [hasSearched, setHasSearched] = useState(false)

  const { data: objectTypes } = useObjectTypes(tenantId)
  const searchMutation = useSearch()

  // Auto-search if query comes from URL
  useEffect(() => {
    const q = searchParams.get('q')
    if (q && !hasSearched) {
      setQuery(q)
      handleSearchInternal(q)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const results: SearchResultItem[] = searchMutation.data?.results || []
  const meta = searchMutation.data
    ? {
        total: searchMutation.data.total,
        vectorHits: searchMutation.data.vectorHits,
        graphHits: searchMutation.data.graphHits,
        durationMs: searchMutation.data.durationMs,
        reranked: searchMutation.data.reranked,
      }
    : null

  const handleSearchInternal = async (q: string) => {
    if (!q.trim()) return
    setHasSearched(true)
    await searchMutation.mutateAsync({
      q: q.trim(),
      tenantId,
      objectTypes: filterType ? [filterType] : undefined,
      searchMode: mode,
    })
  }

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    await handleSearchInternal(query)
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">语义搜索</h1>
        <p className="text-slate-500 text-sm mt-1">基于向量相似度和知识图谱的混合检索</p>
      </div>

      {/* Search Form */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6 space-y-4">
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="flex-1 relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="输入搜索关键词..."
              className="w-full px-4 py-2.5 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={searchMutation.isPending || !query.trim()}
            className="px-6 py-2.5 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium disabled:opacity-50 flex items-center gap-2"
          >
            {searchMutation.isPending ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                搜索中...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                搜索
              </>
            )}
          </button>
        </form>

        <div className="flex flex-wrap items-center gap-4">
          {/* Mode Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">模式</span>
            <div className="flex rounded-lg border border-slate-200 dark:border-slate-600 overflow-hidden">
              {SEARCH_MODES.map((m) => (
                <button
                  key={m.value}
                  onClick={() => setMode(m.value)}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                    mode === m.value
                      ? 'bg-primary text-white'
                      : 'bg-white dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-600'
                  }`}
                  title={m.desc}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* Object Type Filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">对象类型</span>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="px-3 py-1.5 text-xs border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white outline-none"
            >
              <option value="">全部</option>
              {(objectTypes || []).map((ot) => (
                <option key={ot.id} value={ot.name}>
                  {ot.displayName || ot.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Results Meta */}
      {meta && hasSearched && (
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <span>
            共 <strong className="text-slate-700 dark:text-slate-300">{meta.total}</strong> 条结果
          </span>
          <span>·</span>
          <span>向量: {meta.vectorHits}</span>
          <span>·</span>
          <span>图谱: {meta.graphHits}</span>
          {meta.reranked && (
            <>
              <span>·</span>
              <span className="text-purple-600 dark:text-purple-400">已重排</span>
            </>
          )}
          <span className="ml-auto">耗时 {meta.durationMs}ms</span>
        </div>
      )}

      {/* Results List */}
      <div className="space-y-3">
        {results.map((item) => {
          const badge = SOURCE_BADGES[item.source] || SOURCE_BADGES.keyword
          return (
            <Link
              key={item.objectId}
              to={`/objects/${item.objectType}/${item.objectId}`}
              className="block bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4 hover:shadow-md hover:border-primary/30 transition-all"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-slate-900 dark:text-white truncate">
                      {item.objectKey}
                    </h3>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${badge.color}`}>
                      {badge.label}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mb-2">
                    {item.objectType} · {item.label}
                  </p>
                  {item.explanation && (
                    <p className="text-xs text-slate-400 mb-2">{item.explanation}</p>
                  )}
                  {item.propertiesPreview && Object.keys(item.propertiesPreview).length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(item.propertiesPreview).slice(0, 4).map(([k, v]) => (
                        <span
                          key={k}
                          className="px-2 py-0.5 bg-slate-50 dark:bg-slate-700/50 rounded text-xs text-slate-600 dark:text-slate-400"
                        >
                          {k}: {String(v).slice(0, 30)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="text-right">
                  <span className="text-lg font-bold text-primary">{(item.score * 100).toFixed(1)}</span>
                  <span className="text-xs text-slate-400 ml-0.5">分</span>
                </div>
              </div>
            </Link>
          )
        })}

        {/* Empty States */}
        {searchMutation.isPending && results.length === 0 && (
          <div className="text-center py-12">
            <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-slate-400">正在搜索...</p>
          </div>
        )}

        {!searchMutation.isPending && hasSearched && results.length === 0 && (
          <div className="text-center py-12 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
            <svg className="w-12 h-12 text-slate-300 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <p className="text-sm text-slate-500">未找到匹配结果</p>
            <p className="text-xs text-slate-400 mt-1">尝试更换关键词或调整搜索模式</p>
          </div>
        )}

        {!hasSearched && (
          <div className="text-center py-12 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
            <svg className="w-12 h-12 text-slate-300 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <p className="text-sm text-slate-500">输入关键词开始语义搜索</p>
            <p className="text-xs text-slate-400 mt-1">支持按对象类型过滤和多种搜索模式</p>
          </div>
        )}
      </div>
    </div>
  )
}
