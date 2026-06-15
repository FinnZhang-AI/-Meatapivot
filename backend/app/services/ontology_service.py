"""Ontology service layer — business logic between Router and Repository.

P0-ARCH-03: Router/Service/Repository three-layer separation.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ontology_models import (
    OntologyObjectType,
    OntologyObject,
    OntologyLinkType,
    OntologyLink,
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

    async def list_object_types_paginated(
        self,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[OntologyObjectType], int]:
        """Return (items, total_count) for pagination."""
        items = await self.repo.list_object_types_paginated(self.tenant_id, status, limit, offset)
        total = await self.repo.count_object_types(self.tenant_id, status)
        return items, total
    
    async def check_object_type_name_exists(self, name: str) -> bool:
        """Check if ObjectType name already exists for this tenant."""
        return await self.repo.object_type_name_exists(self.tenant_id, name)
    
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
    # OntologyObject (instance)
    # ------------------------------------------------------------------
    
    async def get_object(self, object_id: UUID) -> Optional[OntologyObject]:
        return await self.repo.get_object(self.tenant_id, object_id)
    
    async def check_object_key_exists(self, object_type_id: UUID, object_key: str) -> bool:
        return await self.repo.object_key_exists(self.tenant_id, object_type_id, object_key)
    
    async def create_object(self, obj: OntologyObject) -> OntologyObject:
        return await self.repo.create_object(obj)
    
    async def list_objects_by_type(self, object_type_id: UUID) -> List[OntologyObject]:
        return await self.repo.list_objects_by_type(self.tenant_id, object_type_id)
    
    async def get_object_type_names(self, type_ids: List[UUID]) -> Dict[UUID, str]:
        return await self.repo.get_object_type_names(type_ids)
    
    async def update_object(
        self,
        object_id: UUID,
        object_key: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> Optional[OntologyObject]:
        return await self.repo.update_object(
            self.tenant_id, object_id,
            object_key=object_key,
            properties=properties,
            status=status,
        )
    
    # ------------------------------------------------------------------
    # LinkType
    # ------------------------------------------------------------------
    
    async def get_link_type(self, link_type_id: UUID) -> Optional[OntologyLinkType]:
        return await self.repo.get_link_type(self.tenant_id, link_type_id)
    
    async def list_link_types(self) -> List[OntologyLinkType]:
        return await self.repo.list_link_types(self.tenant_id)

    async def list_link_types_paginated(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[OntologyLinkType], int]:
        items = await self.repo.list_link_types_paginated(self.tenant_id, limit, offset)
        total = await self.repo.count_link_types(self.tenant_id)
        return items, total
    
    # ------------------------------------------------------------------
    # OntologyLink (instance)
    # ------------------------------------------------------------------
    
    async def get_link(self, link_id: UUID) -> Optional[OntologyLink]:
        return await self.repo.get_link(self.tenant_id, link_id)
    
    async def delete_link(self, link_id: UUID) -> bool:
        return await self.repo.delete_link(self.tenant_id, link_id)
    
    async def list_object_links(self, object_id: UUID) -> List[OntologyLink]:
        return await self.repo.list_object_links(self.tenant_id, object_id)
    
    async def get_link_type_names(self, link_type_ids: List[UUID]) -> Dict[UUID, str]:
        return await self.repo.get_link_type_names(link_type_ids)
    
    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------
    
    async def get_interface(self, interface_id: UUID) -> Optional[OntologyInterface]:
        return await self.repo.get_interface(self.tenant_id, interface_id)
    
    async def list_interfaces(self) -> List[OntologyInterface]:
        return await self.repo.list_interfaces(self.tenant_id)

    async def list_interfaces_paginated(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[OntologyInterface], int]:
        items = await self.repo.list_interfaces_paginated(self.tenant_id, limit, offset)
        total = await self.repo.count_interfaces(self.tenant_id)
        return items, total

    async def create_interface(self, data: Dict[str, Any]) -> OntologyInterface:
        iface = OntologyInterface(tenant_id=self.tenant_id, **data)
        return await self.repo.create_interface(iface)

    async def update_interface(
        self,
        interface_id: UUID,
        updates: Dict[str, Any],
    ) -> Optional[OntologyInterface]:
        return await self.repo.update_interface(self.tenant_id, interface_id, **updates)

    async def delete_interface(self, interface_id: UUID) -> bool:
        return await self.repo.delete_interface(self.tenant_id, interface_id)

    async def validate_all_interfaces(self) -> Dict[str, Any]:
        """Validate every active Interface and report per-ObjectType compliance.

        Returns a dict with:
          - ``status`` — "completed"
          - ``interfaces_total`` / ``interfaces_failed``
          - ``results`` — list of {interface_id, interface_name, total, passed, failed, details}
        """
        interfaces = await self.repo.list_interfaces(self.tenant_id)
        object_types = await self.repo.list_object_types(self.tenant_id, status="active")
        link_types = await self.repo.list_link_types(self.tenant_id)

        results: List[Dict[str, Any]] = []
        failed = 0

        for iface in interfaces:
            if iface.status == "archived":
                continue
            required_prop_names = {
                p["name"] for p in (iface.required_properties or []) if p.get("required", True)
            }
            required_link_names = {l["name"] for l in (iface.required_links or [])}

            implementing = [
                ot for ot in object_types
                if str(iface.id) in (ot.implemented_interfaces or [])
            ]

            details: List[Dict[str, Any]] = []
            passed_count = 0
            failed_count = 0

            for ot in implementing:
                ot_props = {p["name"] for p in (ot.properties or [])}
                missing_props = list(required_prop_names - ot_props)
                missing_links = [
                    req["name"] for req in (iface.required_links or [])
                    if not any(
                        lt.name == req["name"] and lt.source_object_type_id == ot.id
                        for lt in link_types
                    )
                ]
                is_passed = not missing_props and not missing_links
                if is_passed:
                    passed_count += 1
                else:
                    failed_count += 1
                details.append({
                    "object_type_id": str(ot.id),
                    "object_type_name": ot.name,
                    "passed": is_passed,
                    "missing_properties": missing_props,
                    "missing_links": missing_links,
                })

            if failed_count > 0:
                failed += 1

            results.append({
                "interface_id": str(iface.id),
                "interface_name": iface.name,
                "implementations_total": len(implementing),
                "passed": passed_count,
                "failed": failed_count,
                "details": details,
            })

        return {
            "status": "completed",
            "tenant_id": str(self.tenant_id),
            "interfaces_total": len(results),
            "interfaces_failed": failed,
            "results": results,
        }

    # ------------------------------------------------------------------
    # ActionType
    # ------------------------------------------------------------------

    async def get_action_type(self, action_type_id: UUID) -> Optional[OntologyActionType]:
        return await self.repo.get_action_type(self.tenant_id, action_type_id)

    async def list_action_types(self) -> List[OntologyActionType]:
        return await self.repo.list_action_types(self.tenant_id)

    async def list_action_types_paginated(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[OntologyActionType], int]:
        items = await self.repo.list_action_types_paginated(self.tenant_id, limit, offset)
        total = await self.repo.count_action_types(self.tenant_id)
        return items, total

    async def create_action_type(self, data: Dict[str, Any]) -> OntologyActionType:
        at = OntologyActionType(tenant_id=self.tenant_id, **data)
        return await self.repo.create_action_type(at)

    async def update_action_type(
        self,
        action_type_id: UUID,
        updates: Dict[str, Any],
    ) -> Optional[OntologyActionType]:
        return await self.repo.update_action_type(self.tenant_id, action_type_id, **updates)

    async def delete_action_type(self, action_type_id: UUID) -> bool:
        return await self.repo.delete_action_type(self.tenant_id, action_type_id)

    # ------------------------------------------------------------------
    # Function
    # ------------------------------------------------------------------

    async def get_function(self, function_id: UUID) -> Optional[OntologyFunction]:
        return await self.repo.get_function(self.tenant_id, function_id)

    async def list_functions(self) -> List[OntologyFunction]:
        return await self.repo.list_functions(self.tenant_id)

    async def list_functions_paginated(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[OntologyFunction], int]:
        items = await self.repo.list_functions_paginated(self.tenant_id, limit, offset)
        total = await self.repo.count_functions(self.tenant_id)
        return items, total

    async def create_function(self, data: Dict[str, Any]) -> OntologyFunction:
        fn = OntologyFunction(tenant_id=self.tenant_id, **data)
        return await self.repo.create_function(fn)

    async def update_function(
        self,
        function_id: UUID,
        updates: Dict[str, Any],
    ) -> Optional[OntologyFunction]:
        return await self.repo.update_function(self.tenant_id, function_id, **updates)

    async def delete_function(self, function_id: UUID) -> bool:
        return await self.repo.delete_function(self.tenant_id, function_id)

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
