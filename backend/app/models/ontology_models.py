from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Index, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.services.database import Base
import uuid as uuid_module
from datetime import datetime


class OntologyValueType(Base):
    __tablename__ = "ontology_value_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)
    base_type = Column(String(20), nullable=False)
    validation_regex = Column(String(500))
    enum_values = Column(JSONB)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())

    __table_args__ = (
        Index("idx_ontology_value_types_tenant", "tenant_id"),
        {"schema": None},
    )


class OntologyObjectType(Base):
    __tablename__ = "ontology_object_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)
    icon = Column(String(50), default="box")
    properties = Column(JSONB, nullable=False, default=list)
    implemented_interfaces = Column(JSONB, nullable=False, default=list)
    neo4j_label = Column(String(255), nullable=False)
    neo4j_constraints = Column(JSONB, default=list)
    status = Column(String(20), default="draft")
    version = Column(Integer, default=1)
    compiled_at = Column(DateTime(timezone=True))
    compile_status = Column(String(20), default="pending")
    compile_errors = Column(JSONB, default=list)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())

    __table_args__ = (
        Index("idx_ontology_object_types_tenant", "tenant_id"),
        Index("idx_ontology_object_types_status", "status"),
        Index("idx_ontology_object_types_compile", "tenant_id", "compile_status"),
        CheckConstraint("status IN ('draft','active','archived')", name="chk_object_type_status"),
        CheckConstraint("compile_status IN ('pending','compiled','error')", name="chk_object_type_compile_status"),
        {"schema": None},
    )


class OntologyLinkType(Base):
    __tablename__ = "ontology_link_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)
    source_object_type_id = Column(UUID(as_uuid=True), ForeignKey("ontology_object_types.id", ondelete="CASCADE"), nullable=False)
    target_object_type_id = Column(UUID(as_uuid=True), ForeignKey("ontology_object_types.id", ondelete="CASCADE"), nullable=False)
    cardinality = Column(String(20), default="MANY_TO_ONE")
    neo4j_edge_type = Column(String(255), nullable=False)
    neo4j_properties = Column(JSONB, default=list)
    status = Column(String(20), default="active")
    version = Column(Integer, default=1)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())

    __table_args__ = (
        Index("idx_ontology_link_types_tenant", "tenant_id"),
        Index("idx_ontology_link_types_source", "source_object_type_id"),
        Index("idx_ontology_link_types_target", "target_object_type_id"),
        CheckConstraint("cardinality IN ('ONE_TO_ONE','ONE_TO_MANY','MANY_TO_ONE','MANY_TO_MANY')", name="chk_link_type_cardinality"),
        CheckConstraint("status IN ('draft','active','archived')", name="chk_link_type_status"),
        {"schema": None},
    )


class OntologyInterface(Base):
    __tablename__ = "ontology_interfaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)
    required_properties = Column(JSONB, nullable=False, default=list)
    required_links = Column(JSONB, nullable=False, default=list)
    status = Column(String(20), default="active")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())

    __table_args__ = (
        Index("idx_ontology_interfaces_tenant", "tenant_id"),
        CheckConstraint("status IN ('draft','active','archived')", name="chk_interface_status"),
        {"schema": None},
    )


class OntologyActionType(Base):
    __tablename__ = "ontology_action_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)
    target_object_type_id = Column(UUID(as_uuid=True), ForeignKey("ontology_object_types.id", ondelete="CASCADE"), nullable=False)
    parameters = Column(JSONB, nullable=False, default=list)
    modifies_properties = Column(JSONB, nullable=False, default=list)
    modifies_links = Column(JSONB, nullable=False, default=list)
    rules = Column(JSONB, nullable=False, default=list)
    execution_type = Column(String(20), default="direct")
    function_id = Column(UUID(as_uuid=True), ForeignKey("ontology_functions.id"))
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("decision_flows.id"))
    status = Column(String(20), default="active")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())

    __table_args__ = (
        Index("idx_ontology_action_types_tenant", "tenant_id"),
        Index("idx_ontology_action_types_target", "target_object_type_id"),
        CheckConstraint("execution_type IN ('direct','function_backed','workflow')", name="chk_action_execution_type"),
        CheckConstraint("status IN ('draft','active','archived')", name="chk_action_status"),
        {"schema": None},
    )


class OntologyFunction(Base):
    __tablename__ = "ontology_functions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)
    language = Column(String(20), default="python")
    code = Column(Text, nullable=False)
    read_only = Column(Boolean, default=False)
    timeout_seconds = Column(Integer, default=30)
    memory_mb = Column(Integer, default=256)
    status = Column(String(20), default="active")
    current_version = Column(Integer, default=1)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())

    __table_args__ = (
        Index("idx_ontology_functions_tenant", "tenant_id"),
        CheckConstraint("language IN ('python','typescript')", name="chk_function_language"),
        CheckConstraint("status IN ('draft','active','archived')", name="chk_function_status"),
        {"schema": None},
    )


class OntologyFunctionVersion(Base):
    __tablename__ = "ontology_function_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    function_id = Column(UUID(as_uuid=True), ForeignKey("ontology_functions.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    code = Column(Text, nullable=False)
    change_notes = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")

    __table_args__ = (
        Index("idx_ontology_function_versions_func", "function_id"),
        {"schema": None},
    )


class OntologyObject(Base):
    __tablename__ = "ontology_objects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    object_type_id = Column(UUID(as_uuid=True), ForeignKey("ontology_object_types.id", ondelete="CASCADE"), nullable=False)
    object_key = Column(String(255), nullable=False)
    properties = Column(JSONB, nullable=False, default=dict)
    neo4j_node_id = Column(String(255))
    source_type = Column(String(50), default="manual")
    source_id = Column(String(255))
    status = Column(String(20), default="active")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())

    __table_args__ = (
        Index("idx_ontology_objects_tenant", "tenant_id"),
        Index("idx_ontology_objects_type", "object_type_id"),
        Index("idx_ontology_objects_key", "tenant_id", "object_type_id", "object_key"),
        Index("idx_ontology_objects_neo4j", "neo4j_node_id"),
        CheckConstraint("status IN ('active','archived','deleted')", name="chk_object_status"),
        {"schema": None},
    )


class OntologyLink(Base):
    __tablename__ = "ontology_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    link_type_id = Column(UUID(as_uuid=True), ForeignKey("ontology_link_types.id", ondelete="CASCADE"), nullable=False)
    source_object_id = Column(UUID(as_uuid=True), ForeignKey("ontology_objects.id", ondelete="CASCADE"), nullable=False)
    target_object_id = Column(UUID(as_uuid=True), ForeignKey("ontology_objects.id", ondelete="CASCADE"), nullable=False)
    properties = Column(JSONB, nullable=False, default=dict)
    neo4j_rel_id = Column(String(255))
    source_type = Column(String(50), default="manual")
    source_id = Column(String(255))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())

    __table_args__ = (
        Index("idx_ontology_links_tenant", "tenant_id"),
        Index("idx_ontology_links_type", "link_type_id"),
        Index("idx_ontology_links_source", "source_object_id"),
        Index("idx_ontology_links_target", "target_object_id"),
        {"schema": None},
    )


class ActionExecutionLog(Base):
    __tablename__ = "action_execution_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    action_type_id = Column(UUID(as_uuid=True), ForeignKey("ontology_action_types.id", ondelete="SET NULL"))
    target_object_id = Column(UUID(as_uuid=True), ForeignKey("ontology_objects.id", ondelete="SET NULL"))
    target_object_type_id = Column(UUID(as_uuid=True), ForeignKey("ontology_object_types.id", ondelete="SET NULL"))
    parameters = Column(JSONB, nullable=False, default=dict)
    result = Column(JSONB)
    status = Column(String(20), nullable=False)
    error_message = Column(Text)
    rules_evaluation = Column(JSONB, default=list)
    execution_type = Column(String(20))
    function_version = Column(Integer)
    workflow_execution_id = Column(UUID(as_uuid=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    executed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    executed_at = Column(DateTime(timezone=True), server_default="NOW()")
    ip_address = Column(String(50))
    user_agent = Column(Text)

    __table_args__ = (
        Index("idx_action_logs_tenant", "tenant_id"),
        Index("idx_action_logs_action", "action_type_id"),
        Index("idx_action_logs_object", "target_object_id"),
        Index("idx_action_logs_status", "status"),
        Index("idx_action_logs_executed_at", "tenant_id", "executed_at"),
        CheckConstraint("status IN ('pending','running','success','failed','timeout')", name="chk_execution_status"),
        {"schema": None},
    )


class OntologyCompileLog(Base):
    __tablename__ = "ontology_compile_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    version = Column(String(20), nullable=False)              # e.g. "1.3.0"
    parent_version = Column(String(20))                        # for rollback chain
    compile_type = Column(String(20), nullable=False)
    affected_types = Column(JSONB, default=list)               # UUID[] of affected ObjectType IDs
    diff_snapshot = Column(JSONB, nullable=False, default=dict) # schema diff for rollback
    neo4j_stmts = Column(JSONB, default=list)                  # executed Cypher statements
    status = Column(String(20), nullable=False, default="pending")
    errors = Column(JSONB, default=list)
    warnings = Column(JSONB, default=list)
    graphql_schema_snapshot = Column(Text)
    neo4j_constraints_snapshot = Column(JSONB, default=list)
    error_detail = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default="NOW()")
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    executed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    rolled_back_at = Column(DateTime(timezone=True))
    rolled_back_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    __table_args__ = (
        Index("idx_compile_logs_tenant", "tenant_id"),
        Index("idx_compile_logs_status", "status"),
        CheckConstraint("compile_type IN ('full','incremental')", name="chk_compile_type"),
        CheckConstraint("status IN ('pending','running','success','failed','rolled_back')", name="chk_compile_status"),
        {"schema": None},
    )


class OntologyCurrentVersion(Base):
    __tablename__ = "ontology_current_version"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    version = Column(String(20), nullable=False)
    log_id = Column(UUID(as_uuid=True), ForeignKey("ontology_compile_logs.id"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        {"schema": None},
    )


class AIPLLMCall(Base):
    __tablename__ = "aip_llm_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    messages = Column(JSONB, nullable=False)
    parameters = Column(JSONB, default=dict)
    response_text = Column(Text)
    response_json = Column(JSONB)
    finish_reason = Column(String(50))
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost_cents = Column(Integer, default=0)
    first_token_ms = Column(Integer)
    total_duration_ms = Column(Integer)
    session_id = Column(String(255))
    trace_id = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")

    __table_args__ = (
        Index("idx_aip_llm_calls_tenant", "tenant_id"),
        Index("idx_aip_llm_calls_user", "user_id"),
        Index("idx_aip_llm_calls_session", "session_id"),
        Index("idx_aip_llm_calls_created", "tenant_id", "created_at"),
        {"schema": None},
    )


class AIPAgentSession(Base):
    __tablename__ = "aip_agent_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    agent_id = Column(String(255), nullable=False)
    agent_name = Column(String(255))
    state = Column(JSONB, default=dict)
    thread_id = Column(String(255))
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())
    ended_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_aip_agent_sessions_tenant", "tenant_id"),
        Index("idx_aip_agent_sessions_thread", "thread_id"),
        CheckConstraint("status IN ('active','paused','completed','error')", name="chk_agent_status"),
        {"schema": None},
    )


class AIPRAGQuery(Base):
    __tablename__ = "aip_rag_queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    query_text = Column(Text, nullable=False)
    entity_context = Column(JSONB, default=dict)
    vector_results_count = Column(Integer, default=0)
    graph_results_count = Column(Integer, default=0)
    reranked_results_count = Column(Integer, default=0)
    answer_text = Column(Text)
    sources = Column(JSONB, default=list)
    vector_search_ms = Column(Integer)
    graph_search_ms = Column(Integer)
    rerank_ms = Column(Integer)
    llm_generation_ms = Column(Integer)
    total_duration_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default="NOW()")

    __table_args__ = (
        Index("idx_aip_rag_queries_tenant", "tenant_id"),
        Index("idx_aip_rag_queries_created", "tenant_id", "created_at"),
        {"schema": None},
    )


class AIPGuardrailsLog(Base):
    __tablename__ = "aip_guardrails_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    check_type = Column(String(50), nullable=False)
    llm_call_id = Column(UUID(as_uuid=True), ForeignKey("aip_llm_calls.id", ondelete="SET NULL"))
    content_snapshot = Column(Text)
    content_hash = Column(String(64))
    passed = Column(Boolean, nullable=False)
    violations = Column(JSONB, default=list)
    action_taken = Column(String(50))
    pii_entities = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), server_default="NOW()")

    __table_args__ = (
        Index("idx_aip_guardrails_tenant", "tenant_id"),
        Index("idx_aip_guardrails_llm", "llm_call_id"),
        Index("idx_aip_guardrails_type", "tenant_id", "check_type"),
        CheckConstraint("check_type IN ('input','output','pii')", name="chk_guardrails_check_type"),
        {"schema": None},
    )


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)
    connection_config = Column(JSONB, nullable=False)
    description = Column(Text)
    status = Column(String(20), default="active")
    last_tested_at = Column(DateTime(timezone=True))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())

    __table_args__ = (
        Index("idx_data_sources_tenant", "tenant_id"),
        CheckConstraint("source_type IN ('mysql','postgresql','oracle','mongodb','kafka','s3','api')", name="chk_source_type"),
        CheckConstraint("status IN ('active','inactive','error')", name="chk_source_status"),
        {"schema": None},
    )


class DataPipeline(Base):
    __tablename__ = "data_pipelines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id"), nullable=False)
    target_object_type_id = Column(UUID(as_uuid=True), ForeignKey("ontology_object_types.id"))
    config_json = Column(JSONB, nullable=False)
    config_yaml = Column(Text)
    schedule_type = Column(String(20), default="manual")
    schedule_expr = Column(String(255))
    status = Column(String(20), default="draft")
    last_run_at = Column(DateTime(timezone=True))
    last_run_status = Column(String(20))
    last_run_log = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())

    __table_args__ = (
        Index("idx_data_pipelines_tenant", "tenant_id"),
        Index("idx_data_pipelines_source", "source_id"),
        CheckConstraint("schedule_type IN ('manual','cron','event')", name="chk_schedule_type"),
        CheckConstraint("status IN ('draft','active','paused','archived')", name="chk_pipeline_status"),
        {"schema": None},
    )


class CDCSubscription(Base):
    __tablename__ = "cdc_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    data_source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    connector_name = Column(String(255), nullable=False)
    database_name = Column(String(255), nullable=False)
    table_name = Column(String(255), nullable=False)
    target_object_type_id = Column(UUID(as_uuid=True), ForeignKey("ontology_object_types.id"))
    field_mappings = Column(JSONB, nullable=False, default=list)
    status = Column(String(20), default="active")
    lag_seconds = Column(Integer, default=0)
    last_event_at = Column(DateTime(timezone=True))
    total_events = Column(BigInteger, default=0)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()", onupdate=func.now())

    __table_args__ = (
        Index("idx_cdc_subscriptions_tenant", "tenant_id"),
        Index("idx_cdc_subscriptions_source", "data_source_id"),
        CheckConstraint("status IN ('active','paused','error')", name="chk_cdc_status"),
        {"schema": None},
    )