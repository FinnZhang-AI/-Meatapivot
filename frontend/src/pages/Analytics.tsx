import { useState } from 'react'

const Analytics = () => {
  const [timeRange, setTimeRange] = useState('7d')

  const stats = {
    totalQueries: 15634,
    avgResponseTime: '124ms',
    successRate: '99.8%',
    activeUsers: 342,
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
            数据分析
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            平台使用统计与性能监控
          </p>
        </div>
        <select
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value)}
          className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none cursor-pointer"
        >
          <option value="24h">最近 24 小时</option>
          <option value="7d">最近 7 天</option>
          <option value="30d">最近 30 天</option>
          <option value="90d">最近 90 天</option>
        </select>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700">
          <h3 className="text-sm font-medium text-slate-500 dark:text-slate-400">总查询次数</h3>
          <p className="text-3xl font-bold text-slate-900 dark:text-white mt-2">
            {stats.totalQueries.toLocaleString()}
          </p>
          <p className="text-sm text-green-500 mt-2">↑ 12.5% 较上期</p>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700">
          <h3 className="text-sm font-medium text-slate-500 dark:text-slate-400">平均响应时间</h3>
          <p className="text-3xl font-bold text-slate-900 dark:text-white mt-2">
            {stats.avgResponseTime}
          </p>
          <p className="text-sm text-green-500 mt-2">↓ 8.2% 较上期</p>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700">
          <h3 className="text-sm font-medium text-slate-500 dark:text-slate-400">成功率</h3>
          <p className="text-3xl font-bold text-slate-900 dark:text-white mt-2">
            {stats.successRate}
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">稳定运行</p>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700">
          <h3 className="text-sm font-medium text-slate-500 dark:text-slate-400">活跃用户</h3>
          <p className="text-3xl font-bold text-slate-900 dark:text-white mt-2">
            {stats.activeUsers}
          </p>
          <p className="text-sm text-green-500 mt-2">↑ 23.1% 较上期</p>
        </div>
      </div>

      {/* Placeholder Content */}
      <div className="bg-white dark:bg-slate-800 rounded-xl p-12 shadow-sm border border-slate-200 dark:border-slate-700 text-center">
        <svg className="w-16 h-16 mx-auto text-slate-300 dark:text-slate-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
          高级分析功能开发中
        </h3>
        <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto">
          包含更详细的查询趋势、用户行为分析、性能瓶颈识别等功能即将上线
        </p>
      </div>
    </div>
  )
}

export default Analytics