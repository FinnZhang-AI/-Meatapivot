import { useAuth } from '../../hooks/useAuth'
import { useActionTypes, useDeleteActionType } from '../../hooks/useOntology'

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700',
  active: 'bg-green-100 text-green-700',
  archived: 'bg-red-100 text-red-700',
}

export default function ActionTypeList() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id || ''
  const { data: actionTypes, isLoading } = useActionTypes(tenantId)
  const deleteMutation = useDeleteActionType()

  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除此动作类型吗？')) return
    await deleteMutation.mutateAsync({ id, tenantId })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">动作类型</h1>
        <button className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium opacity-50 cursor-not-allowed">
          + 新建动作类型
        </button>
      </div>

      {isLoading && <p className="text-slate-500">加载中...</p>}

      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-700/50">
            <tr>
              <th className="text-left px-4 py-3 font-semibold">名称</th>
              <th className="text-left px-4 py-3 font-semibold">目标类型</th>
              <th className="text-left px-4 py-3 font-semibold">执行方式</th>
              <th className="text-left px-4 py-3 font-semibold">状态</th>
              <th className="text-right px-4 py-3 font-semibold">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {(actionTypes || []).map((at) => (
              <tr key={at.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30">
                <td className="px-4 py-3 font-medium">{at.name}</td>
                <td className="px-4 py-3 text-slate-500">{at.targetObjectTypeName || at.targetObjectTypeId}</td>
                <td className="px-4 py-3 text-slate-500">{at.executionType}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[at.status] || ''}`}>
                    {at.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => handleDelete(at.id)} className="text-red-500 hover:text-red-700 text-xs">删除</button>
                </td>
              </tr>
            ))}
            {(actionTypes || []).length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400">暂无动作类型</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
