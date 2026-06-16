import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from './useAuth'
import { API_BASE_URL, getAuthHeaders, handleResponse } from './useOntology'
import type {
  LLMBudget,
  LLMBudgetCreate,
  LLMBudgetUpdate,
  LLMCostReport,
} from '../types/aip'

interface UseLLMCostOptions {
  days?: number
  groupBy?: 'day' | 'hour'
}

export function useLLMCostReport({ days = 30, groupBy = 'day' }: UseLLMCostOptions = {}) {
  const { user, token } = useAuth()
  const tenantId = user?.tenant_id || ''
  return useQuery<LLMCostReport>({
    queryKey: ['llmCostReport', tenantId, days, groupBy],
    queryFn: async () => {
      const url = `${API_BASE_URL}/aip/llm-cost?days=${days}&group_by=${groupBy}&tenant_id=${encodeURIComponent(tenantId)}`
      const res = await fetch(url, { headers: getAuthHeaders(token) })
      return handleResponse<LLMCostReport>(res)
    },
    enabled: !!tenantId,
    refetchInterval: 60000,
  })
}

export function useLLMBudget() {
  const { user, token } = useAuth()
  const tenantId = user?.tenant_id || ''
  return useQuery<LLMBudget | null>({
    queryKey: ['llmBudget', tenantId],
    queryFn: async () => {
      const url = `${API_BASE_URL}/aip/llm-budgets?tenant_id=${encodeURIComponent(tenantId)}`
      const res = await fetch(url, { headers: getAuthHeaders(token) })
      // 404 is a normal "no budget" outcome; the backend returns null
      if (res.status === 404) return null
      return handleResponse<LLMBudget | null>(res)
    },
    enabled: !!tenantId,
  })
}

export function useUpsertBudget() {
  const { user, token } = useAuth()
  const tenantId = user?.tenant_id || ''
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: LLMBudgetCreate | LLMBudgetUpdate) => {
      // POST = upsert (idempotent), PUT = partial update of existing
      const method = 'POST'
      const res = await fetch(`${API_BASE_URL}/aip/llm-budgets?tenant_id=${encodeURIComponent(tenantId)}`, {
        method,
        headers: getAuthHeaders(token),
        body: JSON.stringify(data),
      })
      return handleResponse<LLMBudget>(res)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llmBudget', tenantId] })
      queryClient.invalidateQueries({ queryKey: ['llmCostReport', tenantId] })
    },
  })
}

export function buildCostCsvUrl(tenantId: string, days: number): string {
  return `${API_BASE_URL}/aip/llm-cost/export?days=${days}&tenant_id=${encodeURIComponent(tenantId)}`
}

export function downloadCostCsv(tenantId: string, days: number, token: string | null): void {
  const url = buildCostCsvUrl(tenantId, days)
  // Use fetch + blob so we can attach the auth header (a bare <a> click would
  // not include it and the request would 401).
  void fetch(url, { headers: getAuthHeaders(token) })
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.blob()
    })
    .then((blob) => {
      const objectUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = `llm-cost-${days}d.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(objectUrl)
    })
    .catch((err) => {
      console.error('CSV download failed', err)
      alert('CSV 下载失败，请稍后重试')
    })
}
