from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = False
    prompt_template_id: Optional[UUID] = None
    prompt_variables: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    message: ChatMessage
    model: str
    usage: Dict[str, Any]


class SSEChunk(BaseModel):
    delta: str
    finish_reason: Optional[str] = None


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    object_types: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=50)
    search_mode: Optional[str] = "hybrid"
    prompt_template_id: Optional[UUID] = None
    prompt_variables: Optional[Dict[str, Any]] = Field(default_factory=dict)
    use_llama_index: bool = False


class RAGSource(BaseModel):
    object_id: str
    object_type: str
    object_key: str
    score: float
    explanation: str
    properties_preview: Dict[str, Any]


class RAGQueryResponse(BaseModel):
    answer: str
    sources: List[RAGSource]
    duration_ms: int
    model: str


class AgentStep(BaseModel):
    type: str
    thought: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None


class WorkflowNodeConfig(BaseModel):
    """Configuration for a workflow node."""
    system_prompt: Optional[str] = None
    action_type_id: Optional[str] = None
    target_object_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    query_template: Optional[str] = None
    object_types: Optional[List[str]] = None
    condition_expression: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)
    pass_target: Optional[str] = None
    fail_target: Optional[str] = None
    prompt: Optional[str] = None


class WorkflowNode(BaseModel):
    id: str
    type: str = Field(..., pattern="^(llm|action|search|human|condition|end)$")
    config: WorkflowNodeConfig = Field(default_factory=WorkflowNodeConfig)


class WorkflowEdge(BaseModel):
    source: str
    target: str
    condition: Optional[str] = None


class AgentToolSchema(BaseModel):
    name: str
    description: str


class AgentDefinitionSchema(BaseModel):
    id: UUID
    name: str
    workflow_mode: str
    model: str
    description: Optional[str] = None
    tools: List[AgentToolSchema] = Field(default_factory=list)
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)
    human_in_the_loop: bool = False


class AgentListResponse(BaseModel):
    agents: List[AgentDefinitionSchema]


class AgentRunRequest(BaseModel):
    input: str = Field(..., min_length=1)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    session_id: Optional[UUID] = None


class AgentRunResponse(BaseModel):
    output: str
    status: str
    trace_id: str
    steps: List[AgentStep] = Field(default_factory=list)
    session_id: Optional[str] = None
    requires_input: bool = False
    prompt: Optional[str] = None


class AgentSSEEvent(BaseModel):
    event: str
    data: Dict[str, Any]


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    template_text: str = Field(..., min_length=1)
    variables: Optional[List[str]] = Field(default_factory=list)
    is_ab_test: bool = False
    ab_test_group: Optional[str] = None


class PromptTemplateUpdate(BaseModel):
    description: Optional[str] = None
    template_text: Optional[str] = None
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_ab_test: Optional[bool] = None
    ab_test_group: Optional[str] = None


class PromptTemplateResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str]
    template_text: str
    variables: List[str]
    version: int
    is_active: bool
    is_ab_test: bool
    ab_test_group: Optional[str]
    usage_count: int
    avg_prompt_tokens: int
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class PromptTemplateListResponse(BaseModel):
    items: List[PromptTemplateResponse]
    total: int
    page: int
    page_size: int
    pages: int


class PromptRenderRequest(BaseModel):
    variables: Dict[str, Any] = Field(default_factory=dict)


class PromptRenderResponse(BaseModel):
    rendered_text: str


class GuardrailsLogResponse(BaseModel):
    id: UUID
    model: str
    input_preview: str
    output_preview: str
    triggered: bool
    rules_triggered: List[str]


class LLMCallLogResponse(BaseModel):
    id: UUID
    model: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int
    status: str


class LLMUsageBucket(BaseModel):
    """One time-window bucket for LLM usage trend."""

    bucket: str  # ISO timestamp string, e.g. "2026-06-15T22:00:00"
    call_count: int
    total_tokens: int
    estimated_cost_cents: int


class LLMUsageTrendResponse(BaseModel):
    group_by: str
    hours: int
    buckets: List[LLMUsageBucket]


# ---------------------------------------------------------------------------
# S4-1: LLM cost dashboard
# ---------------------------------------------------------------------------


class LLMCostByModel(BaseModel):
    model: str
    call_count: int
    total_tokens: int
    estimated_cost_cents: int


class LLMCostTrendPoint(BaseModel):
    bucket: str  # ISO date or datetime
    call_count: int
    total_tokens: int
    estimated_cost_cents: int


class LLMCostReport(BaseModel):
    """Aggregated cost snapshot for the dashboard."""

    tenant_id: str
    days: int
    group_by: str  # "day" or "hour"
    total_calls: int
    total_tokens: int
    total_cost_cents: int
    by_model: List[LLMCostByModel]
    trend: List[LLMCostTrendPoint]
    budget: Optional["LLMBudgetResponse"] = None
    budget_state: str = "unknown"  # "ok" | "warning" | "exceeded" | "no_budget"


class LLMBudgetCreate(BaseModel):
    monthly_budget_cents: int = Field(..., ge=0)
    alert_threshold_percent: int = Field(80, ge=0, le=100)
    model_overrides: Optional[Dict[str, int]] = None
    notes: Optional[str] = None


class LLMBudgetUpdate(BaseModel):
    monthly_budget_cents: Optional[int] = Field(None, ge=0)
    alert_threshold_percent: Optional[int] = Field(None, ge=0, le=100)
    model_overrides: Optional[Dict[str, int]] = None
    notes: Optional[str] = None


class LLMBudgetResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    monthly_budget_cents: int
    alert_threshold_percent: int
    model_overrides: Optional[Dict[str, int]] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AvailableModelsResponse(BaseModel):
    models: List["ModelInfo"]


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    max_tokens: int
    supports_streaming: bool = True


# Rebuild to resolve forward refs after both classes are defined
AvailableModelsResponse.model_rebuild()
LLMCostReport.model_rebuild()
