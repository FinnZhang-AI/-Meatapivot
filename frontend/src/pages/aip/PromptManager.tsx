import { useState } from 'react'
import {
  usePromptTemplates,
  useCreatePromptTemplate,
  useUpdatePromptTemplate,
  useDeletePromptTemplate,
  useRenderPromptTemplate,
} from '../../hooks/useAIP'
import type { PromptTemplate, PromptTemplateCreate, PromptTemplateUpdate } from '../../types/aip'

interface FormState {
  id?: string
  name: string
  description: string
  templateText: string
  variables: string
  isAbTest: boolean
  abTestGroup: string
}

const emptyForm: FormState = {
  name: '',
  description: '',
  templateText: '',
  variables: '',
  isAbTest: false,
  abTestGroup: '',
}

export default function PromptManager() {
  const [page, setPage] = useState(1)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [isEditing, setIsEditing] = useState(false)
  const [renderVars, setRenderVars] = useState('')
  const [renderedText, setRenderedText] = useState('')
  const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplate | null>(null)

  const { data, isLoading, refetch } = usePromptTemplates(page)
  const createMutation = useCreatePromptTemplate()
  const updateMutation = useUpdatePromptTemplate()
  const deleteMutation = useDeletePromptTemplate()
  const renderMutation = useRenderPromptTemplate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const variables = form.variables
      .split(',')
      .map(v => v.trim())
      .filter(Boolean)

    try {
      if (isEditing && form.id) {
        const update: PromptTemplateUpdate = {
          description: form.description || undefined,
          templateText: form.templateText,
          variables,
          isAbTest: form.isAbTest,
          abTestGroup: form.abTestGroup || undefined,
        }
        await updateMutation.mutateAsync({ id: form.id, ...update })
      } else {
        const create: PromptTemplateCreate = {
          name: form.name,
          description: form.description || undefined,
          templateText: form.templateText,
          variables,
          isAbTest: form.isAbTest,
          abTestGroup: form.abTestGroup || undefined,
        }
        await createMutation.mutateAsync(create)
      }
      setForm(emptyForm)
      setIsEditing(false)
      refetch()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to save template')
    }
  }

  const handleEdit = (template: PromptTemplate) => {
    setForm({
      id: template.id,
      name: template.name,
      description: template.description || '',
      templateText: template.templateText,
      variables: (template.variables || []).join(', '),
      isAbTest: template.isAbTest,
      abTestGroup: template.abTestGroup || '',
    })
    setIsEditing(true)
    setSelectedTemplate(template)
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to archive this template?')) return
    try {
      await deleteMutation.mutateAsync(id)
      refetch()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete template')
    }
  }

  const handleRender = async () => {
    if (!selectedTemplate) return
    try {
      const variables: Record<string, any> = {}
      try {
        Object.assign(variables, JSON.parse(renderVars || '{}'))
      } catch {
        alert('Render variables must be valid JSON')
        return
      }
      const result = await renderMutation.mutateAsync({ id: selectedTemplate.id, variables })
      setRenderedText(result.renderedText)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to render template')
    }
  }

  const extractedVariables = Array.from(
    new Set((form.templateText.match(/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g) || []))
  )

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Prompt Template Manager</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Editor */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            {isEditing ? 'Edit Template' : 'Create Template'}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                disabled={isEditing}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <input
                type="text"
                value={form.description}
                onChange={e => setForm({ ...form, description: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Template</label>
              <textarea
                value={form.templateText}
                onChange={e => setForm({ ...form, templateText: e.target.value })}
                rows={8}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Use {{ variable }} syntax"
                required
              />
              <div className="mt-2 text-xs text-gray-500">
                Detected variables: {extractedVariables.join(', ') || 'none'}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Variables (comma separated)</label>
              <input
                type="text"
                value={form.variables}
                onChange={e => setForm({ ...form, variables: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="user_input, context"
              />
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={form.isAbTest}
                  onChange={e => setForm({ ...form, isAbTest: e.target.checked })}
                  className="rounded border-gray-300"
                />
                A/B Test
              </label>
              {form.isAbTest && (
                <input
                  type="text"
                  value={form.abTestGroup}
                  onChange={e => setForm({ ...form, abTestGroup: e.target.value })}
                  placeholder="Group A / Group B"
                  className="rounded-lg border border-gray-300 px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              )}
            </div>
            <div className="flex gap-2 pt-2">
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
              >
                {isEditing ? 'Update' : 'Create'}
              </button>
              {isEditing && (
                <button
                  type="button"
                  onClick={() => {
                    setForm(emptyForm)
                    setIsEditing(false)
                    setSelectedTemplate(null)
                  }}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200"
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        </div>

        {/* Preview / Render */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Preview</h2>
          {selectedTemplate ? (
            <div className="space-y-4">
              <div className="text-sm text-gray-600">
                <span className="font-medium">Selected:</span> {selectedTemplate.name} (v{selectedTemplate.version})
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Render Variables (JSON)</label>
                <textarea
                  value={renderVars}
                  onChange={e => setRenderVars(e.target.value)}
                  rows={4}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder='{"user_input": "hello", "context": "..."}'
                />
              </div>
              <button
                onClick={handleRender}
                className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700"
              >
                Render
              </button>
              {renderedText && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                  <div className="text-xs font-medium text-gray-500 mb-2">Rendered Output</div>
                  <pre className="text-sm text-gray-800 whitespace-pre-wrap">{renderedText}</pre>
                </div>
              )}
            </div>
          ) : (
            <div className="text-gray-400 text-sm">Select a template to preview</div>
          )}
        </div>
      </div>

      {/* List */}
      <div className="mt-8 bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-800">Templates</h2>
          <span className="text-sm text-gray-500">Total: {data?.total ?? 0}</span>
        </div>
        {isLoading ? (
          <div className="p-6 text-sm text-gray-400">Loading...</div>
        ) : (
          <>
            <table className="w-full text-sm text-left">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="px-6 py-3 font-medium">Name</th>
                  <th className="px-6 py-3 font-medium">Version</th>
                  <th className="px-6 py-3 font-medium">Variables</th>
                  <th className="px-6 py-3 font-medium">Usage</th>
                  <th className="px-6 py-3 font-medium">A/B Test</th>
                  <th className="px-6 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data?.items.map(template => (
                  <tr
                    key={template.id}
                    className={`hover:bg-gray-50 cursor-pointer ${selectedTemplate?.id === template.id ? 'bg-blue-50' : ''}`}
                    onClick={() => setSelectedTemplate(template)}
                  >
                    <td className="px-6 py-3">
                      <div className="font-medium text-gray-900">{template.name}</div>
                      <div className="text-xs text-gray-500 truncate max-w-xs">{template.description}</div>
                    </td>
                    <td className="px-6 py-3">{template.version}</td>
                    <td className="px-6 py-3">{(template.variables || []).join(', ')}</td>
                    <td className="px-6 py-3">{template.usageCount}</td>
                    <td className="px-6 py-3">
                      {template.isAbTest ? (
                        <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs">
                          {template.abTestGroup || 'A/B'}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-6 py-3">
                      <div className="flex gap-2">
                        <button
                          onClick={e => {
                            e.stopPropagation()
                            handleEdit(template)
                          }}
                          className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                        >
                          Edit
                        </button>
                        <button
                          onClick={e => {
                            e.stopPropagation()
                            handleDelete(template.id)
                          }}
                          className="text-red-600 hover:text-red-800 text-xs font-medium"
                        >
                          Archive
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data && data.pages > 1 && (
              <div className="px-6 py-4 border-t border-gray-200 flex justify-center gap-2">
                {Array.from({ length: data.pages }, (_, i) => i + 1).map(p => (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`px-3 py-1 rounded text-sm ${
                      p === page ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
