"""Ontology service layer — business logic between Router and Repository.

P0-ARCH-03: Router/Service/Repository three-layer separation.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ontology_models import (
    OntologyObjectType,
    OntologyLinkType,
    OntologyInterface,
    OntologyCompileLog,
    OntologyCurrentVersion,
)
from app.repositories.ontology_repo import OntologyRepository
from app.services.ontology_dag import OntologyDAG
from app.services.ontology_validator import StaticValidator, RuntimeValidator
from app.services.schema_registry import schema_registry

logger = logging.getLogger(__name__)


class OntologyService:
    """Service layer for ontology business logic."""
    
    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self.repo = OntologyRepository(db)
    
    # ------------------------------------------------------------------
    # ObjectType
    # ------------------------------------------------------------------
    
    async def get_object_type(self, object_type_id: UUID) -> Optional[OntologyObjectType]:
        return await self.repo.get_object_type(self.tenant_id, object_type_id)
    
    async def list_object_types(self, status: Optional[str] = None) -> List[OntologyObjectType]:
        return await self.repo.list_object_types(self.tenant_id, status)
    
    async def create_object_type(self, data: Dict[str, Any]) -> OntologyObjectType:
        """Create ObjectType with validation."""
        obj = OntologyObjectType(tenant_id=self.tenant_id, **data)
        
        # Validate
        validator = StaticValidator()
        errors = validator.validate_object_type(obj)
        if errors:
            logger.warning(f"ObjectType validation errors: {errors}")
            # Still create but mark as draft with errors
            obj.status = "draft"
            obj.compile_errors = [e.to_dict() for e in errors]
        
        created = await self.repo.create_object_type(obj)
        
        # Invalidate cache
        await schema_registry.invalidate(self.tenant_id, "object_type", created.id)
        
        return created
    
    async def update_object_type(
        self,
        object_type_id: UUID,
        updates: Dict[str, Any],
    ) -> Optional[OntologyObjectType]:
        """Update ObjectType and invalidate cache."""
        obj = await self.repo.update_object_type(self.tenant_id, object_type_id, **updates)
        if obj:
            await schema_registry.invalidate(self.tenant_id, "object_type", obj.id)
        return obj
    
    async def delete_object_type(self, object_type_id: UUID) -> bool:
        """Delete ObjectType and invalidate cache."""
        result = await self.repo.delete_object_type(self.tenant_id, object_type_id)
        if result:
            await schema_registry.invalidate(self.tenant_id, "object_type", object_type_id)
        return result
    
    # ------------------------------------------------------------------
    # LinkType
    # ------------------------------------------------------------------
    
    async def get_link_type(self, link_type_id: UUID) -> Optional[OntologyLinkType]:
        return await self.repo.get_link_type(self.tenant_id, link_type_id)
    
    async def list_link_types(self) -> List[OntologyLinkType]:
        return await self.repo.list_link_types(self.tenant_id)
    
    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------
    
    async def get_interface(self, interface_id: UUID) -> Optional[OntologyInterface]:
        return await self.repo.get_interface(self.tenant_id, interface_id)
    
    async def list_interfaces(self) -> List[OntologyInterface]:
        return await self.repo.list_interfaces(self.tenant_id)
    
    # ------------------------------------------------------------------
    # DAG / Dependency
    # ------------------------------------------------------------------
    
    async def build_dependency_dag(self) -> OntologyDAG:
        """Build DAG from current ontology definitions.
        
        Edges represent dependencies:
        - ObjectType -> Interface (implements)
        - LinkType -> ObjectType (source/target)
        """
        dag = OntologyDAG()
        
        obj_types = await self.list_object_types()
        link_types = await self.list_link_types()
        interfaces = await self.list_interfaces()
        
        # Add all nodes
        for obj in obj_types:
            dag.add_node(obj.id)
        for link in link_types:
            dag.add_node(link.id)
        for interface in interfaces:
            dag.add_node(interface.id)
        
        # Add edges: ObjectType depends on Interface
        for obj in obj_types:
            if obj.implemented_interfaces:
                for interface_id in obj.implemented_interfaces:
                    try:
                        iid = UUID(interface_id)
                        dag.add_edge(iid, obj.id)  # obj depends on interface
                    except (ValueError, TypeError):
                        continue
        
        # Add edges: LinkType depends on ObjectType (source and target)
        for link in link_types:
            dag.add_edge(link.source_object_type_id, link.id)
            dag.add_edge(link.target_object_type_id, link.id)
        
        return dag
    
    async def detect_cycles(self) -> Optional[List[UUID]]:
        """Detect cycles in ontology dependencies.
        
        Returns cycle path if found, None otherwise.
        """
        dag = await self.build_dependency_dag()
        return dag.find_cycle()
    
    async def get_compile_order(self) -> List[UUID]:
        """Get topological compile order.
        
        Raises ValueError if cycle detected.
        """
        dag = await self.build_dependency_dag()
        sorted_nodes, cycle = dag.topological_sort()
        if cycle:
            cycle_str = " -> ".join(str(n)[:8] for n in cycle)
            raise ValueError(f"Circular dependency detected: {cycle_str}")
        return sorted_nodes
    
    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    
    async def validate_all(self) -> List[Dict[str, Any]]:
        """Run static validation on all ontology definitions."""
        obj_types = await self.list_object_types()
        link_types = await self.list_link_types()
        interfaces = await self.list_interfaces()
        
        validator = StaticValidator()
        errors = validator.validate_all(obj_types, link_types, interfaces)
        
        return [e.to_dict() for e in errors]
    
    # ------------------------------------------------------------------
    # Compile Log / Version
    # ------------------------------------------------------------------
    
    async def get_compile_logs(self, limit: int = 20, offset: int = 0) -> List[OntologyCompileLog]:
        return await self.repo.list_compile_logs(self.tenant_id, limit, offset)
    
    async def get_current_version(self) -> Optional[OntologyCurrentVersion]:
        return await self.repo.get_current_version(self.tenant_id)
    
    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    
    async def get_dashboard_stats(self) -> Dict[str, Any]:
        return await self.repo.get_dashboard_counts(self.tenant_id)
    
    # ------------------------------------------------------------------
    # Schema Cache
    # ------------------------------------------------------------------
    
    async def get_cached_schema(
        self,
        type_name: str,
        type_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        return await schema_registry.get(self.tenant_id, type_name, type_id)
    
    async def cache_schema(
        self,
        type_name: str,
        type_id: UUID,
        schema: Dict[str, Any],
    ) -> None:
        await schema_registry.set(self.tenant_id, type_name, type_id, schema)
