"""GraphQL schema emitter for Ontology compiler.

P1-01: Generates GraphQL schema strings from Ontology definitions.
"""

import logging
from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ontology_models import OntologyObjectType, OntologyLinkType

logger = logging.getLogger(__name__)


class SchemaEmitter:
    """Emits GraphQL schema from Ontology definitions."""

    TYPE_MAPPING = {
        "string": "String",
        "int": "Int",
        "integer": "Int",
        "float": "Float",
        "date": "DateTime",
        "datetime": "DateTime",
        "boolean": "Boolean",
        "json": "JSON",
        "text": "String",
        "uuid": "ID",
        "enum": "String",
    }

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    def _map_property_type(self, prop_type: str) -> str:
        """Map Ontology property type to GraphQL type."""
        return self.TYPE_MAPPING.get(prop_type, "String")

    def emit_object_type(self, obj_type: OntologyObjectType) -> List[str]:
        """Emit GraphQL type definition lines."""
        lines = []
        lines.append(f"type {obj_type.name} {{")
        lines.append("  id: ID!")
        lines.append("  objectKey: String!")

        if obj_type.properties:
            for prop in obj_type.properties:
                if not isinstance(prop, dict):
                    continue
                prop_type = prop.get("type", "string")
                graphql_type = self._map_property_type(prop_type)
                required_marker = "!" if prop.get("required", False) else ""
                lines.append(f"  {prop['name']}: {graphql_type}{required_marker}")

        lines.append("  createdAt: DateTime!")
        lines.append("  updatedAt: DateTime!")
        lines.append("}")
        lines.append("")
        return lines

    def emit_link_type(self, link_type: OntologyLinkType, type_names: dict) -> List[str]:
        """Emit GraphQL relationship type definition lines."""
        lines = []
        source_name = type_names.get(link_type.source_object_type_id, "Unknown")
        target_name = type_names.get(link_type.target_object_type_id, "Unknown")

        cardinality = link_type.cardinality
        if cardinality == "ONE_TO_ONE":
            reverse_target = f"{target_name}! @relationship(type: \"{link_type.name}\", direction: IN)"
        elif cardinality == "ONE_TO_MANY":
            reverse_target = f"[{target_name}!]! @relationship(type: \"{link_type.name}\", direction: IN)"
        elif cardinality == "MANY_TO_ONE":
            reverse_target = f"{target_name}! @relationship(type: \"{link_type.name}\", direction: IN)"
        else:
            reverse_target = f"[{target_name}!]! @relationship(type: \"{link_type.name}\", direction: IN)"

        lines.append(f"type {source_name} {{")
        lines.append(f"  {link_type.name}: {reverse_target}")
        lines.append("}")
        lines.append("")
        return lines

    async def generate_schema(self) -> str:
        """Generate full GraphQL schema from all ontology definitions."""
        schema_lines = [
            '"""Ontology GraphQL Schema - Auto-generated"""',
            "scalar JSON",
            "",
        ]

        object_types_result = await self.db.execute(
            select(OntologyObjectType).where(
                OntologyObjectType.tenant_id == self.tenant_id,
                OntologyObjectType.status == "active",
                OntologyObjectType.compile_status == "compiled",
            )
        )
        object_types = list(object_types_result.scalars().all())

        for ot in object_types:
            schema_lines.extend(self.emit_object_type(ot))

        link_types_result = await self.db.execute(
            select(OntologyLinkType).where(
                OntologyLinkType.tenant_id == self.tenant_id,
                OntologyLinkType.status == "active",
            )
        )
        link_types = list(link_types_result.scalars().all())

        type_names = {
            ot.id: ot.name for ot in object_types
        }
        type_names.update({
            lt.source_object_type_id: None,
            lt.target_object_type_id: None,
        })

        for lt in link_types:
            schema_lines.extend(self.emit_link_type(lt, type_names))

        return "\n".join(schema_lines)