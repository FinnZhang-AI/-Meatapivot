import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
  type EdgeChange,
  Handle,
  Position,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useAuth } from '../../hooks/useAuth'
import { API_BASE_URL, getAuthHeaders, handleResponse } from '../../hooks/useOntology'

interface WorkshopAppData {
  id: string
  name: string
  graph: { nodes: Node[]; edges: Edge[]; viewport?: { x: number; y: number; zoom: number } }
}

// ---------------------------------------------------------------------------
// Node components — S3-3 MVP: Table, Chart, Action (Filter and LinkNav later)
// ---------------------------------------------------------------------------

interface BaseNodeProps {
  data: { label: string; [key: string]: unknown }
  selected?: boolean
}

const NodeShell = ({ kind, label, color, children, selected }: {
  kind: string
  label: string
  color: string
  children?: React.ReactNode
  selected?: boolean
}) => (
  <div
    className={`px-3 py-2 rounded-lg border-2 bg-white dark:bg-slate-800 shadow-sm min-w-[160px] ${
      selected ? 'border-primary' : 'border-slate-200 dark:border-slate-700'
    }`}
  >
    <Handle type="target" position={Position.Left} className="!bg-slate-400" />
    <div className="flex items-center gap-2 mb-1">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      <span className="text-[10px] uppercase tracking-wider text-slate-500">{kind}</span>
    </div>
    <div className="text-sm font-medium text-slate-900 dark:text-white">{label}</div>
    {children}
    <Handle type="source" position={Position.Right} className="!bg-slate-400" />
  </div>
)

const TableNode = ({ data, selected }: BaseNodeProps) => (
  <NodeShell kind="Table" label={data.label as string} color="bg-blue-500" selected={selected}>
    <p className="text-xs text-slate-500 mt-1">查询对象类型实例</p>
  </NodeShell>
)

const ChartNode = ({ data, selected }: BaseNodeProps) => {
  const upstream = (data.upstream as string) || ''
  return (
    <NodeShell kind="Chart" label={data.label as string} color="bg-emerald-500" selected={selected}>
      <p className="text-xs text-slate-500 mt-1">
        {upstream ? `↑ 消费: ${upstream}` : '未连接数据源'}
      </p>
    </NodeShell>
  )
}

const ActionNode = ({ data, selected }: BaseNodeProps) => (
  <NodeShell kind="Action" label={data.label as string} color="bg-amber-500" selected={selected}>
    <p className="text-xs text-slate-500 mt-1">触发 Action</p>
  </NodeShell>
)

const nodeTypes = {
  table: TableNode,
  chart: ChartNode,
  action: ActionNode,
}

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------

const WORKSPACE_KINDS = [
  { type: 'table', label: 'Object Table', desc: '查询某 ObjectType 的实例' },
  { type: 'chart', label: 'Chart', desc: '消费上游数据画图' },
  { type: 'action', label: 'Action Button', desc: '触发 Action' },
]

const WorkshopEditor = () => {
  const { appId } = useParams<{ appId: string }>()
  const navigate = useNavigate()
  const { user, token } = useAuth()
  const tenantId = user?.tenant_id || ''

  const [appName, setAppName] = useState('')
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)

  // Load app on mount
  useEffect(() => {
    if (!appId) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}/workshop/apps/${appId}?tenant_id=${encodeURIComponent(tenantId)}`,
          { headers: getAuthHeaders(token) }
        )
        const data = await handleResponse<WorkshopAppData>(res)
        if (cancelled) return
        setAppName(data.name)
        setNodes((data.graph?.nodes as Node[]) || [])
        setEdges((data.graph?.edges as Edge[]) || [])
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [appId, tenantId, token])

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds))
  }, [])
  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((eds) => applyEdgeChanges(changes, eds))
  }, [])
  const onConnect = useCallback((connection: Connection) => {
    setEdges((eds) => addEdge({ ...connection, animated: true }, eds))
  }, [])

  // When a Chart node receives an incoming edge, copy the source's label
  // into the chart's data.upstream so the node can show what it consumes.
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.type !== 'chart') return n
        const incoming = edges.find((e) => e.target === n.id)
        if (!incoming) {
          if (n.data.upstream) return { ...n, data: { ...n.data, upstream: '' } }
          return n
        }
        const source = nds.find((x) => x.id === incoming.source)
        return {
          ...n,
          data: { ...n.data, upstream: (source?.data.label as string) || incoming.source },
        }
      })
    )
  }, [edges])

  const addNode = (type: string) => {
    const id = `${type}_${Math.random().toString(36).slice(2, 8)}`
    const newNode: Node = {
      id,
      type,
      position: { x: 80 + Math.random() * 200, y: 80 + Math.random() * 200 },
      data: { label: `${type} ${nodes.filter((n) => n.type === type).length + 1}` },
    }
    setNodes((nds) => [...nds, newNode])
  }

  const updateNodeLabel = (id: string, label: string) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, label } } : n))
    )
  }

  const removeNode = (id: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== id))
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id))
    if (selectedNode?.id === id) setSelectedNode(null)
  }

  const save = async () => {
    if (!appId) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(
        `${API_BASE_URL}/workshop/apps/${appId}?tenant_id=${encodeURIComponent(tenantId)}`,
        {
          method: 'PUT',
          headers: getAuthHeaders(token),
          body: JSON.stringify({
            name: appName,
            graph: { nodes, edges },
          }),
        }
      )
      if (!res.ok) throw new Error(await res.text())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  const nodeCount = useMemo(() => nodes.length, [nodes])
  const edgeCount = useMemo(() => edges.length, [edges])

  if (loading) {
    return <div className="text-center py-12 text-slate-400">加载中…</div>
  }

  return (
    <div className="h-[calc(100vh-7rem)] flex flex-col gap-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-2">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <button
            type="button"
            onClick={() => navigate('/workshop')}
            className="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
          >
            ← 返回
          </button>
          <input
            type="text"
            value={appName}
            onChange={(e) => setAppName(e.target.value)}
            className="font-semibold text-slate-900 dark:text-white bg-transparent outline-none flex-1 min-w-0"
          />
          <span className="text-xs text-slate-400">
            {nodeCount} 节点 · {edgeCount} 边
          </span>
        </div>
        <div className="flex items-center gap-2">
          {error && <span className="text-xs text-rose-500">{error}</span>}
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="px-4 py-1.5 bg-primary text-white rounded-lg text-sm font-medium disabled:opacity-50"
          >
            {saving ? '保存中…' : '保存'}
          </button>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-[200px_1fr_240px] gap-3 min-h-0">
        {/* Component Panel */}
        <aside className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-3 space-y-2 overflow-y-auto">
          <p className="text-xs uppercase tracking-wider text-slate-400 px-1 mb-2">组件</p>
          {WORKSPACE_KINDS.map((k) => (
            <button
              key={k.type}
              type="button"
              onClick={() => addNode(k.type)}
              className="w-full text-left p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
            >
              <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{k.label}</p>
              <p className="text-xs text-slate-500">{k.desc}</p>
            </button>
          ))}
          <p className="text-xs text-slate-400 px-1 pt-3 mt-3 border-t border-slate-200 dark:border-slate-700">
            提示：点击组件添加到画布；从节点右侧 handle 拖到另一节点左侧 handle 建立连接
          </p>
        </aside>

        {/* Canvas */}
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_e, node) => setSelectedNode(node)}
            onPaneClick={() => setSelectedNode(null)}
            fitView
          >
            <Background gap={16} />
            <Controls />
            <MiniMap pannable zoomable />
          </ReactFlow>
        </div>

        {/* Property Panel */}
        <aside className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-3 overflow-y-auto">
          <p className="text-xs uppercase tracking-wider text-slate-400 px-1 mb-2">属性</p>
          {selectedNode ? (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-500">标签</label>
                <input
                  type="text"
                  value={(selectedNode.data.label as string) || ''}
                  onChange={(e) => updateNodeLabel(selectedNode.id, e.target.value)}
                  className="w-full mt-1 px-2 py-1.5 text-sm border rounded dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500">类型</label>
                <p className="text-sm mt-1">{selectedNode.type}</p>
              </div>
              <div>
                <label className="text-xs text-slate-500">位置</label>
                <p className="text-xs text-slate-400 mt-1">
                  ({Math.round(selectedNode.position.x)}, {Math.round(selectedNode.position.y)})
                </p>
              </div>
              <button
                type="button"
                onClick={() => removeNode(selectedNode.id)}
                className="w-full px-3 py-1.5 text-sm text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-900/20 rounded-lg"
              >
                删除节点
              </button>
            </div>
          ) : (
            <p className="text-xs text-slate-400">点击节点查看属性</p>
          )}
        </aside>
      </div>
    </div>
  )
}

export default WorkshopEditor
