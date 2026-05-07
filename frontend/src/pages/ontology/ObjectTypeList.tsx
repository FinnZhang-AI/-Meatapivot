import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import {
  useObjectTypes,
  useCreateObjectType,
  useUpdateObjectType,
  useDeleteObjectType,
} from '../../hooks/useOntology'
import type { ObjectType, PropertyDef } from '../../types/ontology'

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700',
  active: 'bg-green-100 text-green-700',
  archived: 'bg-red-100 text-red-700',
}

const COMPILE_STYLES: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  compiled: 'bg-green-100 text-green-700',
  error: 'bg-red-100 text-red-700',
}

const EMPTY_FORM: Partial<ObjectType> = {
  name: '',
  displayName: '',
  description: '',
  icon: 'box',
  properties: [],
  implementedInterfaces: [],
}

export default function ObjectTypeList() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id || ''
  const { data: objectTypes, isLoading, error } = useObjectTypes(tenantId)
  const createMutation = useCreateObjectType()
  const updateMutation = useUpdateObjectType()
  const deleteMutation = useDeleteObjectType()

  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<Partial<ObjectType>>(EMPTY_FORM)
  const [newProp, setNewProp] = useState<Partial<PropertyDef>>({
    name: '',
    type: 'string',
    required: false,
  })

  const filtered = (objectTypes || []).filter((ot) =>
    ot.name.toLowerCase().includes(search.toLowerCase()) ||
    (ot.displayName || '').toLowerCase().includes(search.toLowerCase())
  )

  const openCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setShowModal(true)
  }

  const openEdit = (ot: ObjectType) => {
    setEditingId(ot.id)
    setForm({
      name: ot.name,
      displayName: ot.displayName || '',
      description: ot.description || '',
      icon: ot.icon || 'box',
      properties: ot.properties ? [...ot.properties] : [],
      implementedInterfaces: ot.implementedInterfaces ? [...ot.implementedInterfaces] : [],
    })
    setShowModal(true)
  }

  const handleAddProperty = () => {
    if (!newProp.name) return
    setForm((prev) => ({
      ...prev,
      properties: [...(prev.properties || []), newProp as PropertyDef],
    }))
    setNewProp({ name: '', type: 'string', required: false })
  }

  const handleRemoveProperty = (idx: number) => {
    setForm((prev) => ({
      ...prev,
      properties: (prev.properties || []).filter((_, i) => i !== idx),
    }))
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
    if (!confirm('确定要删除此对象类型吗？')) return
    await deleteMutation.mutateAsync({ id, tenantId })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">对象类型</h1>
        <button
          onClick={openCreate}
          className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors text-sm font-medium"
        >
          + 新建对象类型
        </button>
      </div>

      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="搜索对象类型..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-md px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
        />
      </div>

      {isLoading && <p className="text-slate-500">加载中...</p>}
      {error && <p className="text-red-500">加载失败: {error.message}</p>}

      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-700/50">
            <tr>
              <th className="text-left px-4 py-3 font-semibold text-slate-600 dark:text-slate-300">名称</th>
              <th className="text-left px-4 py-3 font-semibold text-slate-600 dark:text-slate-300">显示名</th>
              <th className="text-left px-4 py-3 font-semibold text-slate-600 dark:text-slate-300">状态</th>
              <th className="text-left px-4 py-3 font-semibold text-slate-600 dark:text-slate-300">编译状态</th>
              <th className="text-left px-4 py-3 font-semibold text-slate-600 dark:text-slate-300">版本</th>
              <th className="text-right px-4 py-3 font-semibold text-slate-600 dark:text-slate-300">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {filtered.map((ot) => (
              <tr key={ot.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30">
                <td className="px-4 py-3">
                  <Link to={`/ontology/object-types/${ot.id}`} className="font-medium text-primary hover:underline">
                    {ot.name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{ot.displayName || '-'}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[ot.status] || 'bg-slate-100'}`}>
                    {ot.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${COMPILE_STYLES[ot.compileStatus] || 'bg-slate-100'}`}>
                    {ot.compileStatus}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{ot.version}</td>
                <td className="px-4 py-3 text-right space-x-2">
                  <Link to={`/ontology/object-types/${ot.id}`} className="text-primary hover:underline text-xs">查看</Link>
                  <button onClick={() => openEdit(ot)} className="text-blue-500 hover:text-blue-700 text-xs">编辑</button>
                  <button onClick={() => handleDelete(ot.id)} className="text-red-500 hover:text-red-700 text-xs">删除</button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                  暂无对象类型
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create / Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
            <h2 className="text-lg font-bold mb-4 text-slate-900 dark:text-white">
              {editingId ? '编辑对象类型' : '新建对象类型'}
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">名称</label>
                  <input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                    placeholder="e.g. Customer"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">显示名</label>
                  <input
                    value={form.displayName || ''}
                    onChange={(e) => setForm({ ...form, displayName: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                    placeholder="e.g. 客户"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">描述</label>
                <textarea
                  value={form.description || ''}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                  rows={2}
                />
              </div>

              {/* Properties */}
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">属性定义</label>
                <div className="space-y-2">
                  {(form.properties || []).map((prop, idx) => (
                    <div key={idx} className="flex items-center gap-2 bg-slate-50 dark:bg-slate-700/50 px-3 py-2 rounded-lg">
                      <span className="text-sm font-medium">{prop.name}</span>
                      <span className="text-xs text-slate-500">({prop.type})</span>
                      {prop.required && <span className="text-xs text-red-500">*必填</span>}
                      <button onClick={() => handleRemoveProperty(idx)} className="ml-auto text-red-500 text-xs">删除</button>
                    </div>
                  ))}
                  <div className="flex items-center gap-2">
                    <input
                      value={newProp.name}
                      onChange={(e) => setNewProp({ ...newProp, name: e.target.value })}
                      placeholder="属性名"
                      className="flex-1 px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white text-sm"
                    />
                    <select
                      value={newProp.type}
                      onChange={(e) => setNewProp({ ...newProp, type: e.target.value as any })}
                      className="px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white text-sm"
                    >
                      <option value="string">string</option>
                      <option value="int">int</option>
                      <option value="float">float</option>
                      <option value="date">date</option>
                      <option value="boolean">boolean</option>
                      <option value="json">json</option>
                    </select>
                    <label className="flex items-center gap-1 text-sm text-slate-600 dark:text-slate-400">
                      <input
                        type="checkbox"
                        checked={newProp.required || false}
                        onChange={(e) => setNewProp({ ...newProp, required: e.target.checked })}
                      />
                      必填
                    </label>
                    <button onClick={handleAddProperty} className="px-3 py-2 bg-slate-200 dark:bg-slate-600 rounded-lg text-sm">添加</button>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleSubmit} className="px-4 py-2 bg-primary text-white rounded-lg text-sm">
                {editingId ? '保存' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
