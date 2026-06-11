export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  model?: string
}

export interface ChatRequest {
  messages: ChatMessage[]
  model?: string
  temperature?: number
  maxTokens?: number
  stream?: boolean
}

export interface ChatResponse {
  message: ChatMessage
  model: string
  usage: {
    promptTokens: number
    completionTokens: number
    totalTokens: number
  }
}

export interface SSEChunk {
  delta: string
  finishReason?: string
  done?: boolean
}

export interface RAGSource {
  objectId: string
  objectType: string
  objectKey: string
  score: number
  explanation: string
  propertiesPreview: Record<string, any>
}

export interface RAGQueryRequest {
  query: string
  objectTypes?: string[]
  topK?: number
  searchMode?: 'hybrid' | 'keyword' | 'graph'
}

export interface RAGQueryResponse {
  answer: string
  sources: RAGSource[]
  durationMs: number
  model: string
}

export interface AgentStep {
  type: string
  thought?: string
  content?: string
  toolCalls?: Array<{
    tool: string
    args: Record<string, any>
    result: string
  }>
  durationMs?: number
  error?: string
}

export interface AgentDefinition {
  id: string
  name: string
  workflowMode: string
  model: string
}

export interface AgentRunRequest {
  input: string
  context?: Record<string, any>
  sessionId?: string
}

export interface AgentRunResponse {
  output: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'interrupted' | 'not_found'
  traceId: string
  steps?: AgentStep[]
  sessionId?: string
}

export interface GuardrailsLog {
  id: string
  model: string
  inputPreview: string
  outputPreview: string
  triggered: boolean
  rulesTriggered: string[]
  createdAt: string
}

export interface LLMCallLog {
  id: string
  model: string
  promptTokens: number
  completionTokens: number
  durationMs: number
  status: 'success' | 'error' | 'timeout' | 'rate_limited'
  createdAt: string
}

export interface ModelInfo {
  id: string
  name: string
  provider: string
  maxTokens: number
  supportsStreaming: boolean
}
