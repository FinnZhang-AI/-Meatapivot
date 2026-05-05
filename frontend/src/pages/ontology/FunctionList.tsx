import { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { useFunctions } from '../../hooks/useOntology'

export default function FunctionList() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id || ''
  const { data: functions, isLoading } = useFunctions(tenantId)
  const [search, setSearch] = useState('')

  const filtered = (functions || []).filter((f) =>
    f.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">函数库</h1>
      </div>
      <input
        type="text"
        placeholder="搜索..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-md px-4 py-2 border rounded-lg dark:bg-slate-800 dark:border-slate-700 dark:text-white"
      />
      {isLoading ? <p className="text-slate-500">加载中...</p> : (
        <div className="bg-white dark:bg-slate-800 rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-700/50">
              <tr>
                <th className="text-left px-4 py-3">名称</th>
                <th className="text-left px-4 py-3">语言</th>
                <th className="text-left px-4 py-3">超时</th>
                <th className="text-left px-4 py-3">状态</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filtered.map((fn) => (
                <tr key={fn.id}>
                  <td className="px-4 py-3 font-medium">{fn.displayName || fn.name}</td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs bg-purple-100 text-purple-700">{fn.language}</span></td>
                  <td className="px-4 py-3">{fn.timeoutSeconds}s</td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">{fn.status}</span></td>
                </tr>
              ))}
              {filtered.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-400">暂无数据</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
