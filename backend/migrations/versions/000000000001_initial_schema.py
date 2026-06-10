"""Initial schema migration.

Creates all tables defined in SQLAlchemy Base metadata.
This is the baseline migration for Meatapivot v2.2.

Note: This migration uses Base.metadata.create_all for the baseline.
Subsequent migrations should use explicit op.create_table/alter_column.
"""

from alembic import op
from sqlalchemy import create_engine
from app.services.database import Base
from app.models.database_models import *  # noqa: F401,F403
from app.models.ontology_models import *  # noqa: F401,F403

# revision identifiers, used by Alembic.
revision = "000000000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables from SQLAlchemy metadata via run_sync."""
    bind = op.get_bind()
    sync_url = str(bind.url).replace("+asyncpg", "")
    engine = create_engine(sync_url)
    Base.metadata.create_all(engine)


def downgrade() -> None:
    """Drop all tables."""
    bind = op.get_bind()
    sync_url = str(bind.url).replace("+asyncpg", "")
    engine = create_engine(sync_url)
    Base.metadata.drop_all(engine)
