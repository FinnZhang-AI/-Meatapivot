import { useQuery, useMutation } from '@tanstack/react-query'
import { useState, useCallback, useRef } from 'react'
import { useAuth } from './useAuth'
import type {
  ChatRequest,
  ChatResponse,
  SSEChunk,
  RAGQueryRequest,
  RAGQueryResponse,
  LLMCallLog,
  GuardrailsLog,
  AgentRunRequest,
  AgentRunResponse,
  AgentDefinition,
  PromptTemplate,
  PromptTemplateCreate,
  PromptTemplateUpdate,
  PromptTemplateList,
  PromptRenderRequest,
  PromptRenderResponse,
} from '../types/aip'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

function getAuthHeaders(token: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.text()
    throw new Error(error || `HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function useChat() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async (request: ChatRequest) => {
      const response = await fetch(`${API_BASE_URL}/aip/chat`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(request),
      })
      return handleResponse<ChatResponse>(response)
    },
  })
}

export function useStreamChat() {
  const { token } = useAuth()
  const [isStreaming, setIsStreaming] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const abort = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
      setIsStreaming(false)
    }
  }, [])

  const streamChat = useCallback(
    async (request: ChatRequest, onMessage: (chunk: SSEChunk) => void) => {
      abort()
      const controller = new AbortController()
      abortControllerRef.current = controller
      setIsStreaming(true)

      try {
        const response = await fetch(`${API_BASE_URL}/aip/chat/stream`, {
          method: 'POST',
          headers: {
            ...getAuthHeaders(token),
            Accept: 'text/event-stream',
          },
          body: JSON.stringify({ ...request, stream: true }),
          signal: controller.signal,
        })

        if (!response.ok) {
          const error = await response.text()
          throw new Error(error || `HTTP ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('Response body is null')
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data:')) continue

            const payload = trimmed.slice(5).trim()
            if (payload === '[DONE]') {
              setIsStreaming(false)
              return
            }
            if (!payload) continue

            try {
              const chunk: SSEChunk = JSON.parse(payload)
              onMessage(chunk)
            } catch {
              // Ignore malformed JSON lines
            }
          }
        }
      } catch (err) {
        const error = err as Error
        if (error.name !== 'AbortError') {
          throw error
        }
      } finally {
        setIsStreaming(false)
        abortControllerRef.current = null
      }
    },
    [token, abort]
  )

  return { streamChat, isStreaming, abort }
}

export function useRAGQuery() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async (request: RAGQueryRequest) => {
      const response = await fetch(`${API_BASE_URL}/aip/rag/query`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(request),
      })
      return handleResponse<RAGQueryResponse>(response)
    },
  })
}

export function useLLMCalls() {
  const { token } = useAuth()
  return useQuery<LLMCallLog[]>({
    queryKey: ['llmCalls'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/aip/llm-calls`, {
        headers: getAuthHeaders(token),
      })
      return handleResponse<LLMCallLog[]>(response)
    },
  })
}

export function useGuardrailsLogs() {
  const { token } = useAuth()
  return useQuery<GuardrailsLog[]>({
    queryKey: ['guardrailsLogs'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/aip/guardrails`, {
        headers: getAuthHeaders(token),
      })
      return handleResponse<GuardrailsLog[]>(response)
    },
  })
}

export function useAgentList() {
  const { token } = useAuth()
  return useQuery<AgentDefinition[]>({
    queryKey: ['agents'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/aip/agents`, {
        headers: getAuthHeaders(token),
      })
      const data = await handleResponse<{ agents: AgentDefinition[] }>(response)
      return data.agents
    },
    staleTime: 60000,
  })
}

export function useAgentRun() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async (request: AgentRunRequest & { agentId: string }) => {
      const { agentId, ...body } = request
      const response = await fetch(`${API_BASE_URL}/aip/agents/${agentId}/run`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(body),
      })
      return handleResponse<AgentRunResponse>(response)
    },
  })
}

export function useAgentStatus() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async ({ agentId, traceId }: { agentId: string; traceId: string }) => {
      const response = await fetch(`${API_BASE_URL}/aip/agents/${agentId}/status?trace_id=${traceId}`, {
        headers: getAuthHeaders(token),
      })
      return handleResponse<AgentRunResponse>(response)
    },
  })
}

export function useAgentInterrupt() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async ({ agentId, traceId }: { agentId: string; traceId: string }) => {
      const response = await fetch(`${API_BASE_URL}/aip/agents/${agentId}/interrupt?trace_id=${traceId}`, {
        method: 'POST',
        headers: getAuthHeaders(token),
      })
      return handleResponse<AgentRunResponse>(response)
    },
  })
}

export function useAgentResume() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async (request: AgentRunRequest & { agentId: string; traceId: string }) => {
      const { agentId, traceId, ...body } = request
      const response = await fetch(`${API_BASE_URL}/aip/agents/${agentId}/resume?trace_id=${traceId}`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(body),
      })
      return handleResponse<AgentRunResponse>(response)
    },
  })
}

export function useAgentStream() {
  const { token } = useAuth()

  const streamRun = async (
    request: AgentRunRequest & { agentId: string },
    onEvent: (event: { event: string; trace_id?: string; data?: any }) => void,
  ) => {
    const { agentId, ...body } = request
    const response = await fetch(`${API_BASE_URL}/aip/agents/${agentId}/stream`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(token),
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const error = await response.text()
      throw new Error(error || `HTTP ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('Response body is null')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue

        const payload = trimmed.slice(5).trim()
        if (payload === '[DONE]') return
        if (!payload) continue

        try {
          const parsed = JSON.parse(payload)
          onEvent(parsed)
        } catch {
          // Ignore malformed JSON lines
        }
      }
    }
  }

  return { streamRun }
}

// ---------------------------------------------------------------------------
// Prompt Template Management
// ---------------------------------------------------------------------------

export function usePromptTemplates(page: number = 1, pageSize: number = 20) {
  const { token } = useAuth()
  return useQuery<PromptTemplateList>({
    queryKey: ['promptTemplates', page, pageSize],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/aip/prompts?page=${page}&page_size=${pageSize}`, {
        headers: getAuthHeaders(token),
      })
      return handleResponse<PromptTemplateList>(response)
    },
  })
}

export function useCreatePromptTemplate() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async (request: PromptTemplateCreate) => {
      // Convert camelCase to snake_case for backend
      const body = {
        name: request.name,
        description: request.description,
        template_text: request.templateText,
        variables: request.variables,
        is_ab_test: request.isAbTest,
        ab_test_group: request.abTestGroup,
      }
      const response = await fetch(`${API_BASE_URL}/aip/prompts`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(body),
      })
      return handleResponse<PromptTemplate>(response)
    },
  })
}

export function useUpdatePromptTemplate() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async (request: PromptTemplateUpdate & { id: string }) => {
      const { id, ...rest } = request
      const body: Record<string, any> = {}
      if (rest.description !== undefined) body.description = rest.description
      if (rest.templateText !== undefined) body.template_text = rest.templateText
      if (rest.variables !== undefined) body.variables = rest.variables
      if (rest.isActive !== undefined) body.is_active = rest.isActive
      if (rest.isAbTest !== undefined) body.is_ab_test = rest.isAbTest
      if (rest.abTestGroup !== undefined) body.ab_test_group = rest.abTestGroup

      const response = await fetch(`${API_BASE_URL}/aip/prompts/${id}`, {
        method: 'PUT',
        headers: getAuthHeaders(token),
        body: JSON.stringify(body),
      })
      return handleResponse<PromptTemplate>(response)
    },
  })
}

export function useDeletePromptTemplate() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async (id: string) => {
      const response = await fetch(`${API_BASE_URL}/aip/prompts/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(token),
      })
      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || `HTTP ${response.status}`)
      }
    },
  })
}

export function useRenderPromptTemplate() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async (request: PromptRenderRequest & { id: string }) => {
      const { id, variables } = request
      const response = await fetch(`${API_BASE_URL}/aip/prompts/${id}/render`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify({ variables }),
      })
      return handleResponse<PromptRenderResponse>(response)
    },
  })
}
