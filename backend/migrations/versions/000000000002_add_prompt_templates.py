"""Add aip_prompt_templates table.

Revision ID: 000000000002
Revises: 000000000001
Create Date: 2026-06-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "000000000002"
down_revision = "000000000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aip_prompt_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("template_text", sa.Text, nullable=False),
        sa.Column("variables", JSONB, default=list),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("is_ab_test", sa.Boolean, default=False),
        sa.Column("ab_test_group", sa.String(50)),
        sa.Column("usage_count", sa.Integer, default=0),
        sa.Column("avg_prompt_tokens", sa.Integer, default=0),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), onupdate=sa.text("NOW()")),
        sa.Index("idx_aip_prompt_templates_tenant", "tenant_id"),
        sa.Index("idx_aip_prompt_templates_name", "tenant_id", "name"),
    )


def downgrade() -> None:
    op.drop_table("aip_prompt_templates")
