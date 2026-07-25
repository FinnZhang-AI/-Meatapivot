import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from './useAuth'
import { API_BASE_URL, getAuthHeaders, handleResponse } from './useOntology'

export interface WorkshopNodeResult {
  node_id: string
  node_type: string
  status: 'pending' | 'running' | 'done' | 'error' | 'skipped'
  output: unknown
  error: string | null
  duration_ms: number | null
}

export interface WorkshopExecutionSummary {
  id: string
  app_id: string
  status: string
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
}

export interface WorkshopExecution extends WorkshopExecutionSummary {
  tenant_id: string
  results: Record<string, WorkshopNodeResult>
  error_message: string | null
}

interface WorkshopExecutionListResponse {
  items: WorkshopExecutionSummary[]
  total: number
  page: number
  page_size: number
  pages: number
}

export function useRunWorkshop(appId?: string) {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  const executionsQuery = useQuery<WorkshopExecutionListResponse>({
    queryKey: ['workshopExecutions', appId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/workshop/apps/${appId}/executions?page=1&page_size=20`,
        { headers: getAuthHeaders(token) }
      )
      return handleResponse<WorkshopExecutionListResponse>(response)
    },
    enabled: !!appId,
  })
  const latestExecutionId = executionsQuery.data?.items[0]?.id
  const currentExecutionQuery = useQuery<WorkshopExecution>({
    queryKey: ['workshopExecution', appId, latestExecutionId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/workshop/apps/${appId}/executions/${latestExecutionId}`,
        { headers: getAuthHeaders(token) }
      )
      return handleResponse<WorkshopExecution>(response)
    },
    enabled: !!appId && !!latestExecutionId,
  })
  const mutation = useMutation<WorkshopExecution>({
    mutationFn: async () => {
      const response = await fetch(`${API_BASE_URL}/workshop/apps/${appId}/run`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify({}),
      })
      return handleResponse<WorkshopExecution>(response)
    },
    onSuccess: (execution) => {
      queryClient.setQueryData(
        ['workshopExecution', appId, execution.id],
        execution
      )
      queryClient.invalidateQueries({ queryKey: ['workshopExecutions', appId] })
    },
  })

  return {
    run: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error ?? currentExecutionQuery.error ?? executionsQuery.error,
    executions: executionsQuery.data?.items ?? [],
    currentExecution: mutation.data ?? currentExecutionQuery.data,
    refetch: executionsQuery.refetch,
  }
}
