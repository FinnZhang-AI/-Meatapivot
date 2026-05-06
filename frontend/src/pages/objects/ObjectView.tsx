import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  useObject,
  useObjectLinks,
  useActionTypes,
  useSubgraph,
  useExecuteAction,
} from '../../hooks/useOntology'
import { useAuth } from '../../hooks/useAuth'
import PropertyTable from '../../components/ontology/PropertyTable'
import OntologyGraph from '../../components/ontology/OntologyGraph'
import RelatedObjects from '../../components/ontology/RelatedObjects'
import type { GraphNode, OntologyLink } from '../../types/ontology'

export default function ObjectView() {
  const { type, id } = useParams<{ type: string; id: string }>()
  const { user } = useAuth()
  const tenantId = user?.tenant_id || ''

  const { data: obj, isLoading: objLoading } = useObject(id || '')
  const { data: links, isLoading: linksLoading } = useObjectLinks(id || '')
  const { data: actionTypes } = useActionTypes(tenantId)
  const { data: subgraph, isLoading: graphLoading } = useSubgraph(id || '')
  const executeAction = useExecuteAction()

  const [showGraph, setShowGraph] = useState(true)
  const [activeAction, setActiveAction] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const objectTypeName = type || obj?.objectTypeName || 'Unknown'

  const relatedActions = (actionTypes || []).filter(
    (at) => at.targetObjectTypeId === obj?.objectTypeId
  )

  const navigate = useNavigate()

  const handleNodeClick = (node: GraphNode) => {
    if (node.properties?.object_id) {
      navigate(`/objects/${node.objectType}/${node.properties.object_id}`)
    }
  }

  const handleExecuteAction = async (actionId: string) => {
    if (!id) return
    setActiveAction(actionId)
    try {
      await executeAction.mutateAsync({
        actionTypeId: actionId,
        targetObjectId: id,
      })
      setActionMessage({ type: 'success', text: '动作执行成功' })
    } catch (e: any) {
      setActionMessage({ type: 'error', text: `执行失败: ${e.message}` })
    } finally {
      setActiveAction(null)
      setTimeout(() => setActionMessage(null), 3000)
    }
  }

  if (objLoading) {
    return <div className="p-6 text-slate-500">加载对象数据中...</div>
  }

  if (!obj) {
    return <div className="p-6 text-red-500">对象不存在或已被删除</div>
  }

  // Build RelatedObjects-compatible links from objectLinks + subgraph edges
  const enrichedLinks: OntologyLink[] = (links || []).map((l) => ({
    ...l,
    targetObjectKey:
      l.sourceObjectId === id
        ? l.targetObjectId.slice(0, 8)
        : l.sourceObjectId.slice(0, 8),
    targetObjectType: l.linkTypeName || 'Unknown',
  }))

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Link to="/ontology/object-types" className="hover:text-primary">
          对象类型
        </Link>
        <span>/</span>
        <Link
          to={`/ontology/object-types/${obj.objectTypeId}`}
          className="hover:text-primary"
        >
          {objectTypeName}
        </Link>
        <span>/</span>
        <span className="text-slate-900 dark:text-white font-medium">
          {obj.objectKey}
        </span>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            {obj.objectKey}
          </h1>
          <p className="text-slate-500 text-sm mt-1">{objectTypeName}</p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              obj.status === 'active'
                ? 'bg-green-100 text-green-700'
                : 'bg-slate-100 text-slate-700'
            }`}
          >
            {obj.status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column */}
        <div className="lg:col-span-2 space-y-6">
          {/* Properties */}
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
            <h2 className="text-lg font-semibold mb-4">属性</h2>
            <PropertyTable
              properties={obj.properties || {}}
              editable={true}
              onChange={(props) => console.log('Updated props:', props)}
            />
          </div>

          {/* Subgraph */}
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">关联图谱</h2>
              <button
                onClick={() => setShowGraph(!showGraph)}
                className="text-sm text-primary hover:underline"
              >
                {showGraph ? '隐藏' : '显示'}
              </button>
            </div>
            {showGraph && (
              graphLoading ? (
                <div className="h-80 flex items-center justify-center text-slate-400">
                  加载图谱中...
                </div>
              ) : (
                <OntologyGraph
                  nodes={subgraph?.nodes || []}
                  edges={subgraph?.edges || []}
                  onNodeClick={handleNodeClick}
                  height={320}
                />
              )
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Action message */}
          {actionMessage && (
            <div
              className={`px-4 py-3 rounded-lg text-sm font-medium ${
                actionMessage.type === 'success'
                  ? 'bg-green-50 text-green-700 border border-green-200'
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}
            >
              {actionMessage.text}
            </div>
          )}

          {/* Related Objects */}
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
            <h2 className="text-lg font-semibold mb-4">关联对象</h2>
            {linksLoading ? (
              <div className="text-slate-400 py-4 text-center">加载中...</div>
            ) : (
              <RelatedObjects objectId={id || ''} links={enrichedLinks} />
            )}
          </div>

          {/* Actions */}
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
            <h2 className="text-lg font-semibold mb-4">可用动作</h2>
            <div className="space-y-2">
              {relatedActions.length === 0 ? (
                <div className="text-sm text-slate-400">暂无可用动作</div>
              ) : (
                relatedActions.map((action) => (
                  <button
                    key={action.id}
                    disabled={activeAction === action.id}
                    onClick={() => handleExecuteAction(action.id)}
                    className="w-full px-4 py-2 text-left text-sm bg-slate-50 dark:bg-slate-700/50 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
                  >
                    <span className="font-medium">
                      {action.displayName || action.name}
                    </span>
                    <span className="ml-2 text-xs text-slate-500">
                      ({action.executionType})
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
