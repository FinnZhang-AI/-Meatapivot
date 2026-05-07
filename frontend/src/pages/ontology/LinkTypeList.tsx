import { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'
import {
  useLinkTypes,
  useObjectTypes,
  useCreateLinkType,
  useUpdateLinkType,
  useDeleteLinkType,
} from '../../hooks/useOntology'
import type { LinkType, Cardinality } from '../../types/ontology'

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700',
  active: 'bg-green-100 text-green-700',
  archived: 'bg-red-100 text-red-700',
}

const EMPTY_FORM: Partial<LinkType> = {
  name: '',
  displayName: '',
  description: '',
  sourceObjectTypeId: '',
  targetObjectTypeId: '',
  cardinality: 'MANY_TO_ONE',
  status: 'active',
}

export default function LinkTypeList() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id || ''
  const { data: linkTypes, isLoading } = useLinkTypes(tenantId)
  const { data: objectTypes } = useObjectTypes(tenantId)
  const createMutation = useCreateLinkType()
  const updateMutation = useUpdateLinkType()
  const deleteMutation = useDeleteLinkType()

  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<Partial<LinkType>>(EMPTY_FORM)

  const filtered = (linkTypes || []).filter((lt) =>
    lt.name.toLowerCase().includes(search.toLowerCase())
  )

  const openCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setShowModal(true)
  }

  const openEdit = (lt: LinkType) => {
    setEditingId(lt.id)
    setForm({
      name: lt.name,
      displayName: lt.displayName || '',
      description: lt.description || '',
      sourceObjectTypeId: lt.sourceObjectTypeId,
      targetObjectTypeId: lt.targetObjectTypeId,
      cardinality: lt.cardinality,
      status: lt.status,
    })
    setShowModal(true)
  }

  const handleSubmit = async () => {
    if (!form.name || !form.sourceObjectTypeId || !form.targetObjectTypeId) return
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
    if (!confirm('确定要删除此关系类型吗？')) return
    await deleteMutation.mutateAsync({ id, tenantId })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">关系类型</h1>
        <button
          onClick={openCreate}
          className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors text-sm font-medium"
        >
          + 新建关系类型
        </button>
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
                <th className="text-left px-4 py-3">方向</th>
                <th className="text-left px-4 py-3">基数</th>
                <th className="text-left px-4 py-3">状态</th>
                <th className="text-right px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filtered.map((lt) => (
                <tr key={lt.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30">
                  <td className="px-4 py-3 font-medium">{lt.name}</td>
                  <td className="px-4 py-3 text-slate-500">{lt.sourceObjectTypeName} → {lt.targetObjectTypeName}</td>
                  <td className="px-4 py-3">{lt.cardinality}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_STYLES[lt.status]}`}>{lt.status}</span></td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <button onClick={() => openEdit(lt)} className="text-blue-500 hover:text-blue-700 text-xs">编辑</button>
                    <button onClick={() => handleDelete(lt.id)} className="text-red-500 hover:text-red-700 text-xs">删除</button>
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
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-bold mb-4 text-slate-900 dark:text-white">{editingId ? '编辑关系类型' : '新建关系类型'}</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">名称</label>
                  <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">显示名</label>
                  <input value={form.displayName || ''} onChange={(e) => setForm({ ...form, displayName: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">描述</label>
                <textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" rows={2} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">源类型</label>
                  <select value={form.sourceObjectTypeId} onChange={(e) => setForm({ ...form, sourceObjectTypeId: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white">
                    <option value="">请选择</option>
                    {(objectTypes || []).map((ot) => (<option key={ot.id} value={ot.id}>{ot.displayName || ot.name}</option>))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">目标类型</label>
                  <select value={form.targetObjectTypeId} onChange={(e) => setForm({ ...form, targetObjectTypeId: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white">
                    <option value="">请选择</option>
                    {(objectTypes || []).map((ot) => (<option key={ot.id} value={ot.id}>{ot.displayName || ot.name}</option>))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">基数</label>
                <select value={form.cardinality} onChange={(e) => setForm({ ...form, cardinality: e.target.value as Cardinality })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white">
                  <option value="ONE_TO_ONE">一对一</option>
                  <option value="ONE_TO_MANY">一对多</option>
                  <option value="MANY_TO_ONE">多对一</option>
                  <option value="MANY_TO_MANY">多对多</option>
                </select>
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
