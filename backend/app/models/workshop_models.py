"""Workshop app persistence models — S3-3, V4-1.

A Workshop is a saved layout of nodes (Table, Chart, Action, etc.) and the
edges that wire their data together. We store the entire React Flow graph
as JSONB so the editor can round-trip the state without a custom DSL.

V4-1 adds ``WorkshopExecution``: a snapshot of one Run click. We persist
the per-node outputs so a user can re-open a previous run and inspect
its results without re-executing.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid as uuid_module

from app.services.database import Base


class WorkshopApp(Base):
    __tablename__ = "workshop_apps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    description = Column(Text)
    # React Flow state: { nodes: [...], edges: [...], viewport: {...} }
    graph = Column(JSONB, nullable=False, default=dict)
    status = Column(String(50), nullable=False, default="draft")  # draft / published / archived
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()")

    __table_args__ = (
        Index("idx_workshop_apps_tenant", "tenant_id"),
        Index("idx_workshop_apps_status", "tenant_id", "status"),
    )


class WorkshopExecution(Base):
    """One Run of a workshop app.

    ``graph_snapshot`` captures the graph at the moment the run started so
    historical results survive later edits to the app. ``results`` is keyed
    by node id: ``{ node_id: { status, output, error, duration_ms } }``.
    """

    __tablename__ = "workshop_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    app_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workshop_apps.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(20), nullable=False, default="running")
    # running | completed | failed | partial (some nodes failed)
    graph_snapshot = Column(JSONB, nullable=False, default=dict)
    results = Column(JSONB, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True), server_default="NOW()")
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    error_message = Column(Text)

    __table_args__ = (
        Index("idx_workshop_executions_app", "app_id"),
        Index("idx_workshop_executions_tenant", "tenant_id"),
        Index("idx_workshop_executions_status", "tenant_id", "status"),
        CheckConstraint(
            "status IN ('running','completed','failed','partial')",
            name="chk_workshop_execution_status",
        ),
    )

