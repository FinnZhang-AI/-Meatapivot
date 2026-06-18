"""Workshop Pydantic schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorkshopAppCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    graph: Dict[str, Any] = Field(default_factory=dict)


class WorkshopAppUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    graph: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class WorkshopAppResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str] = None
    graph: Dict[str, Any]
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WorkshopAppListResponse(BaseModel):
    items: List[WorkshopAppResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# V4-1: Workshop runtime execution
# ---------------------------------------------------------------------------


class WorkshopNodeResult(BaseModel):
    """One node's outcome within a run."""

    node_id: str
    node_type: str
    status: str  # "pending" | "running" | "done" | "error" | "skipped"
    output: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class WorkshopExecutionRequest(BaseModel):
    """Body for POST /workshop/apps/{id}/run.

    Optional ``node_overrides`` lets a runner force a few input values
    (e.g. an Action's parameters) without editing the saved graph.
    """

    node_overrides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class WorkshopExecutionResponse(BaseModel):
    id: UUID
    app_id: UUID
    tenant_id: UUID
    status: str
    results: Dict[str, WorkshopNodeResult]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class WorkshopExecutionListItem(BaseModel):
    id: UUID
    app_id: UUID
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class WorkshopExecutionListResponse(BaseModel):
    items: List[WorkshopExecutionListItem]
    total: int
    page: int
    page_size: int
    pages: int
