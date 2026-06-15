from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
import logging
import math

from app.services.database import get_db
from app.models.ontology_models import OntologyInterface, OntologyObjectType
from app.models.ontology_schemas import (
    InterfaceCreate, InterfaceUpdate, InterfaceResponse, InterfaceListResponse,
    InterfaceValidationResult, ImplementationValidation,
    PropertyDef, InterfaceLinkRequirement
)
from app.routers.auth import get_current_user, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ontology - Interfaces"])


async def _get_tenant_id(current_user: UserResponse) -> UUID:
    return UUID(current_user.tenant_id)


@router.post("", response_model=InterfaceResponse, status_code=status.HTTP_201_CREATED)
async def create_interface(
    interface_data: InterfaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new Interface"""
    tenant_id = await _get_tenant_id(current_user)
    
    existing = await db.execute(
        select(OntologyInterface).where(
            OntologyInterface.tenant_id == tenant_id,
            OntologyInterface.name == interface_data.name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Interface '{interface_data.name}' already exists")
    
    required_properties = [p.model_dump() for p in interface_data.required_properties]
    required_links = [l.model_dump() for l in interface_data.required_links]
    
    interface = OntologyInterface(
        tenant_id=tenant_id,
        name=interface_data.name,
        display_name=interface_data.display_name,
        description=interface_data.description,
        required_properties=required_properties,
        required_links=required_links,
        status="active",
        created_by=UUID(current_user.id) if current_user.id else None
    )
    
    db.add(interface)
    await db.flush()
    await db.refresh(interface)
    
    return InterfaceResponse(
        id=interface.id,
        tenant_id=interface.tenant_id,
        name=interface.name,
        display_name=interface.display_name,
        description=interface.description,
        required_properties=[PropertyDef(**p) for p in interface.required_properties],
        required_links=[InterfaceLinkRequirement(**l) for l in interface.required_links],
        status=interface.status,
        created_by=interface.created_by,
        created_at=interface.created_at,
        updated_at=interface.updated_at
    )


@router.get("", response_model=InterfaceListResponse)
async def list_interfaces(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """List all Interfaces"""
    tenant_id = await _get_tenant_id(current_user)
    
    query = select(OntologyInterface).where(OntologyInterface.tenant_id == tenant_id)
    
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    query = query.order_by(OntologyInterface.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    interfaces = result.scalars().all()
    
    items = []
    for iface in interfaces:
        items.append(InterfaceResponse(
            id=iface.id,
            tenant_id=iface.tenant_id,
            name=iface.name,
            display_name=iface.display_name,
            description=iface.description,
            required_properties=[PropertyDef(**p) for p in iface.required_properties],
            required_links=[InterfaceLinkRequirement(**l) for l in iface.required_links],
            status=iface.status,
            created_by=iface.created_by,
            created_at=iface.created_at,
            updated_at=iface.updated_at
        ))
    
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return InterfaceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.get("/{interface_id}", response_model=InterfaceResponse)
async def get_interface(
    interface_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a single Interface"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyInterface).where(
            OntologyInterface.id == interface_id,
            OntologyInterface.tenant_id == tenant_id
        )
    )
    iface = result.scalar_one_or_none()
    
    if not iface:
        raise HTTPException(status_code=404, detail="Interface not found")
    
    return InterfaceResponse(
        id=iface.id,
        tenant_id=iface.tenant_id,
        name=iface.name,
        display_name=iface.display_name,
        description=iface.description,
        required_properties=[PropertyDef(**p) for p in iface.required_properties],
        required_links=[InterfaceLinkRequirement(**l) for l in iface.required_links],
        status=iface.status,
        created_by=iface.created_by,
        created_at=iface.created_at,
        updated_at=iface.updated_at
    )


@router.put("/{interface_id}", response_model=InterfaceResponse)
async def update_interface(
    interface_id: UUID,
    update_data: InterfaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Update an Interface"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyInterface).where(
            OntologyInterface.id == interface_id,
            OntologyInterface.tenant_id == tenant_id
        )
    )
    iface = result.scalar_one_or_none()
    
    if not iface:
        raise HTTPException(status_code=404, detail="Interface not found")
    
    if update_data.display_name is not None:
        iface.display_name = update_data.display_name
    if update_data.description is not None:
        iface.description = update_data.description
    if update_data.required_properties is not None:
        iface.required_properties = [p.model_dump() for p in update_data.required_properties]
    if update_data.required_links is not None:
        iface.required_links = [l.model_dump() for l in update_data.required_links]
    if update_data.status is not None:
        iface.status = update_data.status
    
    await db.flush()
    await db.refresh(iface)
    
    return InterfaceResponse(
        id=iface.id,
        tenant_id=iface.tenant_id,
        name=iface.name,
        display_name=iface.display_name,
        description=iface.description,
        required_properties=[PropertyDef(**p) for p in iface.required_properties],
        required_links=[InterfaceLinkRequirement(**l) for l in iface.required_links],
        status=iface.status,
        created_by=iface.created_by,
        created_at=iface.created_at,
        updated_at=iface.updated_at
    )


@router.delete("/{interface_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interface(
    interface_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Archive an Interface"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyInterface).where(
            OntologyInterface.id == interface_id,
            OntologyInterface.tenant_id == tenant_id
        )
    )
    iface = result.scalar_one_or_none()
    
    if not iface:
        raise HTTPException(status_code=404, detail="Interface not found")
    
    iface.status = "archived"
    await db.flush()


@router.get("/{interface_id}/validate", response_model=InterfaceValidationResult)
async def validate_interface(
    interface_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Validate which Object Types implement this Interface correctly"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyInterface).where(
            OntologyInterface.id == interface_id,
            OntologyInterface.tenant_id == tenant_id
        )
    )
    iface = result.scalar_one_or_none()
    
    if not iface:
        raise HTTPException(status_code=404, detail="Interface not found")
    
    required_prop_names = {p["name"] for p in iface.required_properties if p.get("required", True)}
    required_link_names = {l["name"] for l in iface.required_links}
    
    query = select(OntologyObjectType).where(
        OntologyObjectType.tenant_id == tenant_id,
        OntologyObjectType.status == "active"
    )
    result = await db.execute(query)
    all_object_types = result.scalars().all()
    
    implementing_types = [
        ot for ot in all_object_types
        if str(interface_id) in (ot.implemented_interfaces or [])
    ]
    
    total = len(implementing_types)
    passed_count = 0
    failed_count = 0
    details = []
    
    for ot in implementing_types:
        ot_props = {p["name"] for p in ot.properties}
        missing_props = required_prop_names - ot_props
        
        missing_links = []
        for req_link in iface.required_links:
            link_exists = any(
                lt.name == req_link["name"] and lt.source_object_type_id == ot.id
                for lt in await db.execute(select(OntologyLinkType).where(OntologyLinkType.tenant_id == tenant_id))
            )
            if not link_exists:
                missing_links.append(req_link["name"])
        
        is_passed = len(missing_props) == 0 and len(missing_links) == 0
        
        if is_passed:
            passed_count += 1
        else:
            failed_count += 1
        
        details.append(ImplementationValidation(
            object_type_id=ot.id,
            object_type_name=ot.name,
            passed=is_passed,
            missing_properties=list(missing_props),
            missing_links=list(missing_links)
        ))
    
    return InterfaceValidationResult(
        interface_id=interface_id,
        total_implementations=total,
        passed=passed_count,
        failed=failed_count,
        details=details
    )


from app.models.ontology_models import OntologyLinkType