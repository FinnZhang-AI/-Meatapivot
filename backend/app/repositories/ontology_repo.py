"""Repository layer for Ontology data access.

P0-ARCH-03: Router/Service/Repository three-layer separation.
All direct database queries live here.
"""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ontology_models import (
    OntologyObjectType,
    OntologyLinkType,
    OntologyInterface,
    OntologyActionType,
    OntologyFunction,
    OntologyCompileLog,
    OntologyCurrentVersion,
    OntologyObject,
    OntologyLink,
)

logger = logging.getLogger(__name__)


class OntologyRepository:
    """Repository for ontology CRUD operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ------------------------------------------------------------------
    # ObjectType
    # ------------------------------------------------------------------
    
    async def get_object_type(
        self,
        tenant_id: UUID,
        object_type_id: UUID,
    ) -> Optional[OntologyObjectType]:
        result = await self.db.execute(
            select(OntologyObjectType).where(
                OntologyObjectType.tenant_id == tenant_id,
                OntologyObjectType.id == object_type_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def list_object_types(
        self,
        tenant_id: UUID,
        status: Optional[str] = None,
    ) -> List[OntologyObjectType]:
        query = select(OntologyObjectType).where(
            OntologyObjectType.tenant_id == tenant_id,
        )
        if status:
            query = query.where(OntologyObjectType.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def create_object_type(self, obj_type: OntologyObjectType) -> OntologyObjectType:
        self.db.add(obj_type)
        await self.db.flush()
        await self.db.refresh(obj_type)
        return obj_type
    
    async def update_object_type(
        self,
        tenant_id: UUID,
        object_type_id: UUID,
        **updates,
    ) -> Optional[OntologyObjectType]:
        obj = await self.get_object_type(tenant_id, object_type_id)
        if not obj:
            return None
        for key, value in updates.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj
    
    async def delete_object_type(self, tenant_id: UUID, object_type_id: UUID) -> bool:
        obj = await self.get_object_type(tenant_id, object_type_id)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.flush()
        return True
    
    # ------------------------------------------------------------------
    # LinkType
    # ------------------------------------------------------------------
    
    async def get_link_type(
        self,
        tenant_id: UUID,
        link_type_id: UUID,
    ) -> Optional[OntologyLinkType]:
        result = await self.db.execute(
            select(OntologyLinkType).where(
                OntologyLinkType.tenant_id == tenant_id,
                OntologyLinkType.id == link_type_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def list_link_types(self, tenant_id: UUID) -> List[OntologyLinkType]:
        result = await self.db.execute(
            select(OntologyLinkType).where(
                OntologyLinkType.tenant_id == tenant_id,
            )
        )
        return list(result.scalars().all())
    
    async def create_link_type(self, link_type: OntologyLinkType) -> OntologyLinkType:
        self.db.add(link_type)
        await self.db.flush()
        await self.db.refresh(link_type)
        return link_type
    
    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------
    
    async def get_interface(
        self,
        tenant_id: UUID,
        interface_id: UUID,
    ) -> Optional[OntologyInterface]:
        result = await self.db.execute(
            select(OntologyInterface).where(
                OntologyInterface.tenant_id == tenant_id,
                OntologyInterface.id == interface_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def list_interfaces(self, tenant_id: UUID) -> List[OntologyInterface]:
        result = await self.db.execute(
            select(OntologyInterface).where(
                OntologyInterface.tenant_id == tenant_id,
            )
        )
        return list(result.scalars().all())
    
    # ------------------------------------------------------------------
    # Compile Log
    # ------------------------------------------------------------------
    
    async def get_compile_log(
        self,
        tenant_id: UUID,
        log_id: UUID,
    ) -> Optional[OntologyCompileLog]:
        result = await self.db.execute(
            select(OntologyCompileLog).where(
                OntologyCompileLog.tenant_id == tenant_id,
                OntologyCompileLog.id == log_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def get_latest_compile_log(
        self,
        tenant_id: UUID,
        status: Optional[str] = None,
    ) -> Optional[OntologyCompileLog]:
        query = select(OntologyCompileLog).where(
            OntologyCompileLog.tenant_id == tenant_id,
        )
        if status:
            query = query.where(OntologyCompileLog.status == status)
        query = query.order_by(OntologyCompileLog.completed_at.desc()).limit(1)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_compile_logs(
        self,
        tenant_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[OntologyCompileLog]:
        result = await self.db.execute(
            select(OntologyCompileLog).where(
                OntologyCompileLog.tenant_id == tenant_id,
            )
            .order_by(OntologyCompileLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    # ------------------------------------------------------------------
    # Current Version
    # ------------------------------------------------------------------
    
    async def get_current_version(self, tenant_id: UUID) -> Optional[OntologyCurrentVersion]:
        result = await self.db.execute(
            select(OntologyCurrentVersion).where(
                OntologyCurrentVersion.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def set_current_version(
        self,
        tenant_id: UUID,
        version: str,
        log_id: UUID,
    ) -> OntologyCurrentVersion:
        current = await self.get_current_version(tenant_id)
        if current:
            current.version = version
            current.log_id = log_id
        else:
            current = OntologyCurrentVersion(
                tenant_id=tenant_id,
                version=version,
                log_id=log_id,
            )
            self.db.add(current)
        await self.db.flush()
        await self.db.refresh(current)
        return current
    
    # ------------------------------------------------------------------
    # Dashboard Stats
    # ------------------------------------------------------------------
    
    async def get_dashboard_counts(self, tenant_id: UUID) -> dict:
        """Get counts for dashboard."""
        obj_type_count = await self.db.scalar(
            select(func.count()).select_from(OntologyObjectType).where(
                OntologyObjectType.tenant_id == tenant_id,
            )
        )
        link_type_count = await self.db.scalar(
            select(func.count()).select_from(OntologyLinkType).where(
                OntologyLinkType.tenant_id == tenant_id,
            )
        )
        interface_count = await self.db.scalar(
            select(func.count()).select_from(OntologyInterface).where(
                OntologyInterface.tenant_id == tenant_id,
            )
        )
        action_type_count = await self.db.scalar(
            select(func.count()).select_from(OntologyActionType).where(
                OntologyActionType.tenant_id == tenant_id,
            )
        )
        function_count = await self.db.scalar(
            select(func.count()).select_from(OntologyFunction).where(
                OntologyFunction.tenant_id == tenant_id,
            )
        )
        object_instance_count = await self.db.scalar(
            select(func.count()).select_from(OntologyObject).where(
                OntologyObject.tenant_id == tenant_id,
            )
        )
        
        return {
            "object_type_count": obj_type_count or 0,
            "link_type_count": link_type_count or 0,
            "interface_count": interface_count or 0,
            "action_type_count": action_type_count or 0,
            "function_count": function_count or 0,
            "object_instance_count": object_instance_count or 0,
        }
