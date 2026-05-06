import { useState, useRef, useEffect } from 'react'
import ForceGraph2D from 'react-force-graph-2d'

const KnowledgeGraph = () => {
  const [graphData, setGraphData] = useState<{ nodes: any[]; links: any[] }>({ nodes: [], links: [] })
  const [selectedNode, setSelectedNode] = useState<any>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState('all')
  const fgRef = useRef<any>()

  // Mock graph data
  useEffect(() => {
    const mockData = {
      nodes: [
        { id: '1', name: '某科技公司', type: 'organization', val: 30, color: '#3B82F6' },
        { id: '2', name: '张三', type: 'person', val: 20, color: '#10B981' },
        { id: '3', name: '李四', type: 'person', val: 20, color: '#10B981' },
        { id: '4', name: '投资事件', type: 'event', val: 25, color: '#F59E0B' },
        { id: '5', name: '北京', type: 'location', val: 15, color: '#EF4444' },
        { id: '6', name: '上海', type: 'location', val: 15, color: '#EF4444' },
        { id: '7', name: '某投资公司', type: 'organization', val: 28, color: '#3B82F6' },
        { id: '8', name: '王五', type: 'person', val: 18, color: '#10B981' },
        { id: '9', name: '技术合作', type: 'event', val: 22, color: '#F59E0B' },
        { id: '10', name: '深圳', type: 'location', val: 15, color: '#EF4444' },
      ],
      links: [
        { source: '1', target: '2', type: 'employed', label: '任职' },
        { source: '1', target: '3', type: 'employed', label: '任职' },
        { source: '7', target: '1', type: 'invested', label: '投资' },
        { source: '4', target: '1', type: 'target', label: '标的' },
        { source: '4', target: '7', type: 'investor', label: '投资方' },
        { source: '1', target: '5', type: 'located_in', label: '位于' },
        { source: '7', target: '6', type: 'located_in', label: '位于' },
        { source: '2', target: '8', type: 'knows', label: '认识' },
        { source: '1', target: '9', type: 'participated', label: '参与' },
        { source: '9', target: '10', type: 'held_in', label: '举办地' },
      ],
    }
    setGraphData(mockData)
  }, [])

  const nodeTypes = [
    { value: 'all', label: '全部类型', color: '#6B7280' },
    { value: 'person', label: '人员', color: '#10B981' },
    { value: 'organization', label: '组织', color: '#3B82F6' },
    { value: 'event', label: '事件', color: '#F59E0B' },
    { value: 'location', label: '地点', color: '#EF4444' },
  ]

  const handleNodeClick = (node: any) => {
    setSelectedNode(node)
    if (fgRef.current) {
      fgRef.current.centerZoomGraph(node.x, node.y, 2)
    }
  }

  const filteredData = {
    nodes: filterType === 'all' 
      ? graphData.nodes 
      : graphData.nodes.filter(n => n.type === filterType),
    links: graphData.links.filter(l => 
      filterType === 'all' 
        ? true 
        : graphData.nodes.find(n => n.id === l.source)?.type === filterType ||
          graphData.nodes.find(n => n.id === l.target)?.type === filterType
    ),
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
            知识图谱
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            交互式实体关系网络分析与探索
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors cursor-pointer flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            添加实体
          </button>
        </div>
      </div>

      {/* Search and Filter Bar */}
      <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm border border-slate-200 dark:border-slate-700">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-64">
            <div className="relative">
              <input
                type="text"
                placeholder="搜索实体、关系..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
              />
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-500 dark:text-slate-400">类型筛选:</span>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none cursor-pointer"
            >
              {nodeTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <button className="px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors cursor-pointer flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
              重置视图
            </button>
            <button className="px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors cursor-pointer flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              导出
            </button>
          </div>
        </div>
      </div>

      {/* Graph Container */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Graph Area */}
        <div className="lg:col-span-3 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="h-[600px] relative">
            <ForceGraph2D
              ref={fgRef}
              graphData={filteredData}
              nodeLabel="name"
              nodeColor="color"
              nodeVal="val"
              linkLabel="label"
              linkColor={() => '#94A3B8'}
              linkWidth={2}
              linkDirectionalArrowLength={6}
              linkDirectionalArrowRelPos={1}
              onNodeClick={handleNodeClick}
              backgroundColor="transparent"
              nodeCanvasObject={(node, ctx, globalScale) => {
                const label = node.name
                const fontSize = 12 / globalScale
                const radius = node.val / globalScale
                
                // Draw node circle
                ctx.beginPath()
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false)
                ctx.fillStyle = node.color
                ctx.fill()
                
                // Draw border
                ctx.strokeStyle = '#fff'
                ctx.lineWidth = 2 / globalScale
                ctx.stroke()
                
                // Draw label
                ctx.font = `${fontSize}px Sans-Serif`
                ctx.textAlign = 'center'
                ctx.textBaseline = 'middle'
                ctx.fillStyle = node.type === 'person' ? '#fff' : '#1E293B'
                ctx.fillText(label, node.x, node.y)
              }}
            />
            
            {/* Graph Controls */}
            <div className="absolute bottom-4 right-4 flex flex-col gap-2">
              <button className="w-10 h-10 bg-white dark:bg-slate-700 rounded-lg shadow-lg flex items-center justify-center hover:bg-slate-50 dark:hover:bg-slate-600 cursor-pointer">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </button>
              <button className="w-10 h-10 bg-white dark:bg-slate-700 rounded-lg shadow-lg flex items-center justify-center hover:bg-slate-50 dark:hover:bg-slate-600 cursor-pointer">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                </svg>
              </button>
            </div>

            {/* Legend */}
            <div className="absolute top-4 left-4 bg-white/90 dark:bg-slate-800/90 backdrop-blur-sm rounded-lg p-3 shadow-lg border border-slate-200 dark:border-slate-700">
              <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2">图例</h4>
              <div className="space-y-2">
                {nodeTypes.filter(t => t.value !== 'all').map((type) => (
                  <div key={type.value} className="flex items-center gap-2">
                    <div 
                      className="w-3 h-3 rounded-full" 
                      style={{ backgroundColor: type.color }}
                    />
                    <span className="text-xs text-slate-600 dark:text-slate-300">{type.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Node Details Panel */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-4">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
            节点详情
          </h3>
          
          {selectedNode ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3 pb-3 border-b border-slate-200 dark:border-slate-700">
                <div 
                  className="w-12 h-12 rounded-full flex items-center justify-center text-white font-semibold"
                  style={{ backgroundColor: selectedNode.color }}
                >
                  {selectedNode.name.charAt(0)}
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 dark:text-white">
                    {selectedNode.name}
                  </h4>
                  <span className="text-xs px-2 py-1 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                    {nodeTypes.find(t => t.value === selectedNode.type)?.label || selectedNode.type}
                  </span>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-xs text-slate-500 dark:text-slate-400">实体 ID</label>
                  <p className="text-sm font-mono text-slate-900 dark:text-white">{selectedNode.id}</p>
                </div>
                <div>
                  <label className="text-xs text-slate-500 dark:text-slate-400">关联数量</label>
                  <p className="text-sm text-slate-900 dark:text-white">
                    {filteredData.links.filter(l => l.source === selectedNode.id || l.target === selectedNode.id).length} 个关系
                  </p>
                </div>
                <div>
                  <label className="text-xs text-slate-500 dark:text-slate-400">中心度</label>
                  <p className="text-sm text-slate-900 dark:text-white">{(selectedNode.val / 30 * 100).toFixed(1)}%</p>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-200 dark:border-slate-700">
                <h5 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">相关操作</h5>
                <div className="space-y-2">
                  <button className="w-full px-3 py-2 text-sm bg-primary/10 text-primary rounded-lg hover:bg-primary/20 transition-colors cursor-pointer">
                    查看详情
                  </button>
                  <button className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors cursor-pointer">
                    展开邻居
                  </button>
                  <button className="w-full px-3 py-2 text-sm border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer">
                    删除节点
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-12">
              <svg className="w-12 h-12 mx-auto text-slate-300 dark:text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
              </svg>
              <p className="text-slate-500 dark:text-slate-400 text-sm">
                点击节点查看详情
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Statistics Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-lg p-4 shadow-sm border border-slate-200 dark:border-slate-700">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
            {filteredData.nodes.length}
          </div>
          <div className="text-sm text-slate-500 dark:text-slate-400">当前节点数</div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-lg p-4 shadow-sm border border-slate-200 dark:border-slate-700">
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">
            {filteredData.links.length}
          </div>
          <div className="text-sm text-slate-500 dark:text-slate-400">当前关系数</div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-lg p-4 shadow-sm border border-slate-200 dark:border-slate-700">
          <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
            {new Set(filteredData.nodes.map(n => n.type)).size}
          </div>
          <div className="text-sm text-slate-500 dark:text-slate-400">实体类型</div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-lg p-4 shadow-sm border border-slate-200 dark:border-slate-700">
          <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
            {(filteredData.links.length / filteredData.nodes.length || 0).toFixed(2)}
          </div>
          <div className="text-sm text-slate-500 dark:text-slate-400">平均连接度</div>
        </div>
      </div>
    </div>
  )
}

export default KnowledgeGraph