from sqlalchemy import Column, String, DateTime, Boolean, Integer, BigInteger, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.services.database import Base
import uuid as uuid_module


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(String)
    config = Column(JSONB, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    documents = relationship("Document", back_populates="uploader")
    decision_flows = relationship("DecisionFlow", back_populates="creator")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100))
    bucket_name = Column(String(255), default="knowledge-base")
    object_key = Column(String(512), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    status = Column(String(50), default="uploaded")
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    uploader = relationship("User", back_populates="documents")


class DecisionFlow(Base):
    __tablename__ = "decision_flows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(String)
    dag_definition = Column(JSONB, nullable=False)
    version = Column(Integer, default=1)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    status = Column(String(50), default="draft")
    last_run_at = Column(DateTime(timezone=True))
    last_run_status = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    creator = relationship("User", back_populates="decision_flows")
    executions = relationship("FlowExecution", back_populates="flow", cascade="all, delete-orphan")


class FlowExecution(Base):
    __tablename__ = "flow_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    flow_id = Column(UUID(as_uuid=True), ForeignKey("decision_flows.id", ondelete="CASCADE"))
    execution_id = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), default="pending")
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    result = Column(JSONB)
    error_message = Column(String)
    logs = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    flow = relationship("DecisionFlow", back_populates="executions")


class KGEntity(Base):
    __tablename__ = "kg_entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    entity_name = Column(String(255), nullable=False)
    entity_type = Column(String(100))
    properties = Column(JSONB, default=dict)
    neo4j_node_id = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
