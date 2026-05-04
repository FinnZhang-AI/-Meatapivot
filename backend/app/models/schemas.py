from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class EntityType(str, Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    DOCUMENT = "document"
    EVENT = "event"
    LOCATION = "location"
    CONCEPT = "concept"


class RelationType(str, Enum):
    OWNS = "owns"
    WORKS_FOR = "works_for"
    LOCATED_AT = "located_at"
    RELATED_TO = "related_to"
    DERIVED_FROM = "derived_from"
    REFERENCES = "references"


class DataSourceType(str, Enum):
    DATABASE = "database"
    API = "api"
    FILE = "file"
    STREAM = "stream"


# Authentication Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None
    tenant_id: Optional[str] = None
    roles: List[str] = []


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    tenant_id: str
    roles: List[str] = ["user"]


class UserResponse(BaseModel):
    id: str = "user-default"
    username: str = "default"
    email: str = "user@example.com"
    tenant_id: str = "tenant-default"
    roles: List[str] = ["user"]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True


# Tenant Schemas
class TenantCreate(BaseModel):
    name: str
    description: Optional[str] = None
    config: Dict[str, Any] = {}


class TenantResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    config: Dict[str, Any]
    created_at: datetime
    is_active: bool


# Data Source Schemas
class DataSourceCreate(BaseModel):
    name: str
    type: DataSourceType
    config: Dict[str, Any]
    description: Optional[str] = None


class DataSourceResponse(BaseModel):
    id: str
    name: str
    type: DataSourceType
    config: Dict[str, Any]
    status: str
    last_sync: Optional[datetime]
    created_at: datetime


# Knowledge Graph Schemas
class EntityCreate(BaseModel):
    name: str
    type: EntityType
    properties: Dict[str, Any] = {}
    source_id: Optional[str] = None


class EntityResponse(BaseModel):
    id: str
    name: str
    type: EntityType
    properties: Dict[str, Any]
    relationships: List["RelationshipResponse"]
    created_at: datetime
    updated_at: datetime


class RelationshipCreate(BaseModel):
    source_entity_id: str
    target_entity_id: str
    type: RelationType
    properties: Dict[str, Any] = {}


class RelationshipResponse(BaseModel):
    id: str
    source_entity_id: str
    target_entity_id: str
    type: RelationType
    properties: Dict[str, Any]
    created_at: datetime


# Visualization Schemas
class GraphQuery(BaseModel):
    query: str
    params: Dict[str, Any] = {}
    limit: int = 100


class GraphData(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class ChartConfig(BaseModel):
    type: str
    data: Dict[str, Any]
    options: Dict[str, Any] = {}


# Workflow Schemas
class WorkflowStep(BaseModel):
    name: str
    type: str
    config: Dict[str, Any]
    next_step: Optional[str] = None


class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    steps: List[WorkflowStep]
    trigger: Dict[str, Any] = {}


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    steps: List[WorkflowStep]
    status: str
    created_at: datetime
    updated_at: datetime


class WorkflowExecution(BaseModel):
    workflow_id: str
    input_data: Dict[str, Any]
    context: Dict[str, Any] = {}


# Search Schemas
class SearchQuery(BaseModel):
    query: str
    filters: Dict[str, Any] = {}
    limit: int = 20
    offset: int = 0


class SearchResult(BaseModel):
    entities: List[EntityResponse]
    documents: List[Dict[str, Any]]
    total: int


# Document Schemas
class DocumentMetadata(BaseModel):
    title: str
    description: Optional[str] = None
    document_type: str = "general"
    tags: List[str] = []


class DocumentResponse(BaseModel):
    id: str
    title: str
    filename: str
    object_name: str
    document_type: str
    description: Optional[str]
    file_size: int
    mime_type: str
    tags: List[str]
    uploaded_by: str
    tenant_id: str
    uploaded_at: str
    url: str


# Decision Flow Schemas
class DecisionFlowStep(BaseModel):
    id: str = Field(default_factory=lambda: f"step-{datetime.utcnow().timestamp()}")
    name: str
    step_type: str  # query, transform, condition, notification, api_call
    config: Dict[str, Any] = {}
    input_variable: Optional[str] = None
    output_variable: Optional[str] = None
    continue_on_error: bool = False
    on_false_goto: Optional[str] = None


class DecisionFlowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    version: Optional[str] = "1.0.0"
    steps: List[DecisionFlowStep]


class DecisionFlowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    version: str
    steps: List[DecisionFlowStep]
    created_at: str
    created_by: str
    is_active: bool = True


class FlowExecutionRequest(BaseModel):
    initial_context: Optional[Dict[str, Any]] = {}


class FlowExecutionResponse(BaseModel):
    execution_id: str
    flow_id: str
    status: str  # queued, running, completed, failed
    started_at: str


# Graph Query Schemas
class GraphQueryRequest(BaseModel):
    cypher_query: str
    parameters: Dict[str, Any] = {}


class GraphQueryResponse(BaseModel):
    data: List[Dict[str, Any]]
    total: int


# Entity Update Schema
class EntityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


# Search Request Schema
class SearchRequest(BaseModel):
    query: str
    limit: int = 20
    offset: int = 0