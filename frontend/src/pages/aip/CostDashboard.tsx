import { useMemo, useState } from 'react'
import {
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAuth } from '../../hooks/useAuth'
import {
  downloadCostCsv,
  useLLMBudget,
  useLLMCostReport,
  useUpsertBudget,
} from '../../hooks/useLLMCost'

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#84CC16', '#F97316']
const DAYS_OPTIONS = [7, 30, 90]
const GROUP_OPTIONS = [
  { value: 'day' as const, label: '按天' },
  { value: 'hour' as const, label: '按小时' },
]

const formatBucketLabel = (iso: string): string => {
  // "2026-06-15T22:00" or "2026-06-15T00:00" — strip the time part for day view
  const m = iso.match(/T(\d{2}:\d{2})/)
  if (m) return m[1] // hour view
  return iso.slice(5) // "06-15"
}

const formatUsd = (cents: number): string => {
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(cents) / 100
  if (abs < 0.01) return `${sign}$${abs.toFixed(4)}`
  return `${sign}$${abs.toFixed(2)}`
}

const BUDGET_TONE: Record<string, { label: string; bg: string; text: string; ring: string }> = {
  ok: { label: '预算正常', bg: 'bg-emerald-50', text: 'text-emerald-700', ring: 'border-emerald-300' },
  warning: { label: '预算告警', bg: 'bg-amber-50', text: 'text-amber-700', ring: 'border-amber-300' },
  exceeded: { label: '预算超支', bg: 'bg-rose-50', text: 'text-rose-700', ring: 'border-rose-300' },
  no_budget: { label: '未设置预算', bg: 'bg-slate-50', text: 'text-slate-500', ring: 'border-slate-300' },
  unknown: { label: '未知', bg: 'bg-slate-50', text: 'text-slate-500', ring: 'border-slate-300' },
}

const CostDashboard = () => {
  const { user, token } = useAuth()
  const tenantId = user?.tenant_id || ''

  const [days, setDays] = useState<number>(30)
  const [groupBy, setGroupBy] = useState<'day' | 'hour'>('day')
  const [editingBudget, setEditingBudget] = useState(false)
  const [budgetDraft, setBudgetDraft] = useState({ monthlyBudgetCents: 10000, alertThresholdPercent: 80 })

  const { data: report, isLoading, error, refetch } = useLLMCostReport({ days, groupBy })
  const { data: budget } = useLLMBudget()
  const upsertBudget = useUpsertBudget()

  const byModelData = useMemo(
    () =>
      (report?.byModel || []).map((m) => ({
        name: m.model,
        value: m.estimatedCostCents,
        tokens: m.totalTokens,
        calls: m.callCount,
      })),
    [report]
  )
  const trendData = useMemo(
    () =>
      (report?.trend || []).map((t) => ({
        name: formatBucketLabel(t.bucket),
        cost: t.estimatedCostCents / 100,
        tokens: t.totalTokens,
        calls: t.callCount,
      })),
    [report]
  )

  const state = report?.budgetState || 'unknown'
  const tone = BUDGET_TONE[state] || BUDGET_TONE.unknown

  const openBudgetEditor = () => {
    setBudgetDraft({
      monthlyBudgetCents: budget?.monthlyBudgetCents ?? 10000,
      alertThresholdPercent: budget?.alertThresholdPercent ?? 80,
    })
    setEditingBudget(true)
  }

  const saveBudget = async () => {
    await upsertBudget.mutateAsync({
      monthlyBudgetCents: budgetDraft.monthlyBudgetCents,
      alertThresholdPercent: budgetDraft.alertThresholdPercent,
    })
    setEditingBudget(false)
    void refetch()
  }

  if (isLoading && !report) {
    return <div className="text-center py-12 text-slate-400">加载中…</div>
  }
  if (error) {
    return (
      <div className="text-sm text-rose-500 bg-rose-50 dark:bg-rose-900/20 rounded-lg p-3">
        加载失败：{String(error)}
      </div>
    )
  }
  if (!report) {
    return <div className="text-center py-12 text-slate-400">暂无数据</div>
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">LLM 成本仪表盘</h1>
          <p className="text-slate-500 text-sm mt-1">按模型 / 租户 / 时间段聚合的 Token 消耗与费用</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value, 10))}
            className="text-sm border rounded-lg px-2 py-1.5 bg-white dark:bg-slate-700 border-slate-200 dark:border-slate-600"
          >
            {DAYS_OPTIONS.map((d) => (
              <option key={d} value={d}>
                最近 {d} 天
              </option>
            ))}
          </select>
          <select
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value as 'day' | 'hour')}
            className="text-sm border rounded-lg px-2 py-1.5 bg-white dark:bg-slate-700 border-slate-200 dark:border-slate-600"
          >
            {GROUP_OPTIONS.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => downloadCostCsv(tenantId, days, token)}
            disabled={!report.totalCalls}
            className="px-3 py-1.5 text-sm border rounded-lg bg-white dark:bg-slate-700 border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-600 disabled:opacity-50"
          >
            导出 CSV
          </button>
        </div>
      </div>

      {/* Budget banner */}
      <div className={`rounded-xl border p-4 flex items-center justify-between gap-3 ${tone.bg} ${tone.ring}`}>
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-semibold ${tone.text}`}>{tone.label}</p>
          <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5">
            {budget?.monthlyBudgetCents
              ? `本月预估 ${formatUsd(report.totalCostCents)} / ${formatUsd(budget.monthlyBudgetCents)}（告警阈值 ${budget.alertThresholdPercent}%）`
              : '点击右侧设置月度预算与告警阈值'}
          </p>
        </div>
        {editingBudget ? (
          <div className="flex items-end gap-2 flex-wrap">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-slate-500">月度预算（USD cents）</label>
              <input
                type="number"
                min={0}
                value={budgetDraft.monthlyBudgetCents}
                onChange={(e) => setBudgetDraft({ ...budgetDraft, monthlyBudgetCents: parseInt(e.target.value || '0', 10) })}
                className="block w-40 mt-0.5 px-2 py-1 text-sm border rounded dark:bg-slate-800 dark:border-slate-600"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-slate-500">告警阈值（%）</label>
              <input
                type="number"
                min={0}
                max={100}
                value={budgetDraft.alertThresholdPercent}
                onChange={(e) => setBudgetDraft({ ...budgetDraft, alertThresholdPercent: parseInt(e.target.value || '0', 10) })}
                className="block w-24 mt-0.5 px-2 py-1 text-sm border rounded dark:bg-slate-800 dark:border-slate-600"
              />
            </div>
            <button
              type="button"
              onClick={saveBudget}
              disabled={upsertBudget.isPending}
              className="px-3 py-1.5 text-sm bg-primary text-white rounded disabled:opacity-50"
            >
              {upsertBudget.isPending ? '保存中…' : '保存'}
            </button>
            <button
              type="button"
              onClick={() => setEditingBudget(false)}
              className="px-3 py-1.5 text-sm text-slate-500"
            >
              取消
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={openBudgetEditor}
            className="px-3 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800"
          >
            {budget ? '编辑预算' : '设置预算'}
          </button>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500 uppercase tracking-wider">总费用（{days} 天）</p>
          <p className="text-3xl font-bold mt-1 text-slate-900 dark:text-white">
            {formatUsd(report.totalCostCents)}
          </p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500 uppercase tracking-wider">总调用次数</p>
          <p className="text-3xl font-bold mt-1 text-slate-900 dark:text-white">
            {report.totalCalls.toLocaleString()}
          </p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500 uppercase tracking-wider">总 Token 数</p>
          <p className="text-3xl font-bold mt-1 text-slate-900 dark:text-white">
            {report.totalTokens.toLocaleString()}
          </p>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">
            成本趋势（USD）
          </h3>
          <div className="h-64">
            {trendData.length === 0 || trendData.every((p) => p.cost === 0) ? (
              <div className="h-full flex items-center justify-center text-slate-400 text-sm">
                暂无调用记录
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
                  <XAxis dataKey="name" stroke="#94A3B8" fontSize={11} />
                  <YAxis stroke="#94A3B8" fontSize={11} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1E293B', border: 'none', borderRadius: '8px', color: '#F1F5F9' }}
                    formatter={(value: number) => [`$${value.toFixed(4)}`, '成本']}
                  />
                  <Line type="monotone" dataKey="cost" stroke="#3B82F6" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">
            按模型成本分布
          </h3>
          <div className="h-64">
            {byModelData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-400 text-sm">
                暂无模型使用记录
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={byModelData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {byModelData.map((_, i) => (
                      <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1E293B', border: 'none', borderRadius: '8px', color: '#F1F5F9' }}
                    formatter={(value: number) => [`$${(value / 100).toFixed(4)}`, '成本']}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Per-model table */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 px-5 py-3 border-b border-slate-200 dark:border-slate-700">
          按模型明细
        </h3>
        {byModelData.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-sm">暂无数据</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-700/40 text-xs text-slate-500 uppercase">
              <tr>
                <th className="text-left px-5 py-2">模型</th>
                <th className="text-right px-5 py-2">调用次数</th>
                <th className="text-right px-5 py-2">Token 数</th>
                <th className="text-right px-5 py-2">成本</th>
              </tr>
            </thead>
            <tbody>
              {byModelData.map((m) => (
                <tr key={m.name} className="border-t border-slate-200 dark:border-slate-700">
                  <td className="px-5 py-2 font-medium text-slate-800 dark:text-slate-100">{m.name}</td>
                  <td className="px-5 py-2 text-right text-slate-600 dark:text-slate-300">
                    {m.calls.toLocaleString()}
                  </td>
                  <td className="px-5 py-2 text-right text-slate-600 dark:text-slate-300">
                    {m.tokens.toLocaleString()}
                  </td>
                  <td className="px-5 py-2 text-right font-mono text-slate-800 dark:text-slate-100">
                    {formatUsd(m.value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default CostDashboard
