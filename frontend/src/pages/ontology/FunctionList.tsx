import { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'
import {
  useFunctions,
  useCreateFunction,
  useUpdateFunction,
  useDeleteFunction,
} from '../../hooks/useOntology'
import type { FunctionDef } from '../../types/ontology'

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700',
  active: 'bg-green-100 text-green-700',
  archived: 'bg-red-100 text-red-700',
}

const EMPTY_FORM: Partial<FunctionDef> = {
  name: '',
  displayName: '',
  description: '',
  language: 'python',
  code: '',
  timeoutSeconds: 30,
  memoryMb: 256,
  status: 'active',
}

export default function FunctionList() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id || ''
  const { data: functions, isLoading } = useFunctions(tenantId)
  const createMutation = useCreateFunction()
  const updateMutation = useUpdateFunction()
  const deleteMutation = useDeleteFunction()

  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<Partial<FunctionDef>>(EMPTY_FORM)

  const filtered = (functions || []).filter((f) =>
    f.name.toLowerCase().includes(search.toLowerCase())
  )

  const openCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setShowModal(true)
  }

  const openEdit = (fn: FunctionDef) => {
    setEditingId(fn.id)
    setForm({
      name: fn.name,
      displayName: fn.displayName || '',
      description: fn.description || '',
      language: fn.language,
      code: fn.code,
      timeoutSeconds: fn.timeoutSeconds,
      memoryMb: fn.memoryMb,
      status: fn.status,
    })
    setShowModal(true)
  }

  const handleSubmit = async () => {
    if (!form.name || !form.code) return
    if (editingId) {
      await updateMutation.mutateAsync({ id: editingId, data: form })
    } else {
      await createMutation.mutateAsync(form)
    }
    setShowModal(false)
    setForm(EMPTY_FORM)
    setEditingId(null)
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除此函数吗？')) return
    await deleteMutation.mutateAsync({ id, tenantId })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">函数库</h1>
        <button onClick={openCreate} className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors text-sm font-medium">+ 新建函数</button>
      </div>
      <input type="text" placeholder="搜索..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-full max-w-md px-4 py-2 border rounded-lg dark:bg-slate-800 dark:border-slate-700 dark:text-white" />
      {isLoading ? <p className="text-slate-500">加载中...</p> : (
        <div className="bg-white dark:bg-slate-800 rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-700/50"><tr><th className="text-left px-4 py-3">名称</th><th className="text-left px-4 py-3">语言</th><th className="text-left px-4 py-3">超时</th><th className="text-left px-4 py-3">状态</th><th className="text-right px-4 py-3">操作</th></tr></thead>
            <tbody className="divide-y">
              {filtered.map((fn) => (
                <tr key={fn.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30">
                  <td className="px-4 py-3 font-medium">{fn.displayName || fn.name}</td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs bg-purple-100 text-purple-700">{fn.language}</span></td>
                  <td className="px-4 py-3">{fn.timeoutSeconds}s</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_STYLES[fn.status]}`}>{fn.status}</span></td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <button onClick={() => openEdit(fn)} className="text-blue-500 hover:text-blue-700 text-xs">编辑</button>
                    <button onClick={() => handleDelete(fn.id)} className="text-red-500 hover:text-red-700 text-xs">删除</button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">暂无数据</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
            <h2 className="text-lg font-bold mb-4 text-slate-900 dark:text-white">{editingId ? '编辑函数' : '新建函数'}</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-sm font-medium mb-1">名称</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" /></div>
                <div><label className="block text-sm font-medium mb-1">显示名</label><input value={form.displayName || ''} onChange={(e) => setForm({ ...form, displayName: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" /></div>
              </div>
              <div><label className="block text-sm font-medium mb-1">描述</label><textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" rows={2} /></div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">语言</label>
                  <select value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value as 'python' | 'typescript' })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white">
                    <option value="python">Python</option><option value="typescript">TypeScript</option>
                  </select>
                </div>
                <div><label className="block text-sm font-medium mb-1">超时 (秒)</label><input type="number" value={form.timeoutSeconds} onChange={(e) => setForm({ ...form, timeoutSeconds: Number(e.target.value) })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" /></div>
                <div><label className="block text-sm font-medium mb-1">内存 (MB)</label><input type="number" value={form.memoryMb} onChange={(e) => setForm({ ...form, memoryMb: Number(e.target.value) })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" /></div>
              </div>
              <div><label className="block text-sm font-medium mb-1">代码</label><textarea value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white font-mono text-sm" rows={10} placeholder={`def main(context):\n    return {"result": "hello"}`} /></div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleSubmit} className="px-4 py-2 bg-primary text-white rounded-lg text-sm">{editingId ? '保存' : '创建'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
