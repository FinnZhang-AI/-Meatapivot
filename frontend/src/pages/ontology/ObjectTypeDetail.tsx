import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  useObjectType,
  useObjects,
  useCreateObject,
  useLinkTypes,
  useActionTypes,
} from '../../hooks/useOntology'
import PropertyTable from '../../components/ontology/PropertyTable'
import type { OntologyObject, PropertyDef } from '../../types/ontology'

const TABS = ['概览', '属性', '关系', '动作', '对象实例']

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700',
  active: 'bg-green-100 text-green-700',
  archived: 'bg-red-100 text-red-700',
}

export default function ObjectTypeDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: objectType, isLoading: typeLoading } = useObjectType(id || '')
  const { data: objects, isLoading: objectsLoading } = useObjects(id || '')
  const { data: linkTypes } = useLinkTypes(objectType?.tenantId || '')
  const { data: actionTypes } = useActionTypes(objectType?.tenantId || '')
  const createObjectMutation = useCreateObject()

  const [activeTab, setActiveTab] = useState('概览')
  const [showCreateObjectModal, setShowCreateObjectModal] = useState(false)
  const [newObject, setNewObject] = useState<Partial<OntologyObject>>({
    objectKey: '',
    properties: {},
  })

  if (typeLoading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!objectType) return <div className="p-6 text-red-500">对象类型不存在</div>

  const relatedLinks = (linkTypes || []).filter(
    (lt) => lt.sourceObjectTypeId === id || lt.targetObjectTypeId === id
  )
  const relatedActions = (actionTypes || []).filter(
    (at) => at.targetObjectTypeId === id
  )

  const handleCreateObject = async () => {
    if (!newObject.objectKey) return
    await createObjectMutation.mutateAsync({
      ...newObject,
      objectTypeId: id,
    })
    setShowCreateObjectModal(false)
    setNewObject({ objectKey: '', properties: {} })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/ontology/object-types')}
          className="text-slate-500 hover:text-slate-700"
        >
          ← 返回
        </button>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{objectType.displayName || objectType.name}</h1>
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[objectType.status]}`}>
          {objectType.status}
        </span>
        <span className="text-xs text-slate-400">v{objectType.version}</span>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-700">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab
                ? 'text-primary border-b-2 border-primary'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[300px]">
        {activeTab === '概览' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
                <h3 className="text-sm font-semibold text-slate-500 mb-2">基本信息</h3>
                <div className="space-y-2 text-sm">
                  <div><span className="text-slate-500">名称:</span> {objectType.name}</div>
                  <div><span className="text-slate-500">显示名:</span> {objectType.displayName || '-'}</div>
                  <div><span className="text-slate-500">描述:</span> {objectType.description || '-'}</div>
                  <div><span className="text-slate-500">Neo4j 标签:</span> {objectType.neo4jLabel || '-'}</div>
                  <div><span className="text-slate-500">编译状态:</span> {objectType.compileStatus}</div>
                </div>
              </div>
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
                <h3 className="text-sm font-semibold text-slate-500 mb-2">统计</h3>
                <div className="space-y-2 text-sm">
                  <div><span className="text-slate-500">属性数:</span> {objectType.properties.length}</div>
                  <div><span className="text-slate-500">实现接口:</span> {objectType.implementedInterfaces.length}</div>
                  <div><span className="text-slate-500">对象实例:</span> {(objects || []).length}</div>
                  <div><span className="text-slate-500">关系类型:</span> {relatedLinks.length}</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === '属性' && (
          <PropertyTable
            properties={objectType.properties.reduce((acc, p) => {
              acc[p.name] = p.defaultValue ?? ''
              return acc
            }, {} as Record<string, any>)}
            schema={objectType.properties}
            editable={false}
          />
        )}

        {activeTab === '关系' && (
          <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
            {relatedLinks.length === 0 ? (
              <div className="p-8 text-center text-slate-400">暂无关系类型</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-slate-50 dark:bg-slate-700/50">
                  <tr>
                    <th className="text-left px-4 py-3">名称</th>
                    <th className="text-left px-4 py-3">方向</th>
                    <th className="text-left px-4 py-3">目标类型</th>
                    <th className="text-left px-4 py-3">基数</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                  {relatedLinks.map((lt) => (
                    <tr key={lt.id}>
                      <td className="px-4 py-3 font-medium">{lt.name}</td>
                      <td className="px-4 py-3">
                        {lt.sourceObjectTypeId === id ? '→  outgoing' : '←  incoming'}
                      </td>
                      <td className="px-4 py-3">
                        {lt.sourceObjectTypeId === id ? lt.targetObjectTypeName : lt.sourceObjectTypeName}
                      </td>
                      <td className="px-4 py-3">{lt.cardinality}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {activeTab === '动作' && (
          <div className="space-y-3">
            {relatedActions.length === 0 ? (
              <div className="p-8 text-center text-slate-400 bg-white dark:bg-slate-800 rounded-lg border">暂无动作类型</div>
            ) : (
              relatedActions.map((action) => (
                <div key={action.id} className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium">{action.displayName || action.name}</span>
                      <span className="ml-2 text-xs text-slate-500">({action.executionType})</span>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-700">{action.parameters.length} 参数</span>
                  </div>
                  <p className="text-sm text-slate-500 mt-1">{action.description || '无描述'}</p>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === '对象实例' && (
          <div className="space-y-4">
            <div className="flex justify-end">
              <button
                onClick={() => setShowCreateObjectModal(true)}
                className="px-4 py-2 bg-primary text-white rounded-lg text-sm"
              >
                + 新建对象
              </button>
            </div>
            <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
              {objectsLoading ? (
                <div className="p-8 text-center text-slate-400">加载中...</div>
              ) : (objects || []).length === 0 ? (
                <div className="p-8 text-center text-slate-400">暂无对象实例</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-700/50">
                    <tr>
                      <th className="text-left px-4 py-3">对象 Key</th>
                      <th className="text-left px-4 py-3">属性</th>
                      <th className="text-left px-4 py-3">状态</th>
                      <th className="text-right px-4 py-3">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                    {(objects || []).map((obj) => (
                      <tr key={obj.id}>
                        <td className="px-4 py-3 font-medium">
                          <Link to={`/objects/${objectType.name}/${obj.id}`} className="text-primary hover:underline">
                            {obj.objectKey}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-slate-500 truncate max-w-xs">
                          {JSON.stringify(obj.properties).slice(0, 60)}...
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_STYLES[obj.status] || ''}`}>
                            {obj.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Link to={`/objects/${objectType.name}/${obj.id}`} className="text-primary text-xs hover:underline">查看</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Create Object Modal */}
      {showCreateObjectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-bold mb-4">新建 {objectType.displayName || objectType.name} 实例</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">对象 Key</label>
                <input
                  value={newObject.objectKey}
                  onChange={(e) => setNewObject({ ...newObject, objectKey: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                />
              </div>
              {objectType.properties.map((prop) => (
                <div key={prop.name}>
                  <label className="block text-sm font-medium mb-1">
                    {prop.displayName || prop.name}
                    {prop.required && <span className="text-red-500">*</span>}
                  </label>
                  {prop.type === 'boolean' ? (
                    <input
                      type="checkbox"
                      checked={!!newObject.properties?.[prop.name]}
                      onChange={(e) =>
                        setNewObject({
                          ...newObject,
                          properties: { ...newObject.properties, [prop.name]: e.target.checked },
                        })
                      }
                    />
                  ) : (
                    <input
                      type={prop.type === 'int' || prop.type === 'float' ? 'number' : 'text'}
                      value={newObject.properties?.[prop.name] || ''}
                      onChange={(e) =>
                        setNewObject({
                          ...newObject,
                          properties: { ...newObject.properties, [prop.name]: e.target.value },
                        })
                      }
                      className="w-full px-3 py-2 border rounded-lg dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                    />
                  )}
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowCreateObjectModal(false)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
              <button onClick={handleCreateObject} className="px-4 py-2 bg-primary text-white rounded-lg text-sm">创建</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
