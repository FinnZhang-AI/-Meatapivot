"""Workshop app persistence models — S3-3.

A Workshop is a saved layout of nodes (Table, Chart, Action, etc.) and the
edges that wire their data together. We store the entire React Flow graph
as JSONB so the editor can round-trip the state without a custom DSL.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
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
