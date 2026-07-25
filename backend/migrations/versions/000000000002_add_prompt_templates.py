"""Add aip_prompt_templates table.

Revision ID: 000000000002
Revises: 000000000001
Create Date: 2026-06-14

AIP-009: Prompt Template Management — first-class multi-tenant CRUD + render.

This migration is defensive: migration 000000000001 calls
``Base.metadata.create_all`` which already provisions the
``aip_prompt_templates`` table plus its non-partial indexes. We therefore
use ``CREATE TABLE / CREATE INDEX IF NOT EXISTS`` so the migration can be
applied on top of either a fresh DB or one created by 000000000001.

The unique partial index enforcing ``(tenant_id, name) WHERE is_active = true``
is *not* produced by ``create_all`` reliably across SQLAlchemy versions for
the conditional ``WHERE`` predicate, so we add it explicitly.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "000000000002"
down_revision = "000000000001"
branch_labels = None
depends_on = None


_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS aip_prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    template_text TEXT NOT NULL,
    variables JSONB DEFAULT '[]'::jsonb,
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    is_ab_test BOOLEAN DEFAULT FALSE,
    ab_test_group VARCHAR(50),
    usage_count INTEGER DEFAULT 0,
    avg_prompt_tokens INTEGER DEFAULT 0,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""


def upgrade() -> None:
    op.execute(_TABLE_DDL)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_aip_prompt_templates_tenant "
        "ON aip_prompt_templates (tenant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_aip_prompt_templates_name "
        "ON aip_prompt_templates (tenant_id, name)"
    )
    # Partial unique: only one *active* template per (tenant, name).
    # Archived copies (is_active=False) may share a name for history.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_aip_prompt_templates_tenant_name_active "
        "ON aip_prompt_templates (tenant_id, name) WHERE is_active = TRUE"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_aip_prompt_templates_tenant_name_active")
    op.execute("DROP TABLE IF EXISTS aip_prompt_templates")
