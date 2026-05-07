import { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'
import {
  useInterfaces,
  useCreateInterface,
  useUpdateInterface,
  useDeleteInterface,
} from '../../hooks/useOntology'
import type { InterfaceDef, PropertyDef, InterfaceLinkRequirement } from '../../types/ontology'

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700',
  active: 'bg-green-100 text-green-700',
  archived: 'bg-red-100 text-red-700',
}

const EMPTY_FORM: Partial<InterfaceDef> = {
  name: '',
  displayName: '',
  description: '',
  requiredProperties: [],
  requiredLinks: [],
  status: 'active',
}

export default function InterfaceList() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id || ''
  const { data: interfaces, isLoading } = useInterfaces(tenantId)
  const createMutation = useCreateInterface()
  const updateMutation = useUpdateInterface()
  const deleteMutation = useDeleteInterface()

  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<Partial<InterfaceDef>>(EMPTY_FORM)
  const [newProp, setNewProp] = useState<Partial<PropertyDef>>({ name: '', type: 'string', required: true })
  const [newLink, setNewLink] = useState<Partial<InterfaceLinkRequirement>>({ name: '', targetType: '', cardinality: 'MANY_TO_ONE' })

  const filtered = (interfaces || []).filter((i) =>
    i.name.toLowerCase().includes(search.toLowerCase())
  )

  const openCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setShowModal(true)
  }

  const openEdit = (iface: InterfaceDef) => {
    setEditingId(iface.id)
    setForm({
      name: iface.name,
      displayName: iface.displayName || '',
      description: iface.description || '',
      requiredProperties: iface.requiredProperties ? [...iface.requiredProperties] : [],
      requiredLinks: iface.requiredLinks ? [...iface.requiredLinks] : [],
      status: iface.status,
    })
    setShowModal(true)
  }

  const handleAddProp = () => {
    if (!newProp.name) return
    setForm((prev) => ({ ...prev, requiredProperties: [...(prev.requiredProperties || []), newProp as PropertyDef] }))
    setNewProp({ name: '', type: 'string', required: true })
  }

  const handleRemoveProp = (idx: number) => {
    setForm((prev) => ({ ...prev, requiredProperties: (prev.requiredProperties || []).filter((_, i) => i !== idx) }))
  }

  const handleAddLink = () => {
    if (!newLink.name || !newLink.targetType) return
    setForm((prev) => ({ ...prev, requiredLinks: [...(prev.requiredLinks || []), newLink as InterfaceLinkRequirement] }))
    setNewLink({ name: '', targetType: '', cardinality: 'MANY_TO_ONE' })
  }

  const handleRemoveLink = (idx: number) => {
    setForm((prev) => ({ ...prev, requiredLinks: (prev.requiredLinks || []).filter((_, i) => i !== idx) }))
  }

  const handleSubmit = async () => {
    if (!form.name) return
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
    if (!confirm('确定要删除此接口契约吗？')) return
    await deleteMutation.mutateAsync({ id, tenantId })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">接口契约</h1>
        <button onClick={openCreate} className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors text-sm font-medium">+ 新建接口</button>
      </div>
      <input type="text" placeholder="搜索..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-full max-w-md px-4 py-2 border rounded-lg dark:bg-slate-800 dark:border-slate-700 dark:text-white" />
      {isLoading ? <p className="text-slate-500">加载中...</p> : (
        <div className="bg-white dark:bg-slate-800 rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-700/50"><tr><th className="text-left px-4 py-3">名称</th><th className="text-left px-4 py-3">必需属性</th><th className="text-left px-4 py-3">必需关系</th><th className="text-left px-4 py-3">状态</th><th className="text-right px-4 py-3">操作</th></tr></thead>
            <tbody className="divide-y">
              {filtered.map((iface) => (
                <tr key={iface.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30">
                  <td className="px-4 py-3 font-medium">{iface.displayName || iface.name}</td>
                  <td className="px-4 py-3">{iface.requiredProperties.length}</td>
                  <td className="px-4 py-3">{iface.requiredLinks.length}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_STYLES[iface.status]}`}>{iface.status}</span></td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <button onClick={() => openEdit(iface)} className="text-blue-500 hover:text-blue-700 text-xs">编辑</button>
                    <button onClick={() => handleDelete(iface.id)} className="text-red-500 hover:text-red-700 text-xs">删除</button>
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
            <h2 className="text-lg font-bold mb-4 text-slate-900 dark:text-white">{editingId ? '编辑接口契约' : '新建接口契约'}</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-sm font-medium mb-1">名称</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" /></div>
                <div><label className="block text-sm font-medium mb-1">显示名</label><input value={form.displayName || ''} onChange={(e) => setForm({ ...form, displayName: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" /></div>
              </div>
              <div><label className="block text-sm font-medium mb-1">描述</label><textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white" rows={2} /></div>

              <div>
                <label className="block text-sm font-medium mb-2">必需属性</label>
                <div className="space-y-2">
                  {(form.requiredProperties || []).map((prop, idx) => (
                    <div key={idx} className="flex items-center gap-2 bg-slate-50 dark:bg-slate-700/50 px-3 py-2 rounded-lg">
                      <span className="text-sm font-medium">{prop.name}</span><span className="text-xs text-slate-500">({prop.type})</span>
                      <button onClick={() => handleRemoveProp(idx)} className="ml-auto text-red-500 text-xs">删除</button>
                    </div>
                  ))}
                  <div className="flex items-center gap-2">
                    <input value={newProp.name} onChange={(e) => setNewProp({ ...newProp, name: e.target.value })} placeholder="属性名" className="flex-1 px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white text-sm" />
                    <select value={newProp.type} onChange={(e) => setNewProp({ ...newProp, type: e.target.value as any })} className="px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white text-sm">
                      <option value="string">string</option><option value="int">int</option><option value="float">float</option><option value="date">date</option><option value="boolean">boolean</option><option value="json">json</option>
                    </select>
                    <button onClick={handleAddProp} className="px-3 py-2 bg-slate-200 dark:bg-slate-600 rounded-lg text-sm">添加</button>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">必需关系</label>
                <div className="space-y-2">
                  {(form.requiredLinks || []).map((link, idx) => (
                    <div key={idx} className="flex items-center gap-2 bg-slate-50 dark:bg-slate-700/50 px-3 py-2 rounded-lg">
                      <span className="text-sm font-medium">{link.name}</span><span className="text-xs text-slate-500">→ {link.targetType} ({link.cardinality})</span>
                      <button onClick={() => handleRemoveLink(idx)} className="ml-auto text-red-500 text-xs">删除</button>
                    </div>
                  ))}
                  <div className="flex items-center gap-2">
                    <input value={newLink.name} onChange={(e) => setNewLink({ ...newLink, name: e.target.value })} placeholder="关系名" className="flex-1 px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white text-sm" />
                    <input value={newLink.targetType} onChange={(e) => setNewLink({ ...newLink, targetType: e.target.value })} placeholder="目标类型" className="flex-1 px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white text-sm" />
                    <button onClick={handleAddLink} className="px-3 py-2 bg-slate-200 dark:bg-slate-600 rounded-lg text-sm">添加</button>
                  </div>
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
