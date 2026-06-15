import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { API_BASE_URL, getAuthHeaders, handleResponse } from '../../hooks/useOntology'

interface WorkshopApp {
  id: string
  name: string
  description: string | null
  status: string
  updated_at: string | null
}

const WorkshopList = () => {
  const { user, token } = useAuth()
  const tenantId = user?.tenant_id || ''
  const [apps, setApps] = useState<WorkshopApp[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `${API_BASE_URL}/workshop/apps?page=1&page_size=20&tenant_id=${encodeURIComponent(tenantId)}`,
        { headers: getAuthHeaders(token) }
      )
      const data = await handleResponse<{ items: WorkshopApp[] }>(res)
      setApps(data.items || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (tenantId) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId])

  const createApp = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName.trim()) return
    try {
      const res = await fetch(`${API_BASE_URL}/workshop/apps?tenant_id=${encodeURIComponent(tenantId)}`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify({
          name: newName.trim(),
          graph: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
        }),
      })
      const data = await handleResponse<WorkshopApp>(res)
      setApps([data, ...apps])
      setNewName('')
      setCreating(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Workshop 应用</h1>
          <p className="text-slate-500 text-sm mt-1">基于 Ontology 的低代码应用构建器</p>
        </div>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 text-sm font-medium"
        >
          + 新建应用
        </button>
      </div>

      {creating && (
        <form
          onSubmit={createApp}
          className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4 flex items-center gap-3"
        >
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="应用名称"
            className="flex-1 px-3 py-2 text-sm border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white"
            autoFocus
          />
          <button
            type="submit"
            className="px-4 py-2 bg-primary text-white rounded-lg text-sm"
          >
            创建
          </button>
          <button
            type="button"
            onClick={() => {
              setCreating(false)
              setNewName('')
            }}
            className="px-4 py-2 text-slate-500 hover:text-slate-700 text-sm"
          >
            取消
          </button>
        </form>
      )}

      {error && (
        <div className="text-sm text-rose-500 bg-rose-50 dark:bg-rose-900/20 rounded-lg p-3">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-8 text-slate-400">加载中…</div>
      ) : apps.length === 0 ? (
        <div className="text-center py-12 text-slate-400 bg-white dark:bg-slate-800 rounded-xl border border-dashed border-slate-300 dark:border-slate-600">
          暂无应用 · 点击「+ 新建应用」开始
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {apps.map((app) => (
            <Link
              key={app.id}
              to={`/workshop/editor/${app.id}`}
              className="block bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5 hover:shadow-md hover:border-primary/30 transition-all"
            >
              <h3 className="font-semibold text-slate-900 dark:text-white truncate">
                {app.name}
              </h3>
              {app.description && (
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">
                  {app.description}
                </p>
              )}
              <div className="flex items-center justify-between mt-3 text-xs text-slate-400">
                <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-700">
                  {app.status}
                </span>
                <span>
                  {app.updated_at ? new Date(app.updated_at).toLocaleString('zh-CN') : ''}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export default WorkshopList
