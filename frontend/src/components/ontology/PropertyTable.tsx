import { useState } from 'react'
import type { PropertyDef } from '../../types/ontology'

interface Props {
  properties: Record<string, any>
  schema?: PropertyDef[]
  editable?: boolean
  onChange?: (properties: Record<string, any>) => void
}

export default function PropertyTable({ properties, schema, editable, onChange }: Props) {
  const [editing, setEditing] = useState<Record<string, any> | null>(null)

  const entries = schema
    ? schema.map((s) => ({ key: s.name, value: properties[s.name], def: s }))
    : Object.entries(properties).map(([key, value]) => ({ key, value, def: undefined as PropertyDef | undefined }))

  const handleEdit = () => {
    setEditing({ ...properties })
  }

  const handleSave = () => {
    if (editing && onChange) {
      onChange(editing)
    }
    setEditing(null)
  }

  const handleCancel = () => {
    setEditing(null)
  }

  const getInputType = (type?: string) => {
    switch (type) {
      case 'int':
      case 'float':
        return 'number'
      case 'boolean':
        return 'checkbox'
      case 'date':
        return 'date'
      default:
        return 'text'
    }
  }

  const displayValue = (value: any, type?: string) => {
    if (value === undefined || value === null) return '-'
    if (type === 'json') return JSON.stringify(value)
    if (type === 'boolean') return value ? '是' : '否'
    return String(value)
  }

  return (
    <div className="space-y-3">
      {editable && !editing && (
        <div className="flex justify-end">
          <button
            onClick={handleEdit}
            className="px-3 py-1.5 text-sm bg-slate-100 dark:bg-slate-700 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
          >
            编辑属性
          </button>
        </div>
      )}
      {editing && (
        <div className="flex justify-end gap-2">
          <button onClick={handleCancel} className="px-3 py-1.5 text-sm border rounded-lg">取消</button>
          <button onClick={handleSave} className="px-3 py-1.5 text-sm bg-primary text-white rounded-lg">保存</button>
        </div>
      )}

      <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-700/50">
            <tr>
              <th className="text-left px-4 py-2 font-semibold text-slate-600 dark:text-slate-300">属性名</th>
              <th className="text-left px-4 py-2 font-semibold text-slate-600 dark:text-slate-300">类型</th>
              <th className="text-left px-4 py-2 font-semibold text-slate-600 dark:text-slate-300">值</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {entries.map(({ key, value, def }) => (
              <tr key={key}>
                <td className="px-4 py-2 font-medium text-slate-900 dark:text-white">
                  {def?.displayName || key}
                  {def?.required && <span className="text-red-500 ml-1">*</span>}
                </td>
                <td className="px-4 py-2 text-slate-500 text-xs">{def?.type || 'unknown'}</td>
                <td className="px-4 py-2">
                  {editing ? (
                    def?.type === 'boolean' ? (
                      <input
                        type="checkbox"
                        checked={!!editing[key]}
                        onChange={(e) => setEditing({ ...editing, [key]: e.target.checked })}
                      />
                    ) : def?.type === 'json' ? (
                      <textarea
                        value={typeof editing[key] === 'object' ? JSON.stringify(editing[key], null, 2) : String(editing[key] || '')}
                        onChange={(e) => {
                          try {
                            setEditing({ ...editing, [key]: JSON.parse(e.target.value) })
                          } catch {
                            setEditing({ ...editing, [key]: e.target.value })
                          }
                        }}
                        className="w-full px-2 py-1 border rounded dark:bg-slate-700 dark:border-slate-600 dark:text-white text-xs font-mono"
                        rows={3}
                      />
                    ) : (
                      <input
                        type={getInputType(def?.type)}
                        value={editing[key] ?? ''}
                        onChange={(e) => setEditing({ ...editing, [key]: e.target.value })}
                        className="w-full px-2 py-1 border rounded dark:bg-slate-700 dark:border-slate-600 dark:text-white text-xs"
                      />
                    )
                  ) : (
                    <span className="text-slate-700 dark:text-slate-300">{displayValue(value, def?.type)}</span>
                  )}
                </td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-slate-400">暂无属性</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
