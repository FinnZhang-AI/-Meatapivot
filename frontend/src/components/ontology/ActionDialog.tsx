import { useState } from 'react'
import type { ActionType } from '../../types/ontology'

interface Props {
  action: ActionType
  open: boolean
  onClose: () => void
  onExecute: (params: Record<string, any>) => Promise<void>
}

export default function ActionDialog({ action, open, onClose, onExecute }: Props) {
  const [params, setParams] = useState<Record<string, any>>({})
  const [executing, setExecuting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!open) return null

  const hasParams = action.parameters && action.parameters.length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setExecuting(true)
    try {
      await onExecute(hasParams ? params : {})
      onClose()
    } catch (err: any) {
      setError(err.message || '执行失败')
    } finally {
      setExecuting(false)
    }
  }

  const handleChange = (name: string, value: any) => {
    setParams((prev) => ({ ...prev, [name]: value }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-2xl w-full max-w-md mx-4 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
              {action.displayName || action.name}
            </h3>
            {action.description && (
              <p className="text-sm text-slate-500 mt-1">{action.description}</p>
            )}
          </div>

          <div className="px-6 py-4 space-y-4">
            {!hasParams ? (
              <p className="text-sm text-slate-500">此操作无需参数，点击确认即可执行。</p>
            ) : (
              action.parameters.map((param) => (
                <div key={param.name}>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                    {param.displayName || param.name}
                    {param.required && <span className="text-red-500 ml-1">*</span>}
                  </label>
                  {param.description && (
                    <p className="text-xs text-slate-400 mb-1">{param.description}</p>
                  )}
                  {param.type === 'boolean' ? (
                    <input
                      type="checkbox"
                      checked={!!params[param.name]}
                      onChange={(e) => handleChange(param.name, e.target.checked)}
                      className="rounded border-slate-300"
                    />
                  ) : param.type === 'object_ref' ? (
                    <input
                      type="text"
                      value={params[param.name] || ''}
                      onChange={(e) => handleChange(param.name, e.target.value)}
                      placeholder="输入对象 ID"
                      required={param.required}
                      className="w-full px-3 py-2 text-sm border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                    />
                  ) : param.type === 'date' ? (
                    <input
                      type="date"
                      value={params[param.name] || ''}
                      onChange={(e) => handleChange(param.name, e.target.value)}
                      required={param.required}
                      className="w-full px-3 py-2 text-sm border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                    />
                  ) : param.type === 'int' || param.type === 'float' ? (
                    <input
                      type="number"
                      value={params[param.name] ?? ''}
                      onChange={(e) => handleChange(param.name, param.type === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value))}
                      required={param.required}
                      className="w-full px-3 py-2 text-sm border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                    />
                  ) : (
                    <input
                      type="text"
                      value={params[param.name] || param.defaultValue || ''}
                      onChange={(e) => handleChange(param.name, e.target.value)}
                      required={param.required}
                      className="w-full px-3 py-2 text-sm border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                    />
                  )}
                </div>
              ))
            )}

            {error && (
              <div className="px-3 py-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
                {error}
              </div>
            )}
          </div>

          <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-700 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={executing}
              className="px-4 py-2 text-sm border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={executing}
              className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {executing ? '执行中...' : '确认执行'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
