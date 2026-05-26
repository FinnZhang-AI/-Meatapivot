from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID


class PropertyDef(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = None
    type: str = Field(..., pattern=r'^(string|int|float|date|boolean|json)$')
    required: bool = False
    default_value: Optional[Any] = None
    validation: Optional["PropertyValidation"] = None
    link_to: Optional[str] = None


class PropertyValidation(BaseModel):
    regex: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    enum: Optional[List[str]] = None


class InterfaceLinkRequirement(BaseModel):
    name: str
    target_type: str
    cardinality: str = "MANY_TO_ONE"


class ActionParameter(BaseModel):
    name: str
    display_name: Optional[str] = None
    type: str
    object_type_ref: Optional[str] = None
    required: bool = False
    default_value: Optional[Any] = None
    description: Optional[str] = None


class ActionRule(BaseModel):
    name: str
    rule_type: str = Field(..., pattern=r'^(opa|expression)$')
    policy: str
    description: Optional[str] = None


class CompileError(BaseModel):
    code: str
    message: str
    field: Optional[str] = None


class ObjectTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, pattern=r'^[A-Z][a-zA-Z0-9_]*$')
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    icon: Optional[str] = Field(default="box", max_length=50)
    properties: List[PropertyDef] = Field(default_factory=list)
    implemented_interfaces: List[UUID] = Field(default_factory=list)
    neo4j_label: Optional[str] = None


class ObjectTypeUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=50)
    properties: Optional[List[PropertyDef]] = None
    implemented_interfaces: Optional[List[UUID]] = None
    status: Optional[str] = Field(None, pattern=r'^(draft|active|archived)$')


class ObjectTypeResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    icon: str
    properties: List[PropertyDef]
    implemented_interfaces: List[UUID]
    neo4j_label: str
    status: str
    version: int
    compile_status: str
    compile_errors: List[CompileError]
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ObjectTypeListResponse(BaseModel):
    items: List[ObjectTypeResponse]
    total: int
    page: int
    page_size: int
    pages: int


class CompileResult(BaseModel):
    status: str
    errors: List[CompileError]
    warnings: List[str]
    neo4j_constraints_created: int
    duration_ms: int


class OntologyObjectCreate(BaseModel):
    object_key: str = Field(..., min_length=1, max_length=255)
    properties: Dict[str, Any] = Field(default_factory=dict)


class OntologyObjectUpdate(BaseModel):
    object_key: Optional[str] = Field(None, min_length=1, max_length=255)
    properties: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, pattern=r'^(active|archived|draft)$')


class OntologyObjectResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    object_type_id: UUID
    object_type_name: str
    object_key: str
    properties: Dict[str, Any]
    neo4j_node_id: Optional[str] = None
    status: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LinkTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    source_object_type_id: UUID
    target_object_type_id: UUID
    cardinality: str = Field(default="MANY_TO_ONE", pattern=r'^(ONE_TO_ONE|ONE_TO_MANY|MANY_TO_ONE|MANY_TO_MANY)$')
    neo4j_edge_type: Optional[str] = None
    properties: List[PropertyDef] = Field(default_factory=list)


class LinkTypeUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    cardinality: Optional[str] = Field(None, pattern=r'^(ONE_TO_ONE|ONE_TO_MANY|MANY_TO_ONE|MANY_TO_MANY)$')
    properties: Optional[List[PropertyDef]] = None
    status: Optional[str] = Field(None, pattern=r'^(draft|active|archived)$')


class LinkTypeResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    source_object_type_id: UUID
    source_object_type_name: str
    target_object_type_id: UUID
    target_object_type_name: str
    cardinality: str
    neo4j_edge_type: str
    neo4j_properties: List[PropertyDef]
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LinkTypeListResponse(BaseModel):
    items: List[LinkTypeResponse]
    total: int
    page: int
    page_size: int
    pages: int


class OntologyLinkCreate(BaseModel):
    source_object_id: UUID
    target_object_id: UUID
    properties: Dict[str, Any] = Field(default_factory=dict)


class OntologyLinkResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    link_type_id: UUID
    link_type_name: str
    source_object_id: UUID
    target_object_id: UUID
    properties: Dict[str, Any]
    neo4j_rel_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GraphNode(BaseModel):
    id: str
    object_id: UUID
    object_type: str
    label: str
    properties: Dict[str, Any]


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: Dict[str, Any]


class GraphMetadata(BaseModel):
    center_object_id: UUID
    depth: int
    total_nodes: int
    total_edges: int
    query_time_ms: int


class SubgraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: GraphMetadata


class InterfaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    required_properties: List[PropertyDef] = Field(default_factory=list)
    required_links: List[InterfaceLinkRequirement] = Field(default_factory=list)


class InterfaceUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    required_properties: Optional[List[PropertyDef]] = None
    required_links: Optional[List[InterfaceLinkRequirement]] = None
    status: Optional[str] = Field(None, pattern=r'^(draft|active|archived)$')


class InterfaceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    required_properties: List[PropertyDef]
    required_links: List[InterfaceLinkRequirement]
    status: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InterfaceListResponse(BaseModel):
    items: List[InterfaceResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ImplementationValidation(BaseModel):
    object_type_id: UUID
    object_type_name: str
    passed: bool
    missing_properties: List[str]
    missing_links: List[str]


class InterfaceValidationResult(BaseModel):
    interface_id: UUID
    total_implementations: int
    passed: int
    failed: int
    details: List[ImplementationValidation]


class ActionTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    target_object_type_id: UUID
    parameters: List[ActionParameter] = Field(default_factory=list)
    modifies_properties: List[str] = Field(default_factory=list)
    modifies_links: List[str] = Field(default_factory=list)
    rules: List[ActionRule] = Field(default_factory=list)
    execution_type: str = Field(default="direct", pattern=r'^(direct|function_backed|workflow)$')
    function_id: Optional[UUID] = None
    workflow_id: Optional[UUID] = None


class ActionTypeUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    parameters: Optional[List[ActionParameter]] = None
    modifies_properties: Optional[List[str]] = None
    modifies_links: Optional[List[str]] = None
    rules: Optional[List[ActionRule]] = None
    execution_type: Optional[str] = Field(None, pattern=r'^(direct|function_backed|workflow)$')
    function_id: Optional[UUID] = None
    workflow_id: Optional[UUID] = None
    status: Optional[str] = Field(None, pattern=r'^(draft|active|archived)$')


class ActionTypeResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    target_object_type_id: UUID
    target_object_type_name: str
    parameters: List[ActionParameter]
    modifies_properties: List[str]
    modifies_links: List[str]
    rules: List[ActionRule]
    execution_type: str
    function_id: Optional[UUID] = None
    workflow_id: Optional[UUID] = None
    status: str
    created_by: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ActionTypeListResponse(BaseModel):
    items: List[ActionTypeResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ActionExecuteRequest(BaseModel):
    target_object_id: Optional[UUID] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    async_execution: bool = False


class RuleEvaluation(BaseModel):
    rule_name: str
    passed: bool
    reason: Optional[str] = None


class ActionExecuteResponse(BaseModel):
    execution_id: UUID
    status: str
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    rules_evaluation: List[RuleEvaluation]
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class FunctionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    language: str = Field(default="python", pattern=r'^(python|typescript)$')
    code: str = Field(..., max_length=10000)
    read_only: bool = False
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    memory_mb: int = Field(default=256, ge=64, le=1024)


class FunctionUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    code: Optional[str] = Field(None, max_length=10000)
    read_only: Optional[bool] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=300)
    memory_mb: Optional[int] = Field(None, ge=64, le=1024)
    status: Optional[str] = Field(None, pattern=r'^(draft|active|archived)$')


class FunctionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    language: str
    code: str
    read_only: bool
    timeout_seconds: int
    memory_mb: int
    current_version: int
    status: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FunctionListResponse(BaseModel):
    items: List[FunctionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class FunctionTestRequest(BaseModel):
    parameters: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)


class FunctionTestResponse(BaseModel):
    success: bool
    output: Optional[Any] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration_ms: int
    memory_peak_mb: Optional[float] = None


class SearchResultItem(BaseModel):
    object_id: UUID
    object_type: str
    object_key: str
    label: str
    score: float
    source: str
    explanation: Optional[str] = None
    properties_preview: Dict[str, Any]


class OntologySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    object_types: Optional[List[str]] = None
    search_mode: str = Field(default="hybrid", pattern=r'^(vector|graph|hybrid|keyword)$')
    top_k: int = Field(default=20, ge=1, le=100)
    explain: bool = False


class OntologySearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]
    total: int
    vector_hits: int
    graph_hits: int
    reranked: bool
    duration_ms: int


class ImportError(BaseModel):
    entity_type: str
    entity_name: str
    error: str


class OntologyImportRequest(BaseModel):
    object_types: List[Dict[str, Any]] = Field(default_factory=list)
    link_types: List[Dict[str, Any]] = Field(default_factory=list)
    interfaces: List[Dict[str, Any]] = Field(default_factory=list)
    action_types: List[Dict[str, Any]] = Field(default_factory=list)
    functions: List[Dict[str, Any]] = Field(default_factory=list)
    conflict_strategy: str = Field(default="skip", pattern=r'^(skip|overwrite|rename)$')


class OntologyImportResult(BaseModel):
    imported_object_types: int
    imported_link_types: int
    imported_interfaces: int
    imported_action_types: int
    imported_functions: int
    skipped: int
    overwritten: int
    renamed: int
    errors: List[ImportError]


class RecentAction(BaseModel):
    id: UUID
    action_name: str
    target_object_key: str
    status: str
    executed_by: Optional[str] = None
    executed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class DashboardStats(BaseModel):
    object_type_count: int
    object_instance_count: int
    link_type_count: int
    interface_count: int
    action_type_count: int
    function_count: int
    action_execution_count: int
    recent_actions: List[RecentAction]


class ValueTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    base_type: str = Field(..., pattern=r'^(string|int|float|date|boolean|json)$')
    validation_regex: Optional[str] = None
    enum_values: Optional[List[str]] = None


class ValueTypeResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    base_type: str
    validation_regex: Optional[str] = None
    enum_values: Optional[List[str]] = None
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ValueTypeListResponse(BaseModel):
    items: List[ValueTypeResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Compile / Rollback / Validation / DAG
# ---------------------------------------------------------------------------

class RollbackRequest(BaseModel):
    log_id: UUID


class ValidationResponse(BaseModel):
    is_valid: bool
    errors: List[Dict[str, Any]]
    error_count: int
    warning_count: int


class CompileLogResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    version: str
    parent_version: Optional[str] = None
    compile_type: str
    status: str
    affected_types: List[UUID]
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    error_count: int = 0
    warning_count: int = 0


class CompileLogListResponse(BaseModel):
    items: List[CompileLogResponse]
    total: int
    limit: int
    offset: int


class DAGCycleResponse(BaseModel):
    has_cycle: bool
    cycle_path: Optional[List[str]] = None
    cycle_description: Optional[str] = None


class DAGImpactResponse(BaseModel):
    node_id: str
    impact_set: List[str]
    impact_count: int


PropertyDef.model_rebuild()
InterfaceLinkRequirement.model_rebuild()
ActionParameter.model_rebuild()
ActionRule.model_rebuild()
PropertyValidation.model_rebuild()