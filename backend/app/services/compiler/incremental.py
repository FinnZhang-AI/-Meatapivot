"""Incremental compilation using DAG impact set.

P1-01/P1-02: BFS impact set for incremental compilation - only recompiles
affected types when a single ObjectType changes.
"""

import logging
from typing import List, Set, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ontology_models import OntologyObjectType, OntologyCompileLog
from app.services.ontology_dag import OntologyDAG
from app.services.compiler.neo4j_emitter import Neo4jEmitter

logger = logging.getLogger(__name__)


class IncrementalCompiler:
    """Handles incremental compilation using DAG-based impact analysis."""

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self._dag: Optional[OntologyDAG] = None

    async def _build_dag(self) -> OntologyDAG:
        """Build dependency DAG from ontology definitions."""
        if self._dag is not None:
            return self._dag

        from app.services.ontology_service import OntologyService
        service = OntologyService(self.db, self.tenant_id)
        self._dag = await service.build_dependency_dag()
        return self._dag

    async def get_affected_types(self, changed_type_id: UUID) -> Set[UUID]:
        """Get all types affected by a change to the given type.
        
        Uses BFS to find all nodes that depend (directly or transitively)
        on the changed type.
        """
        dag = await self._build_dag()
        return dag.get_impact_set(changed_type_id)

    async def incremental_compile(
        self,
        changed_type_id: UUID,
        executed_by: Optional[UUID] = None,
    ) -> dict:
        """Incrementally compile only affected types.
        
        Returns dict with:
        - affected_count: number of types recompiled
        - affected_ids: list of affected type IDs
        - errors: any compilation errors
        """
        affected_ids = await self.get_affected_types(changed_type_id)
        affected_ids.add(changed_type_id)

        emitter = Neo4jEmitter(self.db, self.tenant_id)
        compiled_count = 0
        errors = []

        result = await self.db.execute(
            select(OntologyObjectType).where(
                OntologyObjectType.tenant_id == self.tenant_id,
                OntologyObjectType.id.in_(affected_ids),
            )
        )
        object_types = list(result.scalars().all())

        for ot in object_types:
            try:
                created, _ = await emitter.emit_constraints_for_object_type(ot)
                compiled_count += created
            except Exception as e:
                errors.append({
                    "object_type_id": str(ot.id),
                    "error": str(e),
                })
                logger.error(f"Failed to compile {ot.name}: {e}")

        return {
            "affected_count": len(affected_ids),
            "affected_ids": [str(n) for n in affected_ids],
            "constraints_created": compiled_count,
            "errors": errors,
        }

    async def get_compile_order_for_types(
        self,
        type_ids: Set[UUID],
    ) -> List[UUID]:
        """Get topologically sorted compile order for a set of type IDs."""
        dag = await self._build_dag()
        sorted_nodes, cycle = dag.topological_sort()

        if cycle:
            cycle_str = " -> ".join(str(n)[:8] for n in cycle)
            raise ValueError(f"Circular dependency detected: {cycle_str}")

        return [n for n in sorted_nodes if n in type_ids]