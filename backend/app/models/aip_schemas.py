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


class RAGQueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    duration_ms: int


class AgentRunRequest(BaseModel):
    input: str
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    output: str
    status: str
    trace_id: str


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
