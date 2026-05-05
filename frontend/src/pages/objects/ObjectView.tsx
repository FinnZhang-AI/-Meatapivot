import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useSubgraph } from '../../hooks/useOntology'
import PropertyTable from '../../components/ontology/PropertyTable'
import OntologyGraph from '../../components/ontology/OntologyGraph'
import type { GraphNode } from '../../types/ontology'

// Mock data for demo - in production these would come from API
const MOCK_OBJECT = {
  id: 'demo-id',
  objectKey: 'OBJ-001',
  objectTypeName: 'Customer',
  properties: {
    name: '张三',
    email: 'zhangsan@example.com',
    age: 35,
    vip: true,
  },
}

const MOCK_RELATED = [
  { id: 'rel-1', linkTypeName: 'hasOrder', targetObjectKey: 'ORD-2024-001', targetObjectType: 'Order' },
  { id: 'rel-2', linkTypeName: 'hasOrder', targetObjectKey: 'ORD-2024-002', targetObjectType: 'Order' },
  { id: 'rel-3', linkTypeName: 'managedBy', targetObjectKey: 'EMP-001', targetObjectType: 'Employee' },
]

export default function ObjectView() {
  const { type, id } = useParams<{ type: string; id: string }>()
  const { data: subgraph, isLoading: graphLoading } = useSubgraph(id || '')
  const [showGraph, setShowGraph] = useState(true)

  const handleNodeClick = (node: GraphNode) => {
    console.log('Clicked node:', node)
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Link to="/ontology/object-types" className="hover:text-primary">对象类型</Link>
        <span>/</span>
        <Link to={`/ontology/object-types/${type}`} className="hover:text-primary">{type}</Link>
        <span>/</span>
        <span className="text-slate-900 dark:text-white font-medium">{MOCK_OBJECT.objectKey}</span>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{MOCK_OBJECT.objectKey}</h1>
          <p className="text-slate-500 text-sm mt-1">{MOCK_OBJECT.objectTypeName}</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="px-4 py-2 bg-primary text-white rounded-lg text-sm">执行动作</button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Properties */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
            <h2 className="text-lg font-semibold mb-4">属性</h2>
            <PropertyTable
              properties={MOCK_OBJECT.properties}
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
                <div className="h-80 flex items-center justify-center text-slate-400">加载图谱中...</div>
              ) : (
                <OntologyGraph
                  nodes={subgraph?.nodes || [
                    { id: 'n1', label: MOCK_OBJECT.objectKey, objectType: MOCK_OBJECT.objectTypeName },
                    { id: 'n2', label: 'ORD-001', objectType: 'Order' },
                    { id: 'n3', label: 'ORD-002', objectType: 'Order' },
                    { id: 'n4', label: 'EMP-001', objectType: 'Employee' },
                  ]}
                  edges={subgraph?.edges || [
                    { id: 'e1', source: 'n1', target: 'n2', label: 'hasOrder' },
                    { id: 'e2', source: 'n1', target: 'n3', label: 'hasOrder' },
                    { id: 'e3', source: 'n1', target: 'n4', label: 'managedBy' },
                  ]}
                  onNodeClick={handleNodeClick}
                  height={320}
                />
              )
            )}
          </div>
        </div>

        {/* Right: Related Objects */}
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
            <h2 className="text-lg font-semibold mb-4">关联对象</h2>
            <div className="space-y-3">
              {MOCK_RELATED.map((rel) => (
                <div key={rel.id} className="flex items-center gap-3 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{rel.targetObjectKey}</div>
                    <div className="text-xs text-slate-500">{rel.targetObjectType}</div>
                  </div>
                  <span className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded-full shrink-0">
                    {rel.linkTypeName}
                  </span>
                </div>
              ))}
              {MOCK_RELATED.length === 0 && (
                <div className="text-center text-slate-400 py-4">暂无关联对象</div>
              )}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
            <h2 className="text-lg font-semibold mb-4">可用动作</h2>
            <div className="space-y-2">
              <button className="w-full px-4 py-2 text-left text-sm bg-slate-50 dark:bg-slate-700/50 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
                更新状态
              </button>
              <button className="w-full px-4 py-2 text-left text-sm bg-slate-50 dark:bg-slate-700/50 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
                发送通知
              </button>
              <button className="w-full px-4 py-2 text-left text-sm bg-slate-50 dark:bg-slate-700/50 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
                导出数据
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
