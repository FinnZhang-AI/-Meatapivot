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
