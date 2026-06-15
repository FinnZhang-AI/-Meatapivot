"""Repository layer for Ontology data access.

P0-ARCH-03: Router/Service/Repository three-layer separation.
All direct database queries live here.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
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

    async def count_object_types(self, tenant_id: UUID, status: Optional[str] = None) -> int:
        query = select(func.count()).select_from(OntologyObjectType).where(
            OntologyObjectType.tenant_id == tenant_id,
        )
        if status:
            query = query.where(OntologyObjectType.status == status)
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def list_object_types_paginated(
        self,
        tenant_id: UUID,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[OntologyObjectType]:
        query = select(OntologyObjectType).where(
            OntologyObjectType.tenant_id == tenant_id,
        )
        if status:
            query = query.where(OntologyObjectType.status == status)
        query = query.order_by(OntologyObjectType.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_object_type_names(self, type_ids: List[UUID]) -> Dict[UUID, str]:
        if not type_ids:
            return {}
        result = await self.db.execute(
            select(OntologyObjectType.id, OntologyObjectType.name).where(
                OntologyObjectType.id.in_(type_ids)
            )
        )
        return {row[0]: row[1] for row in result.all()}
    
    async def create_object_type(self, obj_type: OntologyObjectType) -> OntologyObjectType:
        self.db.add(obj_type)
        await self.db.flush()
        await self.db.refresh(obj_type)
        return obj_type

    async def object_type_name_exists(self, tenant_id: UUID, name: str) -> bool:
        result = await self.db.execute(
            select(OntologyObjectType.id).where(
                OntologyObjectType.tenant_id == tenant_id,
                OntologyObjectType.name == name,
            )
        )
        return result.scalar_one_or_none() is not None
    
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
    # OntologyObject (instance)
    # ------------------------------------------------------------------
    
    async def get_object(self, tenant_id: UUID, object_id: UUID) -> Optional[OntologyObject]:
        result = await self.db.execute(
            select(OntologyObject).where(
                OntologyObject.tenant_id == tenant_id,
                OntologyObject.id == object_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def object_key_exists(
        self, tenant_id: UUID, object_type_id: UUID, object_key: str
    ) -> bool:
        result = await self.db.execute(
            select(OntologyObject.id).where(
                OntologyObject.tenant_id == tenant_id,
                OntologyObject.object_type_id == object_type_id,
                OntologyObject.object_key == object_key,
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def create_object(self, obj: OntologyObject) -> OntologyObject:
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj
    
    async def list_objects_by_type(
        self, tenant_id: UUID, object_type_id: UUID
    ) -> List[OntologyObject]:
        result = await self.db.execute(
            select(OntologyObject).where(
                OntologyObject.tenant_id == tenant_id,
                OntologyObject.object_type_id == object_type_id,
                OntologyObject.status != "archived",
            ).order_by(OntologyObject.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def update_object(
        self,
        tenant_id: UUID,
        object_id: UUID,
        object_key: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> Optional[OntologyObject]:
        obj = await self.get_object(tenant_id, object_id)
        if not obj:
            return None
        if object_key is not None:
            obj.object_key = object_key
        if properties is not None:
            obj.properties = properties
        if status is not None:
            obj.status = status
        await self.db.flush()
        await self.db.refresh(obj)
        return obj
    
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

    async def count_link_types(self, tenant_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(OntologyLinkType).where(
                OntologyLinkType.tenant_id == tenant_id,
            )
        )
        return result.scalar() or 0

    async def list_link_types_paginated(
        self,
        tenant_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[OntologyLinkType]:
        result = await self.db.execute(
            select(OntologyLinkType)
            .where(OntologyLinkType.tenant_id == tenant_id)
            .order_by(OntologyLinkType.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def create_link_type(self, link_type: OntologyLinkType) -> OntologyLinkType:
        self.db.add(link_type)
        await self.db.flush()
        await self.db.refresh(link_type)
        return link_type
    
    # ------------------------------------------------------------------
    # OntologyLink (instance)
    # ------------------------------------------------------------------
    
    async def get_link(self, tenant_id: UUID, link_id: UUID) -> Optional[OntologyLink]:
        result = await self.db.execute(
            select(OntologyLink).where(
                OntologyLink.tenant_id == tenant_id,
                OntologyLink.id == link_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def delete_link(self, tenant_id: UUID, link_id: UUID) -> bool:
        link = await self.get_link(tenant_id, link_id)
        if not link:
            return False
        await self.db.delete(link)
        await self.db.flush()
        return True
    
    async def list_object_links(self, tenant_id: UUID, object_id: UUID) -> List[OntologyLink]:
        result = await self.db.execute(
            select(OntologyLink).where(
                OntologyLink.tenant_id == tenant_id,
                (OntologyLink.source_object_id == object_id) | (OntologyLink.target_object_id == object_id),
            )
        )
        return list(result.scalars().all())
    
    async def get_link_type_names(self, link_type_ids: List[UUID]) -> Dict[UUID, str]:
        if not link_type_ids:
            return {}
        result = await self.db.execute(
            select(OntologyLinkType.id, OntologyLinkType.name).where(
                OntologyLinkType.id.in_(link_type_ids)
            )
        )
        return {row[0]: row[1] for row in result.all()}
    
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

    async def count_interfaces(self, tenant_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(OntologyInterface).where(
                OntologyInterface.tenant_id == tenant_id,
            )
        )
        return result.scalar() or 0

    async def list_interfaces_paginated(
        self,
        tenant_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[OntologyInterface]:
        result = await self.db.execute(
            select(OntologyInterface)
            .where(OntologyInterface.tenant_id == tenant_id)
            .order_by(OntologyInterface.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_interface(self, interface: OntologyInterface) -> OntologyInterface:
        self.db.add(interface)
        await self.db.flush()
        await self.db.refresh(interface)
        return interface

    async def update_interface(
        self,
        tenant_id: UUID,
        interface_id: UUID,
        **updates,
    ) -> Optional[OntologyInterface]:
        iface = await self.get_interface(tenant_id, interface_id)
        if not iface:
            return None
        for key, value in updates.items():
            if hasattr(iface, key):
                setattr(iface, key, value)
        await self.db.flush()
        await self.db.refresh(iface)
        return iface

    async def delete_interface(self, tenant_id: UUID, interface_id: UUID) -> bool:
        iface = await self.get_interface(tenant_id, interface_id)
        if not iface:
            return False
        await self.db.delete(iface)
        await self.db.flush()
        return True

    # ------------------------------------------------------------------
    # ActionType
    # ------------------------------------------------------------------

    async def get_action_type(
        self,
        tenant_id: UUID,
        action_type_id: UUID,
    ) -> Optional[OntologyActionType]:
        result = await self.db.execute(
            select(OntologyActionType).where(
                OntologyActionType.tenant_id == tenant_id,
                OntologyActionType.id == action_type_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_action_types(self, tenant_id: UUID) -> List[OntologyActionType]:
        result = await self.db.execute(
            select(OntologyActionType).where(
                OntologyActionType.tenant_id == tenant_id,
            )
        )
        return list(result.scalars().all())

    async def count_action_types(self, tenant_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(OntologyActionType).where(
                OntologyActionType.tenant_id == tenant_id,
            )
        )
        return result.scalar() or 0

    async def list_action_types_paginated(
        self,
        tenant_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[OntologyActionType]:
        result = await self.db.execute(
            select(OntologyActionType)
            .where(OntologyActionType.tenant_id == tenant_id)
            .order_by(OntologyActionType.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_action_type(self, action_type: OntologyActionType) -> OntologyActionType:
        self.db.add(action_type)
        await self.db.flush()
        await self.db.refresh(action_type)
        return action_type

    async def update_action_type(
        self,
        tenant_id: UUID,
        action_type_id: UUID,
        **updates,
    ) -> Optional[OntologyActionType]:
        at = await self.get_action_type(tenant_id, action_type_id)
        if not at:
            return None
        for key, value in updates.items():
            if hasattr(at, key):
                setattr(at, key, value)
        await self.db.flush()
        await self.db.refresh(at)
        return at

    async def delete_action_type(self, tenant_id: UUID, action_type_id: UUID) -> bool:
        at = await self.get_action_type(tenant_id, action_type_id)
        if not at:
            return False
        await self.db.delete(at)
        await self.db.flush()
        return True

    # ------------------------------------------------------------------
    # Function
    # ------------------------------------------------------------------

    async def get_function(
        self,
        tenant_id: UUID,
        function_id: UUID,
    ) -> Optional[OntologyFunction]:
        result = await self.db.execute(
            select(OntologyFunction).where(
                OntologyFunction.tenant_id == tenant_id,
                OntologyFunction.id == function_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_functions(self, tenant_id: UUID) -> List[OntologyFunction]:
        result = await self.db.execute(
            select(OntologyFunction).where(
                OntologyFunction.tenant_id == tenant_id,
            )
        )
        return list(result.scalars().all())

    async def count_functions(self, tenant_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(OntologyFunction).where(
                OntologyFunction.tenant_id == tenant_id,
            )
        )
        return result.scalar() or 0

    async def list_functions_paginated(
        self,
        tenant_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[OntologyFunction]:
        result = await self.db.execute(
            select(OntologyFunction)
            .where(OntologyFunction.tenant_id == tenant_id)
            .order_by(OntologyFunction.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_function(self, function: OntologyFunction) -> OntologyFunction:
        self.db.add(function)
        await self.db.flush()
        await self.db.refresh(function)
        return function

    async def update_function(
        self,
        tenant_id: UUID,
        function_id: UUID,
        **updates,
    ) -> Optional[OntologyFunction]:
        fn = await self.get_function(tenant_id, function_id)
        if not fn:
            return None
        for key, value in updates.items():
            if hasattr(fn, key):
                setattr(fn, key, value)
        await self.db.flush()
        await self.db.refresh(fn)
        return fn

    async def delete_function(self, tenant_id: UUID, function_id: UUID) -> bool:
        fn = await self.get_function(tenant_id, function_id)
        if not fn:
            return False
        await self.db.delete(fn)
        await self.db.flush()
        return True

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
