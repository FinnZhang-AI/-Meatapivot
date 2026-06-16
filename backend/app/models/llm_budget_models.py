"""LLM budget / cost dashboard persistence — S4-1.

Each tenant can have at most one budget row (uniqueness enforced at the
service layer; the schema uses a plain index so a tenant can also have
historical budget snapshots later if we want to track threshold changes).
The model holds a monthly cost cap in USD cents and an alert threshold
(0.0-1.0) so the dashboard can show a "warning" state when actual
spend crosses ``monthly_budget_cents * alert_threshold_percent``.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
import uuid as uuid_module

from app.services.database import Base


class LLMBudget(Base):
    __tablename__ = "llm_budgets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Monthly cap in USD cents (e.g. 10000 = $100/month)
    monthly_budget_cents = Column(Integer, nullable=False, default=10000)
    # 0-100 — at what % of the cap we should warn (e.g. 80 = warn at 80%)
    alert_threshold_percent = Column(Integer, nullable=False, default=80)
    # Optional model-level overrides as JSON: {"gpt-4o": 600}
    model_overrides = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="NOW()")
    updated_at = Column(DateTime(timezone=True), server_default="NOW()")

    __table_args__ = (
        Index("idx_llm_budgets_tenant", "tenant_id", unique=True),
    )
