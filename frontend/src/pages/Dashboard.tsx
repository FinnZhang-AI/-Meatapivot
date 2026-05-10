import { LineChart, Line, PieChart, Pie, Cell } from 'recharts'
import { ResponsiveContainer, XAxis, YAxis, Tooltip } from 'recharts'
import { useDashboardStats } from '../hooks/useOntology'
import { useAuth } from '../hooks/useAuth'

const Dashboard = () => {
  const { user } = useAuth()
  const tenantId = user?.tenant_id || ''
  const { data: stats, isLoading: statsLoading } = useDashboardStats(tenantId)

  // Mock data for charts (backend does not have historical trend data yet)
  const queryTrendData = [
    { name: '00:00', queries: 45 },
    { name: '04:00', queries: 32 },
    { name: '08:00', queries: 128 },
    { name: '12:00', queries: 256 },
    { name: '16:00', queries: 198 },
    { name: '20:00', queries: 145 },
    { name: '23:59', queries: 87 },
  ]

  const entityTypeData = [
    { name: '人员', value: 4500 },
    { name: '组织', value: 3200 },
    { name: '事件', value: 2800 },
    { name: '地点', value: 1500 },
    { name: '其他', value: 847 },
  ]

  const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
            仪表盘
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            欢迎回来，这是您的知识决策平台概览
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500 dark:text-slate-400">
            最后更新：{new Date().toLocaleString('zh-CN')}
          </span>
          <button className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors cursor-pointer flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            刷新
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700 interactive-card">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
              <svg className="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
          </div>
          <h3 className="text-slate-500 dark:text-slate-400 text-sm font-medium">对象类型</h3>
          <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">
            {statsLoading ? '...' : (stats?.objectTypeCount || 0).toLocaleString()}
          </p>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700 interactive-card">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
              <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
              </svg>
            </div>
          </div>
          <h3 className="text-slate-500 dark:text-slate-400 text-sm font-medium">对象实例</h3>
          <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">
            {statsLoading ? '...' : (stats?.objectInstanceCount || 0).toLocaleString()}
          </p>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700 interactive-card">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-lg bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center">
              <svg className="w-6 h-6 text-orange-600 dark:text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
          </div>
          <h3 className="text-slate-500 dark:text-slate-400 text-sm font-medium">动作执行</h3>
          <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">
            {statsLoading ? '...' : (stats?.actionExecutionCount || 0).toLocaleString()}
          </p>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700 interactive-card">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
              <svg className="w-6 h-6 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
          </div>
          <h3 className="text-slate-500 dark:text-slate-400 text-sm font-medium">关系类型</h3>
          <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">
            {statsLoading ? '...' : (stats?.linkTypeCount || 0).toLocaleString()}
          </p>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Query Trend Chart */}
        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
            24 小时查询趋势
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={queryTrendData}>
                <XAxis dataKey="name" stroke="#94A3B8" fontSize={12} />
                <YAxis stroke="#94A3B8" fontSize={12} />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1E293B', 
                    border: 'none', 
                    borderRadius: '8px',
                    color: '#F1F5F9'
                  }} 
                />
                <Line 
                  type="monotone" 
                  dataKey="queries" 
                  stroke="#3B82F6" 
                  strokeWidth={2}
                  dot={{ fill: '#3B82F6', strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Entity Type Distribution */}
        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
            实体类型分布
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={entityTypeData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {entityTypeData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1E293B', 
                    border: 'none', 
                    borderRadius: '8px',
                    color: '#F1F5F9'
                  }} 
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Recent Activities */}
      <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
            最近活动
          </h3>
          <button className="text-sm text-primary hover:text-blue-600 cursor-pointer font-medium">
            查看全部 →
          </button>
        </div>
        <div className="space-y-4">
          {statsLoading ? (
            <div className="text-center py-8 text-slate-400">加载中...</div>
          ) : stats?.recentActions && stats.recentActions.length > 0 ? (
            stats.recentActions.map((activity) => (
              <div
                key={activity.id}
                className="flex items-center justify-between p-4 rounded-lg bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    activity.status === 'success' ? 'bg-green-100 dark:bg-green-900/30' :
                    activity.status === 'failed' ? 'bg-red-100 dark:bg-red-900/30' :
                    'bg-blue-100 dark:bg-blue-900/30'
                  }`}>
                    <svg className="w-5 h-5 text-slate-600 dark:text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-900 dark:text-white">
                      {activity.actionName} · {activity.targetObjectKey}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {activity.status} · {activity.durationMs ? `${activity.durationMs}ms` : 'N/A'}
                    </p>
                  </div>
                </div>
                <span className="text-xs text-slate-400 dark:text-slate-500">
                  {activity.executedAt ? new Date(activity.executedAt).toLocaleString('zh-CN') : ''}
                </span>
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-slate-400">暂无最近活动</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Dashboard