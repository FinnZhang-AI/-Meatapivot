"""Ontology CRUD API Router"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ontology_models import (
    OntologyObjectType,
    OntologyLinkType,
    OntologyInterface,
    OntologyActionType,
    OntologyFunction,
    OntologyFunctionVersion,
    OntologyObject,
    OntologyLink,
    ActionExecutionLog,
)
from app.models.ontology_schemas import (
    ObjectTypeCreate,
    ObjectTypeUpdate,
    ObjectTypeResponse,
    ObjectTypeListResponse,
    CompileResult,
    OntologyObjectCreate,
    OntologyObjectUpdate,
    OntologyObjectResponse,
    LinkTypeCreate,
    LinkTypeUpdate,
    LinkTypeResponse,
    LinkTypeListResponse,
    OntologyLinkCreate,
    OntologyLinkResponse,
    SubgraphResponse,
    GraphNode,
    GraphEdge,
    GraphMetadata,
    InterfaceCreate,
    InterfaceUpdate,
    InterfaceResponse,
    InterfaceListResponse,
    ActionTypeCreate,
    ActionTypeUpdate,
    ActionTypeResponse,
    ActionTypeListResponse,
    ActionExecuteRequest,
    ActionExecuteResponse,
    FunctionCreate,
    FunctionUpdate,
    FunctionResponse,
    FunctionListResponse,
    OntologySearchRequest,
    OntologySearchResponse,
    DashboardStats,
    RecentAction,
    ImportError,
    OntologyImportRequest,
    OntologyImportResult,
    RollbackRequest,
    ValidationResponse,
    CompileLogResponse,
    CompileLogListResponse,
    DAGCycleResponse,
    DAGImpactResponse,
)
from app.services.database import get_db
import time

from app.services.neo4j_client import neo4j_client
from app.services.ontology_compiler import OntologyCompiler
from app.services.ontology_service import OntologyService
from app.services.ontology_dag import OntologyDAG
from app.services.semantic_search import SemanticSearchService
from app.services.action_executor import ActionExecutor
from app.services.compiler.compiler import compile_ontology, compile_object_type as compile_single_object_type
from app.repositories.ontology_repo import OntologyRepository
from app.core.metrics import (
    COMPILE_FULL_DURATION,
    COMPILE_INCREMENTAL_DURATION,
    VALIDATION_DURATION,
    DAG_DETECT_DURATION,
    FUNCTION_EXEC_DURATION,
    DAG_CYCLES_DETECTED,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ontology", tags=["Ontology"])


# Helper: build ObjectTypeResponse from ORM object
def _obj_type_resp(ot: OntologyObjectType) -> ObjectTypeResponse:
    return ObjectTypeResponse(
        id=ot.id,
        tenant_id=ot.tenant_id,
        name=ot.name,
        display_name=ot.display_name,
        description=ot.description,
        icon=ot.icon or "box",
        properties=ot.properties or [],
        implemented_interfaces=ot.implemented_interfaces or [],
        neo4j_label=ot.neo4j_label or ot.name,
        status=ot.status,
        version=ot.version or 1,
        compile_status=ot.compile_status or "pending",
        compile_errors=ot.compile_errors or [],
        created_by=ot.created_by,
        created_at=ot.created_at,
        updated_at=ot.updated_at,
    )


# Helper: build LinkTypeResponse from ORM object
def _link_type_resp(lt: OntologyLinkType, src_name: str = "", tgt_name: str = "") -> LinkTypeResponse:
    return LinkTypeResponse(
        id=lt.id,
        tenant_id=lt.tenant_id,
        name=lt.name,
        display_name=lt.display_name,
        description=lt.description,
        source_object_type_id=lt.source_object_type_id,
        source_object_type_name=src_name,
        target_object_type_id=lt.target_object_type_id,
        target_object_type_name=tgt_name,
        cardinality=lt.cardinality,
        neo4j_edge_type=lt.neo4j_edge_type or lt.name,
        neo4j_properties=lt.neo4j_properties or [],
        status=lt.status,
        version=lt.version or 1,
        created_at=lt.created_at,
        updated_at=lt.updated_at,
    )


# Helper: build ObjectResponse from ORM object
def _obj_resp(obj: OntologyObject, type_name: str = "") -> OntologyObjectResponse:
    return OntologyObjectResponse(
        id=obj.id,
        tenant_id=obj.tenant_id,
        object_type_id=obj.object_type_id,
        object_type_name=type_name,
        object_key=obj.object_key,
        properties=obj.properties or {},
        neo4j_node_id=obj.neo4j_node_id,
        status=obj.status,
        created_by=obj.created_by,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


# ---------------------------------------------------------------------------
# Object Types
# ---------------------------------------------------------------------------

@router.post("/object-types", response_model=ObjectTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_object_type(
    request: Request,
    data: ObjectTypeCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new Object Type."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)

    if await service.check_object_type_name_exists(data.name):
        raise HTTPException(status_code=409, detail="Object type name already exists")

    obj_data = {
        "name": data.name,
        "display_name": data.display_name or data.name,
        "description": data.description,
        "icon": data.icon or "box",
        "properties": [p.model_dump() for p in data.properties],
        "implemented_interfaces": list(data.implemented_interfaces) if data.implemented_interfaces else [],
        "neo4j_label": data.neo4j_label or data.name,
        "status": "draft",
    }
    created = await service.create_object_type(obj_data)
    return _obj_type_resp(created)


@router.get("/object-types", response_model=ObjectTypeListResponse)
async def list_object_types(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List Object Types with pagination."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    items, total = await service.list_object_types_paginated(
        status=status_filter,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    pages = (total + page_size - 1) // page_size
    return ObjectTypeListResponse(
        items=[_obj_type_resp(ot) for ot in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/object-types/{id}", response_model=ObjectTypeResponse)
async def get_object_type(
    request: Request,
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get Object Type by ID."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    ot = await service.get_object_type(id)
    if not ot:
        raise HTTPException(status_code=404, detail="Object type not found")
    return _obj_type_resp(ot)


@router.put("/object-types/{id}", response_model=ObjectTypeResponse)
async def update_object_type(
    request: Request,
    id: UUID,
    data: ObjectTypeUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update Object Type."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)

    updates = data.model_dump(exclude_unset=True)
    if "properties" in updates and updates["properties"] is not None:
        updates["properties"] = [p.model_dump() for p in updates["properties"]]
    if "implemented_interfaces" in updates and updates["implemented_interfaces"] is not None:
        updates["implemented_interfaces"] = list(updates["implemented_interfaces"])

    ot = await service.update_object_type(id, updates)
    if not ot:
        raise HTTPException(status_code=404, detail="Object type not found")
    return _obj_type_resp(ot)


@router.patch("/object-types/{id}", response_model=ObjectTypeResponse)
async def patch_object_type(
    request: Request,
    id: UUID,
    data: ObjectTypeUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partial update Object Type (incremental update)."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    if "properties" in update_data and update_data["properties"] is not None:
        update_data["properties"] = [p.model_dump() for p in update_data["properties"]]
    if "implemented_interfaces" in update_data and update_data["implemented_interfaces"] is not None:
        update_data["implemented_interfaces"] = list(update_data["implemented_interfaces"])

    ot = await service.update_object_type(id, update_data)
    if not ot:
        raise HTTPException(status_code=404, detail="Object type not found")
    return _obj_type_resp(ot)


@router.delete("/object-types/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_object_type(
    request: Request,
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete Object Type (archive)."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)

    # Archive via service (soft-delete pattern)
    ot = await service.update_object_type(id, {"status": "archived"})
    if not ot:
        raise HTTPException(status_code=404, detail="Object type not found")
    return None


@router.post("/object-types/{id}/compile", response_model=CompileResult)
async def compile_object_type_endpoint(
    id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Trigger incremental compilation for an Object Type.

    Uses new CompilationPipeline (Sprint 3).
    """
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    start = time.time()
    result = await compile_single_object_type(db, tenant_id, id)
    COMPILE_INCREMENTAL_DURATION.observe(time.time() - start)
    return result


@router.post("/object-types/{id}/objects", response_model=OntologyObjectResponse, status_code=status.HTTP_201_CREATED)
async def create_object_instance(
    id: UUID,
    data: OntologyObjectCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create an object instance and sync to Neo4j."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)

    obj_type = await service.get_object_type(id)
    if not obj_type:
        raise HTTPException(status_code=404, detail="Object type not found")

    if await service.check_object_key_exists(id, data.object_key):
        raise HTTPException(status_code=409, detail="Object key already exists for this type")

    obj = OntologyObject(
        tenant_id=tenant_id,
        object_type_id=id,
        object_key=data.object_key,
        properties=data.properties or {},
        status="active",
    )
    obj = await service.create_object(obj)

    label = obj_type.neo4j_label or obj_type.name
    props = {"object_id": str(obj.id), "object_key": obj.object_key, "tenant_id": str(tenant_id)}
    props.update({k: v for k, v in (obj.properties or {}).items() if v is not None})
    cypher = f"""
    CREATE (n:{label} $props)
    RETURN elementId(n) as neo4j_node_id
    """
    try:
        graph_result = await neo4j_client.execute_query(cypher, {"props": props})
        if graph_result:
            obj.neo4j_node_id = graph_result[0].get("neo4j_node_id")
            await db.flush()
    except Exception as e:
        logger.warning(f"Neo4j sync failed for object {obj.id}: {e}")

    await db.refresh(obj)
    return _obj_resp(obj, obj_type.name)


@router.get("/object-types/{id}/objects", response_model=List[OntologyObjectResponse])
async def list_objects_by_type(
    id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """List object instances of a given type."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    objs = await service.list_objects_by_type(id)
    type_ids = {o.object_type_id for o in objs}
    type_names = await service.get_object_type_names(list(type_ids))
    return [_obj_resp(o, type_names.get(o.object_type_id, "")) for o in objs]


@router.get("/objects/{object_id}", response_model=OntologyObjectResponse)
async def get_object(
    object_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get a single object instance by ID."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    obj = await service.get_object(object_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    type_names = await service.get_object_type_names([obj.object_type_id])
    type_name = type_names.get(obj.object_type_id, "")
    return _obj_resp(obj, type_name)


@router.put("/objects/{object_id}", response_model=OntologyObjectResponse)
async def update_object(
    object_id: UUID,
    data: OntologyObjectUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update an object instance (properties, key, status)."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    obj = await service.get_object(object_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")

    obj = await service.update_object(
        object_id,
        object_key=data.object_key,
        properties=data.properties,
        status=data.status,
    )

    if data.properties is not None and obj.neo4j_node_id:
        try:
            cypher = """
            MATCH (n)
            WHERE elementId(n) = $neo4j_node_id
            SET n += $props
            """
            props = {"object_id": str(obj.id), "object_key": obj.object_key, "tenant_id": str(tenant_id)}
            props.update({k: v for k, v in (obj.properties or {}).items() if v is not None})
            await neo4j_client.execute_query(cypher, {
                "neo4j_node_id": obj.neo4j_node_id,
                "props": props,
            })
        except Exception as e:
            logger.warning(f"Neo4j sync failed for object update {obj.id}: {e}")

    await db.refresh(obj)
    type_names = await service.get_object_type_names([obj.object_type_id])
    type_name = type_names.get(obj.object_type_id, "")
    return _obj_resp(obj, type_name)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    link_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Delete a link instance (hard delete from PG + Neo4j)."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    link = await service.get_link(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    if link.neo4j_rel_id:
        try:
            cypher = """
            MATCH ()-[r]->()
            WHERE elementId(r) = $rel_id
            DELETE r
            """
            await neo4j_client.execute_query(cypher, {"rel_id": link.neo4j_rel_id})
        except Exception as e:
            logger.warning(f"Neo4j delete failed for link {link.id}: {e}")

    await service.delete_link(link_id)
    return None


@router.get("/objects/{object_id}/links", response_model=list[OntologyLinkResponse])
async def get_object_links(
    object_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get all links connected to an object (as source or target)."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    links = await service.list_object_links(object_id)
    link_type_ids = {l.link_type_id for l in links}
    link_type_names = await service.get_link_type_names(list(link_type_ids))

    return [
        OntologyLinkResponse(
            id=l.id,
            tenant_id=l.tenant_id,
            link_type_id=l.link_type_id,
            link_type_name=link_type_names.get(l.link_type_id, ""),
            source_object_id=l.source_object_id,
            target_object_id=l.target_object_id,
            properties=l.properties or {},
            neo4j_rel_id=l.neo4j_rel_id,
            created_at=l.created_at,
        )
        for l in links
    ]


# ---------------------------------------------------------------------------
# Link Types
# ---------------------------------------------------------------------------

@router.post("/link-types", response_model=LinkTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_link_type(
    request: Request,
    data: LinkTypeCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new Link Type."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)

    # Validate source/target types exist
    for type_id, field in [(data.source_object_type_id, "source"), (data.target_object_type_id, "target")]:
        ot = await service.get_object_type(type_id)
        if not ot:
            raise HTTPException(status_code=404, detail=f"{field} object type not found")

    lt = OntologyLinkType(
        tenant_id=tenant_id,
        name=data.name,
        display_name=data.display_name or data.name,
        description=data.description,
        source_object_type_id=data.source_object_type_id,
        target_object_type_id=data.target_object_type_id,
        cardinality=data.cardinality,
        neo4j_edge_type=data.neo4j_edge_type or data.name,
        neo4j_properties=[p.model_dump() for p in data.properties] if data.properties else [],
        status="active",
    )
    db.add(lt)
    await db.flush()
    await db.refresh(lt)
    return _link_type_resp(lt)


@router.get("/link-types", response_model=LinkTypeListResponse)
async def list_link_types(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List Link Types."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    items, total = await service.list_link_types_paginated(
        limit=page_size,
        offset=(page - 1) * page_size,
    )

    type_ids = set()
    for lt in items:
        type_ids.add(lt.source_object_type_id)
        type_ids.add(lt.target_object_type_id)
    type_names = await service.get_object_type_names(list(type_ids))

    pages = (total + page_size - 1) // page_size
    return LinkTypeListResponse(
        items=[_link_type_resp(lt, type_names.get(lt.source_object_type_id, ""), type_names.get(lt.target_object_type_id, "")) for lt in items],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.get("/link-types/{id}", response_model=LinkTypeResponse)
async def get_link_type(
    request: Request,
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    lt = await service.get_link_type(id)
    if not lt:
        raise HTTPException(status_code=404, detail="Link type not found")
    return _link_type_resp(lt)


@router.put("/link-types/{id}", response_model=LinkTypeResponse)
async def update_link_type(
    request: Request,
    id: UUID,
    data: LinkTypeUpdate,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    lt = await service.get_link_type(id)
    if not lt:
        raise HTTPException(status_code=404, detail="Link type not found")
    if data.display_name is not None:
        lt.display_name = data.display_name
    if data.description is not None:
        lt.description = data.description
    if data.cardinality is not None:
        lt.cardinality = data.cardinality
    if data.properties is not None:
        lt.neo4j_properties = [p.model_dump() for p in data.properties]
    if data.status is not None:
        lt.status = data.status
    lt.version = (lt.version or 1) + 1
    await db.flush()
    await db.refresh(lt)
    return _link_type_resp(lt)


@router.delete("/link-types/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link_type(
    request: Request,
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    lt = await service.get_link_type(id)
    if not lt:
        raise HTTPException(status_code=404, detail="Link type not found")
    lt.status = "archived"
    await db.flush()
    return None


@router.post("/link-types/{id}/links", response_model=OntologyLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_link_instance(
    id: UUID,
    data: OntologyLinkCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a link instance between two objects."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)

    lt = await service.get_link_type(id)
    if not lt:
        raise HTTPException(status_code=404, detail="Link type not found")

    src_obj = await service.get_object(data.source_object_id)
    if not src_obj:
        raise HTTPException(status_code=404, detail="source object not found")
    tgt_obj = await service.get_object(data.target_object_id)
    if not tgt_obj:
        raise HTTPException(status_code=404, detail="target object not found")

    link = OntologyLink(
        tenant_id=tenant_id,
        link_type_id=id,
        source_object_id=data.source_object_id,
        target_object_id=data.target_object_id,
        properties=data.properties or {},
    )
    db.add(link)
    await db.flush()

    edge_type = lt.neo4j_edge_type or lt.name
    try:
        src_node_id = src_obj.neo4j_node_id
        tgt_node_id = tgt_obj.neo4j_node_id

        if src_node_id and tgt_node_id:
            cypher = f"""
            MATCH (a), (b)
            WHERE elementId(a) = $src AND elementId(b) = $tgt
            CREATE (a)-[r:{edge_type} $props]->(b)
            RETURN elementId(r) as neo4j_rel_id
            """
            graph_result = await neo4j_client.execute_query(cypher, {
                "src": src_node_id,
                "tgt": tgt_node_id,
                "props": {"link_id": str(link.id), **(link.properties or {})},
            })
            if graph_result:
                link.neo4j_rel_id = graph_result[0].get("neo4j_rel_id")
                await db.flush()
    except Exception as e:
        logger.warning(f"Neo4j sync failed for link {link.id}: {e}")

    await db.refresh(link)
    return OntologyLinkResponse(
        id=link.id,
        tenant_id=link.tenant_id,
        link_type_id=link.link_type_id,
        link_type_name=lt.name,
        source_object_id=link.source_object_id,
        target_object_id=link.target_object_id,
        properties=link.properties or {},
        neo4j_rel_id=link.neo4j_rel_id,
        created_at=link.created_at,
    )


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------

@router.post("/interfaces", response_model=InterfaceResponse, status_code=status.HTTP_201_CREATED)
async def create_interface(
    request: Request,
    data: InterfaceCreate,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    iface_data = {
        "name": data.name,
        "display_name": data.display_name or data.name,
        "description": data.description,
        "required_properties": [p.model_dump() for p in data.required_properties] if data.required_properties else [],
        "required_links": [l.model_dump() for l in data.required_links] if data.required_links else [],
        "status": "active",
    }
    iface = await service.create_interface(iface_data)
    return InterfaceResponse(
        id=iface.id,
        tenant_id=iface.tenant_id,
        name=iface.name,
        display_name=iface.display_name,
        description=iface.description,
        required_properties=iface.required_properties or [],
        required_links=iface.required_links or [],
        status=iface.status,
        created_at=iface.created_at,
        updated_at=iface.updated_at,
    )


@router.get("/interfaces", response_model=InterfaceListResponse)
async def list_interfaces(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    items, total = await service.list_interfaces_paginated(
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    pages = (total + page_size - 1) // page_size
    return InterfaceListResponse(
        items=[InterfaceResponse(
            id=i.id,
            tenant_id=i.tenant_id,
            name=i.name,
            display_name=i.display_name,
            description=i.description,
            required_properties=i.required_properties or [],
            required_links=i.required_links or [],
            status=i.status,
            created_at=i.created_at,
            updated_at=i.updated_at,
        ) for i in items],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.get("/interfaces/{id}", response_model=InterfaceResponse)
async def get_interface(
    request: Request,
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    iface = await service.get_interface(id)
    if not iface:
        raise HTTPException(status_code=404, detail="Interface not found")
    return InterfaceResponse(
        id=iface.id,
        tenant_id=iface.tenant_id,
        name=iface.name,
        display_name=iface.display_name,
        description=iface.description,
        required_properties=iface.required_properties or [],
        required_links=iface.required_links or [],
        status=iface.status,
        created_at=iface.created_at,
        updated_at=iface.updated_at,
    )


@router.put("/interfaces/{id}", response_model=InterfaceResponse)
async def update_interface(
    request: Request,
    id: UUID,
    data: InterfaceUpdate,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    updates = data.model_dump(exclude_unset=True)
    if "required_properties" in updates and updates["required_properties"] is not None:
        updates["required_properties"] = [p.model_dump() for p in updates["required_properties"]]
    if "required_links" in updates and updates["required_links"] is not None:
        updates["required_links"] = [l.model_dump() for l in updates["required_links"]]
    iface = await service.update_interface(id, **updates)
    if not iface:
        raise HTTPException(status_code=404, detail="Interface not found")
    return InterfaceResponse(
        id=iface.id,
        tenant_id=iface.tenant_id,
        name=iface.name,
        display_name=iface.display_name,
        description=iface.description,
        required_properties=iface.required_properties or [],
        required_links=iface.required_links or [],
        status=iface.status,
        created_at=iface.created_at,
        updated_at=iface.updated_at,
    )


@router.delete("/interfaces/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interface(
    request: Request,
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    iface = await service.get_interface(id)
    if not iface:
        raise HTTPException(status_code=404, detail="Interface not found")
    iface.status = "archived"
    await db.flush()
    return None


# ---------------------------------------------------------------------------
# Action Types
# ---------------------------------------------------------------------------

@router.post("/action-types", response_model=ActionTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_action_type(
    request: Request,
    data: ActionTypeCreate,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    at_data = {
        "name": data.name,
        "display_name": data.display_name or data.name,
        "description": data.description,
        "target_object_type_id": data.target_object_type_id,
        "parameters": [p.model_dump() for p in data.parameters] if data.parameters else [],
        "modifies_properties": data.modifies_properties or [],
        "modifies_links": data.modifies_links or [],
        "rules": [r.model_dump() for r in data.rules] if data.rules else [],
        "execution_type": data.execution_type or "direct",
        "status": "active",
    }
    at = await service.create_action_type(at_data)
    return ActionTypeResponse(
        id=at.id,
        tenant_id=at.tenant_id,
        name=at.name,
        display_name=at.display_name,
        description=at.description,
        target_object_type_id=at.target_object_type_id,
        parameters=at.parameters or [],
        modifies_properties=at.modifies_properties or [],
        modifies_links=at.modifies_links or [],
        rules=at.rules or [],
        execution_type=at.execution_type,
        status=at.status,
        created_at=at.created_at,
        updated_at=at.updated_at,
    )


@router.get("/action-types", response_model=ActionTypeListResponse)
async def list_action_types(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    items, total = await service.list_action_types_paginated(
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    pages = (total + page_size - 1) // page_size
    return ActionTypeListResponse(
        items=[ActionTypeResponse(
            id=i.id,
            tenant_id=i.tenant_id,
            name=i.name,
            display_name=i.display_name,
            description=i.description,
            target_object_type_id=i.target_object_type_id,
            parameters=i.parameters or [],
            modifies_properties=i.modifies_properties or [],
            modifies_links=i.modifies_links or [],
            rules=i.rules or [],
            execution_type=i.execution_type,
            status=i.status,
            created_at=i.created_at,
            updated_at=i.updated_at,
        ) for i in items],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.get("/action-types/{id}", response_model=ActionTypeResponse)
async def get_action_type(
    request: Request,
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    at = await service.get_action_type(id)
    if not at:
        raise HTTPException(status_code=404, detail="Action type not found")
    return ActionTypeResponse(
        id=at.id,
        tenant_id=at.tenant_id,
        name=at.name,
        display_name=at.display_name,
        description=at.description,
        target_object_type_id=at.target_object_type_id,
        parameters=at.parameters or [],
        modifies_properties=at.modifies_properties or [],
        modifies_links=at.modifies_links or [],
        rules=at.rules or [],
        execution_type=at.execution_type,
        status=at.status,
        created_at=at.created_at,
        updated_at=at.updated_at,
    )


@router.put("/action-types/{id}", response_model=ActionTypeResponse)
async def update_action_type(
    request: Request,
    id: UUID,
    data: ActionTypeUpdate,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    updates = data.model_dump(exclude_unset=True)
    if "parameters" in updates and updates["parameters"] is not None:
        updates["parameters"] = [p.model_dump() for p in updates["parameters"]]
    if "rules" in updates and updates["rules"] is not None:
        updates["rules"] = [r.model_dump() for r in updates["rules"]]
    at = await service.update_action_type(id, **updates)
    if not at:
        raise HTTPException(status_code=404, detail="Action type not found")
    return ActionTypeResponse(
        id=at.id,
        tenant_id=at.tenant_id,
        name=at.name,
        display_name=at.display_name,
        description=at.description,
        target_object_type_id=at.target_object_type_id,
        parameters=at.parameters or [],
        modifies_properties=at.modifies_properties or [],
        modifies_links=at.modifies_links or [],
        rules=at.rules or [],
        execution_type=at.execution_type,
        status=at.status,
        created_at=at.created_at,
        updated_at=at.updated_at,
    )


@router.delete("/action-types/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action_type(
    request: Request,
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    at = await service.get_action_type(id)
    if not at:
        raise HTTPException(status_code=404, detail="Action type not found")
    at.status = "archived"
    await db.flush()
    return None


@router.post("/action-types/{id}/execute", response_model=ActionExecuteResponse)
async def execute_action(
    id: UUID,
    data: ActionExecuteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Execute an action on a target object."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    start = time.time()
    executor = ActionExecutor(db, tenant_id)
    result = await executor.execute(
        action_type_id=id,
        target_object_id=data.target_object_id,
        parameters=data.parameters or {},
    )
    FUNCTION_EXEC_DURATION.observe(time.time() - start)
    return result


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

@router.post("/functions", response_model=FunctionResponse, status_code=status.HTTP_201_CREATED)
async def create_function(
    request: Request,
    data: FunctionCreate,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    fn_data = {
        "name": data.name,
        "display_name": data.display_name or data.name,
        "description": data.description,
        "language": data.language or "python",
        "code": data.code,
        "read_only": data.read_only or False,
        "timeout_seconds": data.timeout_seconds or 30,
        "memory_mb": data.memory_mb or 256,
        "status": "active",
    }
    fn = await service.create_function(fn_data)

    # Create initial version
    version = OntologyFunctionVersion(
        function_id=fn.id,
        version=1,
        code=data.code,
        change_notes="Initial version",
    )
    db.add(version)
    await db.flush()
    await db.refresh(fn)
    return FunctionResponse(
        id=fn.id,
        tenant_id=fn.tenant_id,
        name=fn.name,
        display_name=fn.display_name,
        description=fn.description,
        language=fn.language,
        code=fn.code,
        read_only=fn.read_only,
        timeout_seconds=fn.timeout_seconds,
        memory_mb=fn.memory_mb,
        status=fn.status,
        current_version=fn.current_version or 1,
        created_at=fn.created_at,
        updated_at=fn.updated_at,
    )


@router.get("/functions", response_model=FunctionListResponse)
async def list_functions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    items, total = await service.list_functions_paginated(
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    pages = (total + page_size - 1) // page_size
    return FunctionListResponse(
        items=[FunctionResponse(
            id=f.id,
            tenant_id=f.tenant_id,
            name=f.name,
            display_name=f.display_name,
            description=f.description,
            language=f.language,
            code=f.code,
            read_only=f.read_only,
            timeout_seconds=f.timeout_seconds,
            memory_mb=f.memory_mb,
            status=f.status,
            current_version=f.current_version or 1,
            created_at=f.created_at,
            updated_at=f.updated_at,
        ) for f in items],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.get("/functions/{id}", response_model=FunctionResponse)
async def get_function(
    request: Request,
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    fn = await service.get_function(id)
    if not fn:
        raise HTTPException(status_code=404, detail="Function not found")
    return FunctionResponse(
        id=fn.id,
        tenant_id=fn.tenant_id,
        name=fn.name,
        display_name=fn.display_name,
        description=fn.description,
        language=fn.language,
        code=fn.code,
        read_only=fn.read_only,
        timeout_seconds=fn.timeout_seconds,
        memory_mb=fn.memory_mb,
        status=fn.status,
        current_version=fn.current_version or 1,
        created_at=fn.created_at,
        updated_at=fn.updated_at,
    )


@router.put("/functions/{id}", response_model=FunctionResponse)
async def update_function(
    request: Request,
    id: UUID,
    data: FunctionUpdate,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    fn = await service.get_function(id)
    if not fn:
        raise HTTPException(status_code=404, detail="Function not found")
    if fn.read_only:
        raise HTTPException(status_code=403, detail="Cannot modify read-only function")

    if data.display_name is not None:
        fn.display_name = data.display_name
    if data.description is not None:
        fn.description = data.description
    if data.code is not None:
        fn.code = data.code
        fn.current_version = (fn.current_version or 1) + 1
        version = OntologyFunctionVersion(
            function_id=fn.id,
            version=fn.current_version,
            code=data.code,
            change_notes=data.change_notes or "Updated",
        )
        db.add(version)
    if data.timeout_seconds is not None:
        fn.timeout_seconds = data.timeout_seconds
    if data.memory_mb is not None:
        fn.memory_mb = data.memory_mb
    if data.status is not None:
        fn.status = data.status
    await db.flush()
    await db.refresh(fn)
    return FunctionResponse(
        id=fn.id,
        tenant_id=fn.tenant_id,
        name=fn.name,
        display_name=fn.display_name,
        description=fn.description,
        language=fn.language,
        code=fn.code,
        read_only=fn.read_only,
        timeout_seconds=fn.timeout_seconds,
        memory_mb=fn.memory_mb,
        status=fn.status,
        current_version=fn.current_version or 1,
        created_at=fn.created_at,
        updated_at=fn.updated_at,
    )


@router.delete("/functions/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_function(
    request: Request,
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    fn = await service.get_function(id)
    if not fn:
        raise HTTPException(status_code=404, detail="Function not found")
    fn.status = "archived"
    await db.flush()
    return None


@router.post("/functions/{id}/test", response_model=ActionExecuteResponse)
async def test_function(
    id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Test-run a function in sandbox mode."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    fn = await service.get_function(id)
    if not fn:
        raise HTTPException(status_code=404, detail="Function not found")

    # Create a dummy action type for execution
    executor = ActionExecutor(db, tenant_id)
    # Directly call function_backed execution via a synthetic action
    # We'll create a temporary action and execute it
    dummy_action = OntologyActionType(
        tenant_id=tenant_id,
        name=f"_test_{fn.name}",
        target_object_type_id=UUID(int=0),
        execution_type="function_backed",
        function_id=fn.id,
        parameters=[],
        modifies_properties=[],
        modifies_links=[],
        rules=[],
    )
    db.add(dummy_action)
    await db.flush()

    result = await executor.execute(
        action_type_id=dummy_action.id,
        target_object_id=UUID(int=0),
        parameters={},
    )
    return result


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return ontology dashboard statistics."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))

    object_type_count = await db.scalar(
        select(func.count()).select_from(OntologyObjectType).where(
            OntologyObjectType.tenant_id == tenant_id,
            OntologyObjectType.status != "archived",
        )
    )

    object_instance_count = await db.scalar(
        select(func.count()).select_from(OntologyObject).where(
            OntologyObject.tenant_id == tenant_id,
            OntologyObject.status != "archived",
        )
    )

    link_type_count = await db.scalar(
        select(func.count()).select_from(OntologyLinkType).where(
            OntologyLinkType.tenant_id == tenant_id,
            OntologyLinkType.status != "archived",
        )
    )

    interface_count = await db.scalar(
        select(func.count()).select_from(OntologyInterface).where(
            OntologyInterface.tenant_id == tenant_id,
            OntologyInterface.status != "archived",
        )
    )

    action_type_count = await db.scalar(
        select(func.count()).select_from(OntologyActionType).where(
            OntologyActionType.tenant_id == tenant_id,
            OntologyActionType.status != "archived",
        )
    )

    function_count = await db.scalar(
        select(func.count()).select_from(OntologyFunction).where(
            OntologyFunction.tenant_id == tenant_id,
            OntologyFunction.status != "archived",
        )
    )

    action_execution_count = await db.scalar(
        select(func.count()).select_from(ActionExecutionLog).where(
            ActionExecutionLog.tenant_id == tenant_id,
        )
    )

    recent_logs_result = await db.execute(
        select(ActionExecutionLog)
        .where(ActionExecutionLog.tenant_id == tenant_id)
        .order_by(ActionExecutionLog.executed_at.desc())
        .limit(5)
    )
    recent_logs = recent_logs_result.scalars().all()

    # Fetch action type names and object keys for recent logs
    action_type_ids = {log.action_type_id for log in recent_logs if log.action_type_id}
    object_ids = {log.target_object_id for log in recent_logs if log.target_object_id}

    action_names = {}
    if action_type_ids:
        at_result = await db.execute(
            select(OntologyActionType.id, OntologyActionType.name).where(
                OntologyActionType.id.in_(action_type_ids)
            )
        )
        action_names = {row[0]: row[1] for row in at_result.all()}

    object_keys = {}
    if object_ids:
        obj_result = await db.execute(
            select(OntologyObject.id, OntologyObject.object_key).where(
                OntologyObject.id.in_(object_ids)
            )
        )
        object_keys = {row[0]: row[1] for row in obj_result.all()}

    recent_actions = [
        RecentAction(
            id=log.id,
            action_name=action_names.get(log.action_type_id, "Unknown"),
            target_object_key=object_keys.get(log.target_object_id, "Unknown"),
            status=log.status,
            executed_at=log.executed_at,
            duration_ms=log.duration_ms,
        )
        for log in recent_logs
    ]

    return DashboardStats(
        object_type_count=object_type_count or 0,
        object_instance_count=object_instance_count or 0,
        link_type_count=link_type_count or 0,
        interface_count=interface_count or 0,
        action_type_count=action_type_count or 0,
        function_count=function_count or 0,
        action_execution_count=action_execution_count or 0,
        recent_actions=recent_actions,
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@router.post("/search", response_model=OntologySearchResponse)
async def search_ontology(
    request: Request,
    data: OntologySearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Hybrid search across ontology objects."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = SemanticSearchService(db, tenant_id)
    result = await service.search(
        query=data.query,
        object_types=data.object_types,
        search_mode=data.search_mode or "hybrid",
        top_k=data.top_k or 20,
    )
    return result


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------

@router.post("/compile", response_model=CompileResult)
async def full_compile(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Trigger full ontology compilation.

    Uses new CompilationPipeline (Sprint 3) with 6-stage orchestration.
    """
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    start = time.time()
    result = await compile_ontology(db, tenant_id)
    COMPILE_FULL_DURATION.observe(time.time() - start)
    return result


# ---------------------------------------------------------------------------
# P0-ONT-05: Compile Rollback
# ---------------------------------------------------------------------------

@router.post("/compile/rollback", response_model=CompileResult)
async def rollback_compile(
    request: Request,
    rollback_data: RollbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Rollback a specific compile by restoring previous constraints.
    
    P0-ONT-05: Drops Neo4j constraints from the specified compile
    and marks the log as rolled_back.
    """
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    compiler = OntologyCompiler(db, tenant_id)
    result = await compiler.rollback_compile(rollback_data.log_id)
    return result


@router.get("/compile/logs", response_model=CompileLogListResponse)
async def list_compile_logs(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List compile logs for the tenant."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    logs = await service.get_compile_logs(limit=limit, offset=offset)
    
    items = []
    for log in logs:
        items.append(CompileLogResponse(
            id=log.id,
            tenant_id=log.tenant_id,
            version=log.version,
            parent_version=log.parent_version,
            compile_type=log.compile_type,
            status=log.status,
            affected_types=log.affected_types or [],
            duration_ms=log.duration_ms,
            started_at=log.started_at,
            completed_at=log.completed_at,
            rolled_back_at=log.rolled_back_at,
            error_count=len(log.errors) if log.errors else 0,
            warning_count=len(log.warnings) if log.warnings else 0,
        ))
    
    return CompileLogListResponse(
        items=items,
        total=len(items),
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# P0-ONT-02: Validation
# ---------------------------------------------------------------------------

@router.post("/compile/validate", response_model=ValidationResponse)
async def validate_ontology(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Run static validation on all ontology definitions.
    
    P0-ONT-02: Returns structured errors with error_kind, field, detail.
    """
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    start = time.time()
    service = OntologyService(db, tenant_id)
    errors = await service.validate_all()
    VALIDATION_DURATION.observe(time.time() - start)
    
    return ValidationResponse(
        is_valid=len(errors) == 0,
        errors=errors,
        error_count=len(errors),
        warning_count=0,
    )


# ---------------------------------------------------------------------------
# P0-ONT-01: DAG / Dependency
# ---------------------------------------------------------------------------

@router.get("/dag/cycle", response_model=DAGCycleResponse)
async def detect_cycle(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Detect cycles in ontology dependencies.
    
    P0-ONT-01: Returns cycle path if found, otherwise no cycle.
    """
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    start = time.time()
    service = OntologyService(db, tenant_id)
    cycle = await service.detect_cycles()
    DAG_DETECT_DURATION.observe(time.time() - start)
    
    if cycle:
        DAG_CYCLES_DETECTED.inc()
        cycle_str = " -> ".join(str(n)[:8] for n in cycle)
        return DAGCycleResponse(
            has_cycle=True,
            cycle_path=[str(n) for n in cycle],
            cycle_description=f"Circular dependency detected: {cycle_str}",
        )
    
    return DAGCycleResponse(has_cycle=False)


@router.get("/dag/compile-order", response_model=List[str])
async def get_compile_order(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get topological compile order for all ontology types.
    
    P0-ONT-01: Uses Kahn's algorithm. Returns 400 if cycle detected.
    """
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    
    try:
        order = await service.get_compile_order()
        return [str(node_id) for node_id in order]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dag/impact/{node_id}", response_model=DAGImpactResponse)
async def get_impact_set(
    request: Request,
    node_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all nodes that depend on the given node (BFS impact set).
    
    P0-ONT-01: Used for incremental compilation.
    """
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    service = OntologyService(db, tenant_id)
    dag = await service.build_dependency_dag()
    
    try:
        nid = UUID(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid node_id UUID format")
    
    impact = dag.get_impact_set(nid)
    
    return DAGImpactResponse(
        node_id=node_id,
        impact_set=[str(n) for n in impact],
        impact_count=len(impact),
    )


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

@router.get("/export")
async def export_ontology(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Export all active ontology definitions as JSON."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))

    obj_types = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.tenant_id == tenant_id,
            OntologyObjectType.status != "archived",
        )
    )
    link_types = await db.execute(
        select(OntologyLinkType).where(
            OntologyLinkType.tenant_id == tenant_id,
            OntologyLinkType.status != "archived",
        )
    )
    interfaces = await db.execute(
        select(OntologyInterface).where(
            OntologyInterface.tenant_id == tenant_id,
            OntologyInterface.status != "archived",
        )
    )
    action_types = await db.execute(
        select(OntologyActionType).where(
            OntologyActionType.tenant_id == tenant_id,
            OntologyActionType.status != "archived",
        )
    )
    functions = await db.execute(
        select(OntologyFunction).where(
            OntologyFunction.tenant_id == tenant_id,
            OntologyFunction.status != "archived",
        )
    )

    def serialize(orm_obj, fields):
        return {f: getattr(orm_obj, f) for f in fields if hasattr(orm_obj, f)}

    return {
        "version": "2.0",
        "exported_at": datetime.utcnow().isoformat(),
        "object_types": [serialize(ot, ["name", "display_name", "description", "icon", "properties", "implemented_interfaces", "neo4j_label", "status"]) for ot in obj_types.scalars().all()],
        "link_types": [serialize(lt, ["name", "display_name", "description", "source_object_type_id", "target_object_type_id", "cardinality", "neo4j_edge_type", "status"]) for lt in link_types.scalars().all()],
        "interfaces": [serialize(i, ["name", "display_name", "description", "required_properties", "required_links", "status"]) for i in interfaces.scalars().all()],
        "action_types": [serialize(at, ["name", "display_name", "description", "target_object_type_id", "parameters", "rules", "execution_type", "status"]) for at in action_types.scalars().all()],
        "functions": [serialize(f, ["name", "display_name", "description", "language", "code", "timeout_seconds", "memory_mb", "status"]) for f in functions.scalars().all()],
    }





async def _import_entities(
    db: AsyncSession,
    tenant_id: UUID,
    items: List[Dict[str, Any]],
    model_class,
    name_field: str,
    conflict_strategy: str,
    imported: dict,
    skipped: list,
    overwritten: list,
    renamed: list,
    errors: list,
    entity_type: str,
):
    """Helper to import entities with conflict resolution."""
    for item_data in items:
        name = item_data.get(name_field)
        if not name:
            errors.append(ImportError(entity_type=entity_type, entity_name="unknown", error=f"Missing {name_field}"))
            continue

        # Check existing
        existing = await db.execute(
            select(model_class).where(
                model_class.tenant_id == tenant_id,
                model_class.name == name,
            )
        )
        existing_obj = existing.scalar_one_or_none()

        if existing_obj:
            if conflict_strategy == "skip":
                skipped.append(name)
                continue
            elif conflict_strategy == "overwrite":
                for k, v in item_data.items():
                    if hasattr(model_class, k) and k not in ("id", "tenant_id", "created_at"):
                        setattr(existing_obj, k, v)
                overwritten.append(name)
                imported[entity_type] += 1
                continue
            elif conflict_strategy == "rename":
                # Find a unique name
                suffix = 1
                new_name = f"{name}_imported_{suffix}"
                while True:
                    check = await db.execute(
                        select(model_class).where(
                            model_class.tenant_id == tenant_id,
                            model_class.name == new_name,
                        )
                    )
                    if not check.scalar_one_or_none():
                        break
                    suffix += 1
                    new_name = f"{name}_imported_{suffix}"
                item_data = {**item_data, name_field: new_name}
                renamed.append(new_name)

        # Create new
        try:
            entity = model_class(tenant_id=tenant_id, **{k: v for k, v in item_data.items() if hasattr(model_class, k)})
            db.add(entity)
            imported[entity_type] += 1
        except Exception as e:
            errors.append(ImportError(entity_type=entity_type, entity_name=name, error=str(e)))


@router.post("/import", response_model=OntologyImportResult)
async def import_ontology(
    request: Request,
    data: OntologyImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import ontology definitions from JSON with conflict resolution."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    imported = {"object_types": 0, "link_types": 0, "interfaces": 0, "action_types": 0, "functions": 0}
    skipped: List[str] = []
    overwritten: List[str] = []
    renamed: List[str] = []
    errors: List[ImportError] = []

    await _import_entities(
        db, tenant_id, data.object_types, OntologyObjectType, "name",
        data.conflict_strategy, imported, skipped, overwritten, renamed, errors, "object_types"
    )
    await _import_entities(
        db, tenant_id, data.link_types, OntologyLinkType, "name",
        data.conflict_strategy, imported, skipped, overwritten, renamed, errors, "link_types"
    )
    await _import_entities(
        db, tenant_id, data.interfaces, OntologyInterface, "name",
        data.conflict_strategy, imported, skipped, overwritten, renamed, errors, "interfaces"
    )
    await _import_entities(
        db, tenant_id, data.action_types, OntologyActionType, "name",
        data.conflict_strategy, imported, skipped, overwritten, renamed, errors, "action_types"
    )
    await _import_entities(
        db, tenant_id, data.functions, OntologyFunction, "name",
        data.conflict_strategy, imported, skipped, overwritten, renamed, errors, "functions"
    )

    await db.flush()
    return OntologyImportResult(
        imported_object_types=imported["object_types"],
        imported_link_types=imported["link_types"],
        imported_interfaces=imported["interfaces"],
        imported_action_types=imported["action_types"],
        imported_functions=imported["functions"],
        skipped=len(skipped),
        overwritten=len(overwritten),
        renamed=len(renamed),
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Subgraph
# ---------------------------------------------------------------------------

@router.get("/subgraph/{object_id}", response_model=SubgraphResponse)
async def get_subgraph(
    object_id: UUID,
    request: Request,
    depth: int = Query(1, ge=1, le=3),
    db: AsyncSession = Depends(get_db),
):
    """Get subgraph around an object (1-3 hops)."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))

    # Get the starting object
    result = await db.execute(
        select(OntologyObject).where(
            OntologyObject.id == object_id,
            OntologyObject.tenant_id == tenant_id,
        )
    )
    start_obj = result.scalar_one_or_none()
    if not start_obj:
        raise HTTPException(status_code=404, detail="Object not found")

    # Query Neo4j for subgraph
    cypher = """
    MATCH path = (start)-[*1..$depth]-(connected)
    WHERE elementId(start) = $neo4j_node_id
    RETURN [n IN nodes(path) | {id: elementId(n), labels: labels(n), properties: properties(n)}] as path_nodes,
           [r IN relationships(path) | {id: elementId(r), type: type(r), start: elementId(startNode(r)), end: elementId(endNode(r)), properties: properties(r)}] as path_rels
    LIMIT 500
    """
    try:
        graph_result = await neo4j_client.execute_query(cypher, {
            "neo4j_node_id": start_obj.neo4j_node_id,
            "depth": depth,
        })
    except Exception as e:
        logger.warning(f"Neo4j subgraph query failed: {e}")
        graph_result = []

    nodes_map: Dict[str, GraphNode] = {}
    edges_map: Dict[str, GraphEdge] = {}
    object_types: set = set()

    for record in graph_result:
        for n in record.get("path_nodes", []):
            nid = n.get("id")
            labels = n.get("labels", [])
            props = n.get("properties", {})
            if nid and nid not in nodes_map:
                obj_type = labels[0] if labels else "Unknown"
                object_types.add(obj_type)
                nodes_map[nid] = GraphNode(
                    id=nid,
                    label=props.get("object_key", props.get("name", nid)),
                    object_type=obj_type,
                    properties=props,
                )
        for r in record.get("path_rels", []):
            rid = r.get("id")
            if rid and rid not in edges_map:
                edges_map[rid] = GraphEdge(
                    id=rid,
                    source=r.get("start"),
                    target=r.get("end"),
                    label=r.get("type"),
                    properties=r.get("properties", {}),
                )

    return SubgraphResponse(
        nodes=list(nodes_map.values()),
        edges=list(edges_map.values()),
        metadata=GraphMetadata(
            total_nodes=len(nodes_map),
            total_edges=len(edges_map),
            object_types=list(object_types),
        ),
    )
