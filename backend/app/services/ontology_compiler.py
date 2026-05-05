import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ontology_models import (
    OntologyObjectType, OntologyLinkType, OntologyInterface,
    OntologyCompileLog, ActionExecutionLog
)
from app.models.ontology_schemas import CompileResult, CompileError
from app.services.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


class OntologyCompiler:
    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self.errors: List[CompileError] = []
        self.warnings: List[str] = []
        self.constraints_created = 0
    
    async def full_compile(self, executed_by: Optional[UUID] = None) -> CompileResult:
        """Full compilation of all active Ontology definitions"""
        start_time = int(time.time() * 1000)
        
        compile_log = OntologyCompileLog(
            tenant_id=self.tenant_id,
            compile_type="full",
            status="running",
            executed_by=executed_by
        )
        self.db.add(compile_log)
        await self.db.flush()
        
        try:
            result = await self._compile_all()
            
            compile_log.status = "success" if not result.errors else "failed"
            compile_log.errors = [e.model_dump() for e in result.errors]
            compile_log.warnings = result.warnings
            compile_log.neo4j_constraints_snapshot = []
            compile_log.duration_ms = result.duration_ms
            compile_log.completed_at = datetime.utcnow()
            
            await self.db.flush()
            
            return result
            
        except Exception as e:
            logger.error(f"Full compile failed: {e}")
            self.errors.append(CompileError(code="FULL_COMPILE_ERROR", message=str(e)))
            
            compile_log.status = "failed"
            compile_log.errors = [e.model_dump() for e in self.errors]
            compile_log.duration_ms = int(time.time() * 1000) - start_time
            compile_log.completed_at = datetime.utcnow()
            await self.db.flush()
            
            return CompileResult(
                status="has_errors",
                errors=self.errors,
                warnings=self.warnings,
                neo4j_constraints_created=0,
                duration_ms=int(time.time() * 1000) - start_time
            )
    
    async def incremental_compile(
        self,
        object_type_id: UUID,
        executed_by: Optional[UUID] = None
    ) -> CompileResult:
        """Compile a single Object Type and its dependencies"""
        start_time = int(time.time() * 1000)
        
        compile_log = OntologyCompileLog(
            tenant_id=self.tenant_id,
            compile_type="incremental",
            target_object_type_id=object_type_id,
            status="running",
            executed_by=executed_by
        )
        self.db.add(compile_log)
        await self.db.flush()
        
        try:
            result = await self._compile_object_type(object_type_id)
            
            compile_log.status = "success" if not result.errors else "failed"
            compile_log.errors = [e.model_dump() for e in result.errors]
            compile_log.warnings = result.warnings
            compile_log.duration_ms = result.duration_ms
            compile_log.completed_at = datetime.utcnow()
            
            await self.db.flush()
            
            return result
            
        except Exception as e:
            logger.error(f"Incremental compile failed for {object_type_id}: {e}")
            self.errors.append(CompileError(
                code="INCREMENTAL_COMPILE_ERROR",
                message=str(e),
                field=str(object_type_id)
            ))
            
            compile_log.status = "failed"
            compile_log.errors = [e.model_dump() for e in self.errors]
            compile_log.duration_ms = int(time.time() * 1000) - start_time
            compile_log.completed_at = datetime.utcnow()
            await self.db.flush()
            
            return CompileResult(
                status="has_errors",
                errors=self.errors,
                warnings=self.warnings,
                neo4j_constraints_created=0,
                duration_ms=int(time.time() * 1000) - start_time
            )
    
    async def _compile_all(self) -> CompileResult:
        """Internal method to compile all Object Types"""
        result = await self.db.execute(
            select(OntologyObjectType).where(
                OntologyObjectType.tenant_id == self.tenant_id,
                OntologyObjectType.status == "active"
            )
        )
        object_types = result.scalars().all()
        
        compiled_count = 0
        for ot in object_types:
            result = await self._compile_object_type(ot.id)
            if result.errors:
                for err in result.errors:
                    self.errors.append(err)
            else:
                compiled_count += 1
            self.warnings.extend(result.warnings)
        
        duration_ms = int(time.time() * 1000)
        
        return CompileResult(
            status="compiled" if not self.errors else "has_errors",
            errors=self.errors,
            warnings=self.warnings,
            neo4j_constraints_created=self.constraints_created,
            duration_ms=duration_ms
        )
    
    async def _compile_object_type(self, object_type_id: UUID) -> CompileResult:
        """Compile a single Object Type and validate Interface implementations"""
        start_time = int(time.time() * 1000)
        
        result = await self.db.execute(
            select(OntologyObjectType).where(
                OntologyObjectType.id == object_type_id,
                OntologyObjectType.tenant_id == self.tenant_id
            )
        )
        obj_type = result.scalar_one_or_none()
        
        if not obj_type:
            return CompileResult(
                status="has_errors",
                errors=[CompileError(
                    code="NOT_FOUND",
                    message=f"Object Type {object_type_id} not found",
                    field="id"
                )],
                warnings=[],
                neo4j_constraints_created=0,
                duration_ms=int(time.time() * 1000) - start_time
            )
        
        local_errors = []
        local_warnings = []
        constraints = []
        
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
                self.constraints_created += 1
                constraints.append(constraint_name)
            except Exception as e:
                error_str = str(e).lower()
                if "already exists" not in error_str and "constraint already exists" not in error_str:
                    local_errors.append(CompileError(
                        code="CONSTRAINT_FAILED",
                        message=f"Failed to create constraint for {prop['name']}: {str(e)}",
                        field=prop['name']
                    ))
        
        interface_ids = obj_type.implemented_interfaces or []
        for interface_id in interface_ids:
            iface_result = await self.db.execute(
                select(OntologyInterface).where(
                    OntologyInterface.id == UUID(interface_id) if isinstance(interface_id, str) else interface_id,
                    OntologyInterface.tenant_id == self.tenant_id
                )
            )
            iface = iface_result.scalar_one_or_none()
            
            if iface:
                validation_result = await self._validate_interface_implementation(obj_type, iface)
                if validation_result["missing_properties"]:
                    local_errors.append(CompileError(
                        code="INTERFACE_NOT_IMPLEMENTED",
                        message=f"Object Type '{obj_type.name}' missing required properties for Interface '{iface.name}': {validation_result['missing_properties']}",
                        field="properties"
                    ))
        
        if local_errors:
            obj_type.compile_status = "error"
            obj_type.compile_errors = [e.model_dump() for e in local_errors]
        else:
            obj_type.compile_status = "compiled"
            obj_type.compiled_at = datetime.utcnow()
            obj_type.compile_errors = []
        
        await self.db.flush()
        
        return CompileResult(
            status="compiled" if not local_errors else "has_errors",
            errors=local_errors,
            warnings=local_warnings,
            neo4j_constraints_created=len(constraints),
            duration_ms=int(time.time() * 1000) - start_time
        )
    
    async def _validate_interface_implementation(
        self,
        obj_type: OntologyObjectType,
        iface: OntologyInterface
    ) -> Dict[str, Any]:
        """Validate that an Object Type properly implements an Interface"""
        obj_props = {p["name"] for p in obj_type.properties}
        required_prop_names = {p["name"] for p in iface.required_properties if p.get("required", True)}
        
        missing_properties = list(required_prop_names - obj_props)
        
        link_type_result = await self.db.execute(
            select(OntologyLinkType).where(
                OntologyLinkType.tenant_id == self.tenant_id,
                OntologyLinkType.source_object_type_id == obj_type.id
            )
        )
        link_types = link_type_result.scalars().all()
        link_names = {lt.name for lt in link_types}
        
        required_link_names = {l["name"] for l in iface.required_links}
        missing_links = list(required_link_names - link_names)
        
        return {
            "missing_properties": missing_properties,
            "missing_links": missing_links,
            "passed": len(missing_properties) == 0 and len(missing_links) == 0
        }
    
    async def generate_graphql_schema(self) -> str:
        """Generate GraphQL schema from Ontology definitions"""
        result = await self.db.execute(
            select(OntologyObjectType).where(
                OntologyObjectType.tenant_id == self.tenant_id,
                OntologyObjectType.status == "active",
                OntologyObjectType.compile_status == "compiled"
            )
        )
        object_types = result.scalars().all()
        
        schema_lines = [
            '"""Ontology GraphQL Schema - Auto-generated"""',
            "scalar JSON",
            ""
        ]
        
        for ot in object_types:
            schema_lines.append(f"type {ot.name} {{")
            schema_lines.append(f"  id: ID!")
            schema_lines.append(f"  objectKey: String!")
            
            for prop in ot.properties:
                prop_type = self._map_property_type(prop.get("type", "string"))
                required_marker = "!" if prop.get("required", False) else ""
                schema_lines.append(f"  {prop['name']}: {prop_type}{required_marker}")
            
            schema_lines.append(f"  createdAt: DateTime!")
            schema_lines.append(f"  updatedAt: DateTime!")
            schema_lines.append("}")
            schema_lines.append("")
        
        result = await self.db.execute(
            select(OntologyLinkType).where(
                OntologyLinkType.tenant_id == self.tenant_id,
                OntologyLinkType.status == "active"
            )
        )
        link_types = result.scalars().all()
        
        for lt in link_types:
            source_result = await self.db.execute(
                select(OntologyObjectType.name).where(
                    OntologyObjectType.id == lt.source_object_type_id
                )
            )
            target_result = await self.db.execute(
                select(OntologyObjectType.name).where(
                    OntologyObjectType.id == lt.target_object_type_id
                )
            )
            source_name = source_result.scalar_one_or_none() or "Unknown"
            target_name = target_result.scalar_one_or_none() or "Unknown"
            
            cardinality = lt.cardinality
            if cardinality == "ONE_TO_ONE":
                reverse_target = f"{target_name}! @relationship(type: \"{lt.name}\", direction: IN)"
            elif cardinality == "ONE_TO_MANY":
                reverse_target = f"[{target_name}!]! @relationship(type: \"{lt.name}\", direction: IN)"
            elif cardinality == "MANY_TO_ONE":
                reverse_target = f"{target_name}! @relationship(type: \"{lt.name}\", direction: IN)"
            else:
                reverse_target = f"[{target_name}!]! @relationship(type: \"{lt.name}\", direction: IN)"
            
            schema_lines.append(f"type {source_name} {{")
            schema_lines.append(f"  {lt.name}: {reverse_target}")
            schema_lines.append("}")
            schema_lines.append("")
        
        return "\n".join(schema_lines)
    
    def _map_property_type(self, prop_type: str) -> str:
        """Map Ontology property type to GraphQL type"""
        type_mapping = {
            "string": "String",
            "int": "Int",
            "float": "Float",
            "date": "DateTime",
            "boolean": "Boolean",
            "json": "JSON"
        }
        return type_mapping.get(prop_type, "String")


async def compile_ontology(
    db: AsyncSession,
    tenant_id: UUID,
    executed_by: Optional[UUID] = None
) -> CompileResult:
    """Public API to trigger full Ontology compilation"""
    compiler = OntologyCompiler(db, tenant_id)
    return await compiler.full_compile(executed_by)


async def compile_object_type(
    db: AsyncSession,
    tenant_id: UUID,
    object_type_id: UUID,
    executed_by: Optional[UUID] = None
) -> CompileResult:
    """Public API to trigger single Object Type compilation"""
    compiler = OntologyCompiler(db, tenant_id)
    return await compiler.incremental_compile(object_type_id, executed_by)