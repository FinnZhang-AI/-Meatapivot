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
)
from app.services.database import get_db
from app.services.neo4j_client import neo4j_client
from app.services.ontology_compiler import OntologyCompiler
from app.services.semantic_search import SemanticSearchService
from app.services.action_executor import ActionExecutor

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
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))  # fallback; auth middleware should set this
    # Check duplicate name within tenant
    result = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.tenant_id == tenant_id,
            OntologyObjectType.name == data.name,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Object type name already exists")

    obj_type = OntologyObjectType(
        tenant_id=tenant_id,
        name=data.name,
        display_name=data.display_name or data.name,
        description=data.description,
        icon=data.icon or "box",
        properties=[p.model_dump() for p in data.properties],
        implemented_interfaces=list(data.implemented_interfaces) if data.implemented_interfaces else [],
        neo4j_label=data.neo4j_label or data.name,
        status="draft",
    )
    db.add(obj_type)
    await db.flush()
    await db.refresh(obj_type)
    return _obj_type_resp(obj_type)


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
    filters = [OntologyObjectType.tenant_id == tenant_id]
    if status_filter:
        filters.append(OntologyObjectType.status == status_filter)

    total_result = await db.execute(
        select(func.count()).select_from(OntologyObjectType).where(and_(*filters))
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(OntologyObjectType)
        .where(and_(*filters))
        .order_by(OntologyObjectType.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_obj_type_resp(ot) for ot in result.scalars().all()]
    pages = (total + page_size - 1) // page_size
    return ObjectTypeListResponse(items=items, total=total, page=page, page_size=page_size, pages=pages)


@router.get("/object-types/{id}", response_model=ObjectTypeResponse)
async def get_object_type(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get Object Type by ID."""
    result = await db.execute(select(OntologyObjectType).where(OntologyObjectType.id == id))
    ot = result.scalar_one_or_none()
    if not ot:
        raise HTTPException(status_code=404, detail="Object type not found")
    return _obj_type_resp(ot)


@router.put("/object-types/{id}", response_model=ObjectTypeResponse)
async def update_object_type(
    id: UUID,
    data: ObjectTypeUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update Object Type."""
    result = await db.execute(select(OntologyObjectType).where(OntologyObjectType.id == id))
    ot = result.scalar_one_or_none()
    if not ot:
        raise HTTPException(status_code=404, detail="Object type not found")

    if data.display_name is not None:
        ot.display_name = data.display_name
    if data.description is not None:
        ot.description = data.description
    if data.icon is not None:
        ot.icon = data.icon
    if data.properties is not None:
        ot.properties = [p.model_dump() for p in data.properties]
    if data.implemented_interfaces is not None:
        ot.implemented_interfaces = list(data.implemented_interfaces)
    if data.status is not None:
        ot.status = data.status
    ot.version = (ot.version or 1) + 1
    await db.flush()
    await db.refresh(ot)
    return _obj_type_resp(ot)


@router.delete("/object-types/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_object_type(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete Object Type (archive)."""
    result = await db.execute(select(OntologyObjectType).where(OntologyObjectType.id == id))
    ot = result.scalar_one_or_none()
    if not ot:
        raise HTTPException(status_code=404, detail="Object type not found")
    ot.status = "archived"
    await db.flush()
    return None


@router.post("/object-types/{id}/compile", response_model=CompileResult)
async def compile_object_type(
    id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Trigger incremental compilation for an Object Type."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    compiler = OntologyCompiler(db, tenant_id)
    result = await compiler.incremental_compile(id)
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

    # Validate object type exists
    result = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.id == id,
            OntologyObjectType.tenant_id == tenant_id,
        )
    )
    obj_type = result.scalar_one_or_none()
    if not obj_type:
        raise HTTPException(status_code=404, detail="Object type not found")

    # Check duplicate key
    dup = await db.execute(
        select(OntologyObject).where(
            OntologyObject.tenant_id == tenant_id,
            OntologyObject.object_type_id == id,
            OntologyObject.object_key == data.object_key,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Object key already exists for this type")

    obj = OntologyObject(
        tenant_id=tenant_id,
        object_type_id=id,
        object_key=data.object_key,
        properties=data.properties or {},
        status="active",
    )
    db.add(obj)
    await db.flush()

    # Sync to Neo4j
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
    db: AsyncSession = Depends(get_db),
):
    """List object instances of a given type."""
    result = await db.execute(
        select(OntologyObject).where(
            OntologyObject.object_type_id == id,
            OntologyObject.status != "archived",
        ).order_by(OntologyObject.created_at.desc())
    )
    objs = result.scalars().all()

    # Batch fetch type names
    type_ids = {o.object_type_id for o in objs}
    type_result = await db.execute(
        select(OntologyObjectType.id, OntologyObjectType.name).where(
            OntologyObjectType.id.in_(type_ids)
        )
    )
    type_names = {row[0]: row[1] for row in type_result.all()}
    return [_obj_resp(o, type_names.get(o.object_type_id, "")) for o in objs]


@router.get("/objects/{object_id}", response_model=OntologyObjectResponse)
async def get_object(
    object_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get a single object instance by ID."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    result = await db.execute(
        select(OntologyObject).where(
            OntologyObject.id == object_id,
            OntologyObject.tenant_id == tenant_id,
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")

    type_result = await db.execute(
        select(OntologyObjectType.name).where(OntologyObjectType.id == obj.object_type_id)
    )
    type_name = type_result.scalar() or ""
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
    result = await db.execute(
        select(OntologyObject).where(
            OntologyObject.id == object_id,
            OntologyObject.tenant_id == tenant_id,
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")

    if data.object_key is not None:
        obj.object_key = data.object_key
    if data.properties is not None:
        obj.properties = data.properties
    if data.status is not None:
        obj.status = data.status
    await db.flush()

    # Sync to Neo4j if properties changed
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
    type_result = await db.execute(
        select(OntologyObjectType.name).where(OntologyObjectType.id == obj.object_type_id)
    )
    type_name = type_result.scalar() or ""
    return _obj_resp(obj, type_name)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    link_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Delete a link instance (hard delete from PG + Neo4j)."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    result = await db.execute(
        select(OntologyLink).where(
            OntologyLink.id == link_id,
            OntologyLink.tenant_id == tenant_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    # Delete from Neo4j
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

    await db.delete(link)
    await db.flush()
    return None


@router.get("/objects/{object_id}/links", response_model=list[OntologyLinkResponse])
async def get_object_links(
    object_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get all links connected to an object (as source or target)."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    result = await db.execute(
        select(OntologyLink).where(
            OntologyLink.tenant_id == tenant_id,
            (OntologyLink.source_object_id == object_id) | (OntologyLink.target_object_id == object_id),
        )
    )
    links = result.scalars().all()

    # Fetch link type names
    link_type_ids = {l.link_type_id for l in links}
    lt_result = await db.execute(
        select(OntologyLinkType.id, OntologyLinkType.name).where(
            OntologyLinkType.id.in_(link_type_ids)
        )
    )
    link_type_names = {row[0]: row[1] for row in lt_result.all()}

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

    # Validate source/target types exist
    for type_id, field in [(data.source_object_type_id, "source"), (data.target_object_type_id, "target")]:
        r = await db.execute(
            select(OntologyObjectType).where(
                OntologyObjectType.id == type_id,
                OntologyObjectType.tenant_id == tenant_id,
            )
        )
        if not r.scalar_one_or_none():
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
    total_result = await db.execute(
        select(func.count()).select_from(OntologyLinkType).where(
            OntologyLinkType.tenant_id == tenant_id
        )
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(OntologyLinkType)
        .where(OntologyLinkType.tenant_id == tenant_id)
        .order_by(OntologyLinkType.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()

    # Fetch type names
    type_ids = set()
    for lt in items:
        type_ids.add(lt.source_object_type_id)
        type_ids.add(lt.target_object_type_id)
    type_result = await db.execute(
        select(OntologyObjectType.id, OntologyObjectType.name).where(
            OntologyObjectType.id.in_(type_ids)
        )
    )
    type_names = {row[0]: row[1] for row in type_result.all()}

    pages = (total + page_size - 1) // page_size
    return LinkTypeListResponse(
        items=[_link_type_resp(lt, type_names.get(lt.source_object_type_id, ""), type_names.get(lt.target_object_type_id, "")) for lt in items],
        total=total, page=page, page_size=page_size, pages=pages,
    )


@router.get("/link-types/{id}", response_model=LinkTypeResponse)
async def get_link_type(id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OntologyLinkType).where(OntologyLinkType.id == id))
    lt = result.scalar_one_or_none()
    if not lt:
        raise HTTPException(status_code=404, detail="Link type not found")
    return _link_type_resp(lt)


@router.put("/link-types/{id}", response_model=LinkTypeResponse)
async def update_link_type(id: UUID, data: LinkTypeUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OntologyLinkType).where(OntologyLinkType.id == id))
    lt = result.scalar_one_or_none()
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
async def delete_link_type(id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OntologyLinkType).where(OntologyLinkType.id == id))
    lt = result.scalar_one_or_none()
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

    # Validate link type
    r = await db.execute(
        select(OntologyLinkType).where(
            OntologyLinkType.id == id,
            OntologyLinkType.tenant_id == tenant_id,
        )
    )
    lt = r.scalar_one_or_none()
    if not lt:
        raise HTTPException(status_code=404, detail="Link type not found")

    # Validate source/target objects
    for obj_id, field in [(data.source_object_id, "source"), (data.target_object_id, "target")]:
        obj_r = await db.execute(
            select(OntologyObject).where(
                OntologyObject.id == obj_id,
                OntologyObject.tenant_id == tenant_id,
            )
        )
        if not obj_r.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"{field} object not found")

    link = OntologyLink(
        tenant_id=tenant_id,
        link_type_id=id,
        source_object_id=data.source_object_id,
        target_object_id=data.target_object_id,
        properties=data.properties or {},
    )
    db.add(link)
    await db.flush()

    # Sync to Neo4j
    edge_type = lt.neo4j_edge_type or lt.name
    try:
        src_r = await db.execute(
            select(OntologyObject.neo4j_node_id).where(OntologyObject.id == data.source_object_id)
        )
        tgt_r = await db.execute(
            select(OntologyObject.neo4j_node_id).where(OntologyObject.id == data.target_object_id)
        )
        src_node_id = src_r.scalar()
        tgt_node_id = tgt_r.scalar()

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
    iface = OntologyInterface(
        tenant_id=tenant_id,
        name=data.name,
        display_name=data.display_name or data.name,
        description=data.description,
        required_properties=[p.model_dump() for p in data.required_properties] if data.required_properties else [],
        required_links=[l.model_dump() for l in data.required_links] if data.required_links else [],
        status="active",
    )
    db.add(iface)
    await db.flush()
    await db.refresh(iface)
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
    total_result = await db.execute(
        select(func.count()).select_from(OntologyInterface).where(
            OntologyInterface.tenant_id == tenant_id
        )
    )
    total = total_result.scalar() or 0
    result = await db.execute(
        select(OntologyInterface)
        .where(OntologyInterface.tenant_id == tenant_id)
        .order_by(OntologyInterface.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
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
async def get_interface(id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OntologyInterface).where(OntologyInterface.id == id))
    iface = result.scalar_one_or_none()
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
async def update_interface(id: UUID, data: InterfaceUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OntologyInterface).where(OntologyInterface.id == id))
    iface = result.scalar_one_or_none()
    if not iface:
        raise HTTPException(status_code=404, detail="Interface not found")
    if data.display_name is not None:
        iface.display_name = data.display_name
    if data.description is not None:
        iface.description = data.description
    if data.required_properties is not None:
        iface.required_properties = [p.model_dump() for p in data.required_properties]
    if data.required_links is not None:
        iface.required_links = [l.model_dump() for l in data.required_links]
    if data.status is not None:
        iface.status = data.status
    await db.flush()
    await db.refresh(iface)
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
async def delete_interface(id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OntologyInterface).where(OntologyInterface.id == id))
    iface = result.scalar_one_or_none()
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
    at = OntologyActionType(
        tenant_id=tenant_id,
        name=data.name,
        display_name=data.display_name or data.name,
        description=data.description,
        target_object_type_id=data.target_object_type_id,
        parameters=[p.model_dump() for p in data.parameters] if data.parameters else [],
        modifies_properties=data.modifies_properties or [],
        modifies_links=data.modifies_links or [],
        rules=[r.model_dump() for r in data.rules] if data.rules else [],
        execution_type=data.execution_type or "direct",
        status="active",
    )
    db.add(at)
    await db.flush()
    await db.refresh(at)
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
    total_result = await db.execute(
        select(func.count()).select_from(OntologyActionType).where(
            OntologyActionType.tenant_id == tenant_id
        )
    )
    total = total_result.scalar() or 0
    result = await db.execute(
        select(OntologyActionType)
        .where(OntologyActionType.tenant_id == tenant_id)
        .order_by(OntologyActionType.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
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
async def get_action_type(id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OntologyActionType).where(OntologyActionType.id == id))
    at = result.scalar_one_or_none()
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
async def update_action_type(id: UUID, data: ActionTypeUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OntologyActionType).where(OntologyActionType.id == id))
    at = result.scalar_one_or_none()
    if not at:
        raise HTTPException(status_code=404, detail="Action type not found")
    if data.display_name is not None:
        at.display_name = data.display_name
    if data.description is not None:
        at.description = data.description
    if data.parameters is not None:
        at.parameters = [p.model_dump() for p in data.parameters]
    if data.rules is not None:
        at.rules = [r.model_dump() for r in data.rules]
    if data.execution_type is not None:
        at.execution_type = data.execution_type
    if data.status is not None:
        at.status = data.status
    await db.flush()
    await db.refresh(at)
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
    id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    result = await db.execute(
        select(OntologyActionType).where(
            OntologyActionType.id == id,
            OntologyActionType.tenant_id == tenant_id,
        )
    )
    at = result.scalar_one_or_none()
    if not at:
        raise HTTPException(status_code=404, detail="Action type not found")
    at.status = "archived"
    await db.commit()
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
    executor = ActionExecutor(db, tenant_id)
    result = await executor.execute(
        action_type_id=id,
        target_object_id=data.target_object_id,
        parameters=data.parameters or {},
    )
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
    fn = OntologyFunction(
        tenant_id=tenant_id,
        name=data.name,
        display_name=data.display_name or data.name,
        description=data.description,
        language=data.language or "python",
        code=data.code,
        read_only=data.read_only or False,
        timeout_seconds=data.timeout_seconds or 30,
        memory_mb=data.memory_mb or 256,
        status="active",
    )
    db.add(fn)
    await db.flush()

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
    total_result = await db.execute(
        select(func.count()).select_from(OntologyFunction).where(
            OntologyFunction.tenant_id == tenant_id
        )
    )
    total = total_result.scalar() or 0
    result = await db.execute(
        select(OntologyFunction)
        .where(OntologyFunction.tenant_id == tenant_id)
        .order_by(OntologyFunction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
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
async def get_function(id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OntologyFunction).where(OntologyFunction.id == id))
    fn = result.scalar_one_or_none()
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
async def update_function(id: UUID, data: FunctionUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OntologyFunction).where(OntologyFunction.id == id))
    fn = result.scalar_one_or_none()
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
    id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    result = await db.execute(
        select(OntologyFunction).where(
            OntologyFunction.id == id,
            OntologyFunction.tenant_id == tenant_id,
        )
    )
    fn = result.scalar_one_or_none()
    if not fn:
        raise HTTPException(status_code=404, detail="Function not found")
    fn.status = "archived"
    await db.commit()
    return None


@router.post("/functions/{id}/test", response_model=ActionExecuteResponse)
async def test_function(
    id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Test-run a function in sandbox mode."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    result = await db.execute(
        select(OntologyFunction).where(
            OntologyFunction.id == id,
            OntologyFunction.tenant_id == tenant_id,
        )
    )
    fn = result.scalar_one_or_none()
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
    """Trigger full ontology compilation."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    compiler = OntologyCompiler(db, tenant_id)
    result = await compiler.full_compile()
    return result


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





@router.post("/import")
async def import_ontology(
    request: Request,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """Import ontology definitions from JSON."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    imported = {"object_types": 0, "link_types": 0, "interfaces": 0, "action_types": 0, "functions": 0}

    for ot_data in data.get("object_types", []):
        ot = OntologyObjectType(tenant_id=tenant_id, **{k: v for k, v in ot_data.items() if hasattr(OntologyObjectType, k)})
        db.add(ot)
        imported["object_types"] += 1

    for lt_data in data.get("link_types", []):
        lt = OntologyLinkType(tenant_id=tenant_id, **{k: v for k, v in lt_data.items() if hasattr(OntologyLinkType, k)})
        db.add(lt)
        imported["link_types"] += 1

    for i_data in data.get("interfaces", []):
        iface = OntologyInterface(tenant_id=tenant_id, **{k: v for k, v in i_data.items() if hasattr(OntologyInterface, k)})
        db.add(iface)
        imported["interfaces"] += 1

    for at_data in data.get("action_types", []):
        at = OntologyActionType(tenant_id=tenant_id, **{k: v for k, v in at_data.items() if hasattr(OntologyActionType, k)})
        db.add(at)
        imported["action_types"] += 1

    for fn_data in data.get("functions", []):
        fn = OntologyFunction(tenant_id=tenant_id, **{k: v for k, v in fn_data.items() if hasattr(OntologyFunction, k)})
        db.add(fn)
        imported["functions"] += 1

    await db.flush()
    return {"imported": imported}


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
