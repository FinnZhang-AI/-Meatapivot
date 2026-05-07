import { useAuth } from '../../hooks/useAuth'
import {
  useActionTypes,
  useObjectTypes,
  useCreateActionType,
  useUpdateActionType,
  useDeleteActionType,
} from '../../hooks/useOntology'
import type { ActionType, ExecutionType } from '../../types/ontology'
import { useState } from 'react'

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700',
  active: 'bg-green-100 text-green-700',
  archived: 'bg-red-100 text-red-700',
}

const EMPTY_FORM: Partial<ActionType> = {
  name: '',
  displayName: '',
  description: '',
  targetObjectTypeId: '',
  executionType: 'direct',
  parameters: [],
  rules: [],
  status: 'active',
}

export default function ActionTypeList() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id || ''
  const { data: actionTypes, isLoading } = useActionTypes(tenantId)
  const { data: objectTypes } = useObjectTypes(tenantId)
  const createMutation = useCreateActionType()
  const updateMutation = useUpdateActionType()
  const deleteMutation = useDeleteActionType()

  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<Partial<ActionType>>(EMPTY_FORM)

  const openCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setShowModal(true)
  }

  const openEdit = (at: ActionType) => {
    setEditingId(at.id)
    setForm({
      name: at.name,
      displayName: at.displayName || '',
      description: at.description || '',
      targetObjectTypeId: at.targetObjectTypeId,
      executionType: at.executionType,
      parameters: at.parameters ? [...at.parameters] : [],
      rules: at.rules ? [...at.rules] : [],
      status: at.status,
    })
    setShowModal(true)
  }

  const handleSubmit = async () => {
    if (!form.name || !form.targetObjectTypeId) return
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
    if (!confirm('确定要删除此动作类型吗？')) return
    await deleteMutation.mutateAsync({ id, tenantId })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">动作类型</h1>
        <button onClick={openCreate} className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors text-sm font-medium">+ 新建动作类型</button>
      </div>

      {isLoading && <p className="text-slate-500">加载中...</p>}

      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-700/50">
            <tr><th className="text-left px-4 py-3 font-semibold">名称</th><th className="text-left px-4 py-3 font-semibold">目标类型</th><th className="text-left px-4 py-3 font-semibold">执行方式</th><th className="text-left px-4 py-3 font-semibold">状态</th><th className="text-right px-4 py-3 font-semibold">操作</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {(actionTypes || []).map((at) => (
              <tr key={at.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30">
                <td className="px-4 py-3 font-medium">{at.name}</td>
                <td className="px-4 py-3 text-slate-500">{at.targetObjectTypeName || at.targetObjectTypeId}</td>
                <td className="px-4 py-3 text-slate-500">{at.executionType}</td>
                <td className="px-4 py-3"><span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[at.status] || ''}`}>{at.status}</span></td>
                <td className="px-4 py-3 text-right space-x-2">
                  <button onClick={() => openEdit(at)} className="text-blue-500 hover:text-blue-700 text-xs">编辑</button>
                  <button onClick={() => handleDelete(at.id)} className="text-red-500 hover:text-red-700 text-xs">删除</button>
                </td>
              </tr>
            ))}
            {(actionTypes || []).length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">暂无动作类型</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-bold mb-4 text-slate-900 dark:text-white">{editingId ? '编辑动作类型' : '新建动作类型'}</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-sm font-medium mb-1">名称</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" /></div>
                <div><label className="block text-sm font-medium mb-1">显示名</label><input value={form.displayName || ''} onChange={(e) => setForm({ ...form, displayName: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" /></div>
              </div>
              <div><label className="block text-sm font-medium mb-1">描述</label><textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" rows={2} /></div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">目标类型</label>
                  <select value={form.targetObjectTypeId} onChange={(e) => setForm({ ...form, targetObjectTypeId: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white">
                    <option value="">请选择</option>
                    {(objectTypes || []).map((ot) => (<option key={ot.id} value={ot.id}>{ot.displayName || ot.name}</option>))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">执行方式</label>
                  <select value={form.executionType} onChange={(e) => setForm({ ...form, executionType: e.target.value as ExecutionType })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white">
                    <option value="direct">Direct</option><option value="function_backed">Function-backed</option><option value="workflow">Workflow</option>
                  </select>
                </div>
              </div>
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
