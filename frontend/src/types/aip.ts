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
  promptTemplateId?: string
  promptVariables?: Record<string, any>
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
  promptTemplateId?: string
  promptVariables?: Record<string, any>
  useLlamaIndex?: boolean
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

export interface WorkflowNodeConfig {
  system_prompt?: string
  action_type_id?: string
  target_object_id?: string
  parameters?: Record<string, any>
  query_template?: string
  object_types?: string[]
  condition_expression?: string
  top_k?: number
  pass_target?: string
  fail_target?: string
  prompt?: string
}

export interface WorkflowNode {
  id: string
  type: 'llm' | 'action' | 'search' | 'human' | 'condition' | 'end'
  config?: WorkflowNodeConfig
}

export interface WorkflowEdge {
  source: string
  target: string
  condition?: string
}

export interface AgentTool {
  name: string
  description: string
}

export interface AgentDefinition {
  id: string
  name: string
  workflow_mode: string
  model: string
  description?: string
  tools?: AgentTool[]
  nodes?: WorkflowNode[]
  edges?: WorkflowEdge[]
  human_in_the_loop?: boolean
}

export interface AgentRunRequest {
  input: string
  context?: Record<string, any>
  sessionId?: string
}

export interface AgentRunResponse {
  output: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'interrupted' | 'not_found' | 'awaiting_input'
  traceId: string
  steps?: AgentStep[]
  sessionId?: string
  requiresInput?: boolean
  prompt?: string
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

export interface PromptTemplate {
  id: string
  tenantId: string
  name: string
  description?: string
  templateText: string
  variables: string[]
  version: number
  isActive: boolean
  isAbTest: boolean
  abTestGroup?: string
  usageCount: number
  avgPromptTokens: number
  createdBy?: string
  createdAt: string
  updatedAt: string
}

export interface PromptTemplateCreate {
  name: string
  description?: string
  templateText: string
  variables?: string[]
  isAbTest?: boolean
  abTestGroup?: string
}

export interface PromptTemplateUpdate {
  description?: string
  templateText?: string
  variables?: string[]
  isActive?: boolean
  isAbTest?: boolean
  abTestGroup?: string
}

export interface PromptTemplateList {
  items: PromptTemplate[]
  total: number
  page: number
  pageSize: number
  pages: number
}

export interface PromptRenderRequest {
  variables: Record<string, any>
}

export interface PromptRenderResponse {
  renderedText: string
}

export interface ModelInfo {
  id: string
  name: string
  provider: string
  maxTokens: number
  supportsStreaming: boolean
}
