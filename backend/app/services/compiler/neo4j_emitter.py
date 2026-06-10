"""Neo4j constraint emitter for Ontology compiler.

P1-01: Generates Neo4j CREATE CONSTRAINT statements from ObjectType definitions.
"""

import logging
from typing import List, Set, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ontology_models import OntologyObjectType, OntologyLinkType
from app.services.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


class Neo4jEmitter:
    """Emits Neo4j constraints and schema statements."""

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self._constraints_log: List[str] = []

    async def emit_constraints_for_object_type(
        self,
        obj_type: OntologyObjectType,
    ) -> Tuple[int, List[str]]:
        """Emit Neo4j constraints for a single ObjectType.
        
        Returns: (count_created, list_of_constraint_names)
        """
        created = 0
        constraint_names = []

        if not obj_type.neo4j_label:
            obj_type.neo4j_label = obj_type.name

        required_props = [p for p in obj_type.properties if p.get("required", False)]
        unique_props = [p for p in required_props if p.get("validation", {}).get("unique")]

        for prop in unique_props:
            constraint_name = f"constraint_{obj_type.neo4j_label}_{prop['name']}_unique"
            cypher = f"""
            CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
            FOR (n:{obj_type.neo4j_label}) REQUIRE n.{prop['name']} IS UNIQUE
            """
            try:
                await neo4j_client.execute_query(cypher, {})
                created += 1
                constraint_names.append(constraint_name)
                self._constraints_log.append(constraint_name)
                logger.info(f"Created constraint: {constraint_name}")
            except Exception as e:
                error_str = str(e).lower()
                if "already exists" not in error_str and "constraint already exists" not in error_str:
                    raise

        return created, constraint_names

    async def drop_constraints(self, constraint_names: List[str]) -> int:
        """Drop a list of constraints by name."""
        dropped = 0
        for name in constraint_names:
            try:
                cypher = f"DROP CONSTRAINT {name} IF EXISTS"
                await neo4j_client.execute_query(cypher, {})
                dropped += 1
                logger.info(f"Dropped constraint: {name}")
            except Exception as e:
                logger.warning(f"Failed to drop constraint {name}: {e}")
        return dropped

    def get_constraints_log(self) -> List[str]:
        """Get list of constraints created during this session."""
        return self._constraints_log.copy()

    def clear_constraints_log(self) -> None:
        """Clear the constraints log."""
        self._constraints_log.clear()


async def get_active_object_types(db: AsyncSession, tenant_id: UUID) -> List[OntologyObjectType]:
    """Fetch all active ObjectTypes for a tenant."""
    result = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.tenant_id == tenant_id,
            OntologyObjectType.status == "active",
        )
    )
    return list(result.scalars().all())