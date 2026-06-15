import { useState } from 'react'
import { useRAGQuery, usePromptTemplates } from '../../hooks/useAIP'
import type { RAGSource } from '../../types/aip'

export default function RAGSearch() {
  const [query, setQuery] = useState('')
  const { mutateAsync: ragQuery, isPending, data: result } = useRAGQuery()
  const { data: promptTemplates } = usePromptTemplates(1, 100)
  const [selectedPromptId, setSelectedPromptId] = useState('')
  const [useLlamaIndex, setUseLlamaIndex] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    await ragQuery({
      query: query.trim(),
      topK: 5,
      searchMode: 'hybrid',
      promptTemplateId: selectedPromptId || undefined,
      promptVariables: selectedPromptId ? { query: query.trim() } : undefined,
      useLlamaIndex,
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch()
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-white">RAG 搜索</h1>
      <p className="text-slate-500">基于本体知识库的检索增强生成问答</p>

      {/* Search Input */}
      <div className="flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，例如：查询所有VIP客户..."
          className="flex-1 px-4 py-3 border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
        />
        <select
          value={selectedPromptId}
          onChange={(e) => setSelectedPromptId(e.target.value)}
          className="px-3 py-3 border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-sm dark:text-white"
        >
          <option value="">默认 Prompt</option>
          {promptTemplates?.items.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 px-3 py-3 border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-sm dark:text-white cursor-pointer">
          <input
            type="checkbox"
            checked={useLlamaIndex}
            onChange={(e) => setUseLlamaIndex(e.target.checked)}
          />
          LlamaIndex
        </label>
        <button
          onClick={handleSearch}
          disabled={isPending || !query.trim()}
          className="px-6 py-3 bg-primary text-white rounded-xl font-medium hover:bg-blue-600 transition-colors disabled:opacity-50"
        >
          {isPending ? '搜索中...' : '搜索'}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Answer Card */}
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center gap-3 mb-4">
              <h2 className="text-lg font-semibold">答案</h2>
              <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
                {result.durationMs}ms
              </span>
              {result.model && (
                <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full">
                  {result.model}
                </span>
              )}
            </div>
            <div className="prose dark:prose-invert max-w-none">
              <p className="text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">
                {result.answer}
              </p>
            </div>
          </div>

          {/* Sources */}
          <div>
            <h3 className="text-sm font-semibold text-slate-500 mb-3">
              参考来源 ({result.sources.length})
            </h3>
            <div className="grid gap-3">
              {result.sources.map((source: RAGSource, idx: number) => (
                <div
                  key={idx}
                  className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded-full font-medium">
                        {source.objectType}
                      </span>
                      <span className="font-medium text-sm">{source.objectKey}</span>
                    </div>
                    <span className="text-xs text-slate-400">score: {source.score.toFixed(3)}</span>
                  </div>
                  <p className="text-xs text-slate-500 mb-2">{source.explanation}</p>
                  <pre className="text-xs bg-slate-50 dark:bg-slate-900 rounded p-2 overflow-x-auto">
                    {JSON.stringify(source.propertiesPreview, null, 2)}
                  </pre>
                </div>
              ))}
              {result.sources.length === 0 && (
                <div className="text-center text-slate-400 py-4">未找到相关来源</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
