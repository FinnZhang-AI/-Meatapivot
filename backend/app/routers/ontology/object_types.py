from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
import logging
import math

from app.services.database import get_db
from app.models.ontology_models import (
    OntologyObjectType, OntologyObject, OntologyLinkType, OntologyLink,
    OntologyInterface, OntologyActionType, OntologyFunction, OntologyFunctionVersion
)
from app.models.ontology_schemas import (
    ObjectTypeCreate, ObjectTypeUpdate, ObjectTypeResponse, ObjectTypeListResponse,
    CompileResult, CompileError,
    OntologyObjectCreate, OntologyObjectResponse,
    LinkTypeCreate, LinkTypeUpdate, LinkTypeResponse, LinkTypeListResponse,
    OntologyLinkCreate, OntologyLinkResponse,
    SubgraphResponse, GraphNode, GraphEdge, GraphMetadata,
    PropertyDef, OntologySearchRequest, OntologySearchResponse,
    ValidationResponse, DAGCycleResponse
)
from app.routers.auth import get_current_user, UserResponse
from app.services.neo4j_client import neo4j_client
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ontology"])


async def _get_tenant_id(current_user: UserResponse) -> UUID:
    return UUID(current_user.tenant_id)


@router.post("/object-types", response_model=ObjectTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_object_type(
    object_type_data: ObjectTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new Object Type"""
    tenant_id = await _get_tenant_id(current_user)
    
    existing = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.tenant_id == tenant_id,
            OntologyObjectType.name == object_type_data.name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Object Type '{object_type_data.name}' already exists")
    
    properties_json = [p.model_dump() for p in object_type_data.properties]
    implemented_interfaces_json = [str(i) for i in object_type_data.implemented_interfaces]
    
    obj_type = OntologyObjectType(
        tenant_id=tenant_id,
        name=object_type_data.name,
        display_name=object_type_data.display_name,
        description=object_type_data.description,
        icon=object_type_data.icon or "box",
        properties=properties_json,
        implemented_interfaces=implemented_interfaces_json,
        neo4j_label=object_type_data.neo4j_label or object_type_data.name,
        status="draft",
        compile_status="pending",
        created_by=UUID(current_user.id) if current_user.id else None
    )
    
    db.add(obj_type)
    await db.flush()
    await db.refresh(obj_type)
    
    return ObjectTypeResponse(
        id=obj_type.id,
        tenant_id=obj_type.tenant_id,
        name=obj_type.name,
        display_name=obj_type.display_name,
        description=obj_type.description,
        icon=obj_type.icon,
        properties=[PropertyDef(**p) for p in obj_type.properties],
        implemented_interfaces=[UUID(i) for i in obj_type.implemented_interfaces],
        neo4j_label=obj_type.neo4j_label,
        status=obj_type.status,
        version=obj_type.version,
        compile_status=obj_type.compile_status,
        compile_errors=[],
        created_by=obj_type.created_by,
        created_at=obj_type.created_at,
        updated_at=obj_type.updated_at
    )


@router.get("/object-types", response_model=ObjectTypeListResponse)
async def list_object_types(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """List Object Types with pagination"""
    tenant_id = await _get_tenant_id(current_user)
    
    query = select(OntologyObjectType).where(OntologyObjectType.tenant_id == tenant_id)
    
    if status_filter:
        query = query.where(OntologyObjectType.status == status_filter)
    if search:
        query = query.where(
            OntologyObjectType.name.ilike(f"%{search}%") |
            OntologyObjectType.display_name.ilike(f"%{search}%")
        )
    
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    query = query.order_by(OntologyObjectType.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    object_types = result.scalars().all()
    
    items = []
    for ot in object_types:
        compile_errors = [CompileError(**e) for e in (ot.compile_errors or [])]
        items.append(ObjectTypeResponse(
            id=ot.id,
            tenant_id=ot.tenant_id,
            name=ot.name,
            display_name=ot.display_name,
            description=ot.description,
            icon=ot.icon,
            properties=[PropertyDef(**p) for p in ot.properties],
            implemented_interfaces=[UUID(i) for i in ot.implemented_interfaces],
            neo4j_label=ot.neo4j_label,
            status=ot.status,
            version=ot.version,
            compile_status=ot.compile_status,
            compile_errors=compile_errors,
            created_by=ot.created_by,
            created_at=ot.created_at,
            updated_at=ot.updated_at
        ))
    
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return ObjectTypeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.get("/object-types/{object_type_id}", response_model=ObjectTypeResponse)
async def get_object_type(
    object_type_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a single Object Type by ID"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.id == object_type_id,
            OntologyObjectType.tenant_id == tenant_id
        )
    )
    obj_type = result.scalar_one_or_none()
    
    if not obj_type:
        raise HTTPException(status_code=404, detail="Object Type not found")
    
    compile_errors = [CompileError(**e) for e in (obj_type.compile_errors or [])]
    return ObjectTypeResponse(
        id=obj_type.id,
        tenant_id=obj_type.tenant_id,
        name=obj_type.name,
        display_name=obj_type.display_name,
        description=obj_type.description,
        icon=obj_type.icon,
        properties=[PropertyDef(**p) for p in obj_type.properties],
        implemented_interfaces=[UUID(i) for i in obj_type.implemented_interfaces],
        neo4j_label=obj_type.neo4j_label,
        status=obj_type.status,
        version=obj_type.version,
        compile_status=obj_type.compile_status,
        compile_errors=compile_errors,
        created_by=obj_type.created_by,
        created_at=obj_type.created_at,
        updated_at=obj_type.updated_at
    )


@router.put("/object-types/{object_type_id}", response_model=ObjectTypeResponse)
async def update_object_type(
    object_type_id: UUID,
    update_data: ObjectTypeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Update an Object Type"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.id == object_type_id,
            OntologyObjectType.tenant_id == tenant_id
        )
    )
    obj_type = result.scalar_one_or_none()
    
    if not obj_type:
        raise HTTPException(status_code=404, detail="Object Type not found")
    
    if update_data.display_name is not None:
        obj_type.display_name = update_data.display_name
    if update_data.description is not None:
        obj_type.description = update_data.description
    if update_data.icon is not None:
        obj_type.icon = update_data.icon
    if update_data.properties is not None:
        obj_type.properties = [p.model_dump() for p in update_data.properties]
    if update_data.implemented_interfaces is not None:
        obj_type.implemented_interfaces = [str(i) for i in update_data.implemented_interfaces]
    if update_data.status is not None:
        obj_type.status = update_data.status
    
    obj_type.version += 1
    obj_type.compile_status = "pending"
    
    await db.flush()
    await db.refresh(obj_type)
    
    compile_errors = [CompileError(**e) for e in (obj_type.compile_errors or [])]
    return ObjectTypeResponse(
        id=obj_type.id,
        tenant_id=obj_type.tenant_id,
        name=obj_type.name,
        display_name=obj_type.display_name,
        description=obj_type.description,
        icon=obj_type.icon,
        properties=[PropertyDef(**p) for p in obj_type.properties],
        implemented_interfaces=[UUID(i) for i in obj_type.implemented_interfaces],
        neo4j_label=obj_type.neo4j_label,
        status=obj_type.status,
        version=obj_type.version,
        compile_status=obj_type.compile_status,
        compile_errors=compile_errors,
        created_by=obj_type.created_by,
        created_at=obj_type.created_at,
        updated_at=obj_type.updated_at
    )


@router.delete("/object-types/{object_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_object_type(
    object_type_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Archive (soft delete) an Object Type"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.id == object_type_id,
            OntologyObjectType.tenant_id == tenant_id
        )
    )
    obj_type = result.scalar_one_or_none()
    
    if not obj_type:
        raise HTTPException(status_code=404, detail="Object Type not found")
    
    obj_type.status = "archived"
    await db.flush()


@router.post("/object-types/{object_type_id}/compile", response_model=CompileResult)
async def compile_object_type(
    object_type_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Compile a single Object Type to generate Neo4j constraints"""
    import time
    start_time = int(time.time() * 1000)
    
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.id == object_type_id,
            OntologyObjectType.tenant_id == tenant_id
        )
    )
    obj_type = result.scalar_one_or_none()
    
    if not obj_type:
        raise HTTPException(status_code=404, detail="Object Type not found")
    
    errors = []
    warnings = []
    constraints_created = 0
    
    try:
        required_props = [p for p in obj_type.properties if p.get("required", False)]
        unique_props = [p for p in required_props if p.get("validation", {}).get("unique")]
        
        if unique_props:
            for prop in unique_props:
                constraint_name = f"constraint_{obj_type.neo4j_label}_{prop['name']}_unique"
                cypher = f"""
                CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
                FOR (n:{obj_type.neo4j_label}) REQUIRE n.{prop['name']} IS UNIQUE
                """
                try:
                    await neo4j_client.execute_query(cypher, {})
                    constraints_created += 1
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        errors.append(CompileError(
                            code="CONSTRAINT_FAILED",
                            message=f"Failed to create constraint for {prop['name']}: {str(e)}",
                            field=prop['name']
                        ))
        
        if not errors:
            obj_type.compile_status = "compiled"
            obj_type.compiled_at = func.now()
            obj_type.compile_errors = []
        else:
            obj_type.compile_status = "error"
            obj_type.compile_errors = [e.model_dump() for e in errors]
        
        await db.flush()
        
    except Exception as e:
        logger.error(f"Compile failed for ObjectType {object_type_id}: {e}")
        errors.append(CompileError(code="COMPILE_ERROR", message=str(e)))
        obj_type.compile_status = "error"
        obj_type.compile_errors = [e.model_dump() for e in errors]
        await db.flush()
    
    duration_ms = int(time.time() * 1000) - start_time
    
    return CompileResult(
        status="compiled" if not errors else "has_errors",
        errors=errors,
        warnings=warnings,
        neo4j_constraints_created=constraints_created,
        duration_ms=duration_ms
    )


@router.post("/object-types/{object_type_id}/objects", response_model=OntologyObjectResponse, status_code=status.HTTP_201_CREATED)
async def create_ontology_object(
    object_type_id: UUID,
    object_data: OntologyObjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Create an instance of an Object Type"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.id == object_type_id,
            OntologyObjectType.tenant_id == tenant_id
        )
    )
    obj_type = result.scalar_one_or_none()
    
    if not obj_type:
        raise HTTPException(status_code=404, detail="Object Type not found")
    
    existing = await db.execute(
        select(OntologyObject).where(
            OntologyObject.tenant_id == tenant_id,
            OntologyObject.object_type_id == object_type_id,
            OntologyObject.object_key == object_data.object_key
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Object with key '{object_data.object_key}' already exists")
    
    node_id = f"{obj_type.neo4j_label}_{object_data.object_key}_{uuid.uuid4().hex[:8]}"
    
    cypher = f"""
    CREATE (n:{obj_type.neo4j_label} {{
        object_key: $object_key,
        properties: $properties,
        tenant_id: $tenant_id,
        object_type_id: $object_type_id,
        node_id: $node_id,
        created_at: $created_at
    }})
    RETURN n.node_id as node_id
    """
    
    try:
        neo4j_result = await neo4j_client.execute_query(
            cypher,
            {
                "object_key": object_data.object_key,
                "properties": object_data.properties,
                "tenant_id": str(tenant_id),
                "object_type_id": str(object_type_id),
                "node_id": node_id,
                "created_at": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Neo4j node creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create node: {str(e)}")
    
    ontology_object = OntologyObject(
        tenant_id=tenant_id,
        object_type_id=object_type_id,
        object_key=object_data.object_key,
        properties=object_data.properties,
        neo4j_node_id=node_id,
        status="active",
        created_by=UUID(current_user.id) if current_user.id else None
    )
    
    db.add(ontology_object)
    await db.flush()
    await db.refresh(ontology_object)
    
    return OntologyObjectResponse(
        id=ontology_object.id,
        tenant_id=ontology_object.tenant_id,
        object_type_id=object_type_id,
        object_type_name=obj_type.name,
        object_key=ontology_object.object_key,
        properties=ontology_object.properties,
        neo4j_node_id=ontology_object.neo4j_node_id,
        status=ontology_object.status,
        created_by=ontology_object.created_by,
        created_at=ontology_object.created_at,
        updated_at=ontology_object.updated_at
    )


from datetime import datetime
import uuid


@router.get("/objects/{object_id}/graph", response_model=SubgraphResponse)
async def get_object_subgraph(
    object_id: UUID,
    depth: int = Query(2, ge=1, le=5),
    link_types: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get subgraph around an object (up to depth hops)"""
    import time
    start_time = int(time.time() * 1000)
    
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyObject).where(
            OntologyObject.id == object_id,
            OntologyObject.tenant_id == tenant_id
        )
    )
    obj = result.scalar_one_or_none()
    
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    
    result = await db.execute(
        select(OntologyObjectType).where(OntologyObjectType.id == obj.object_type_id)
    )
    obj_type = result.scalar_one_or_none()
    
    cypher_depth = min(depth, 5)
    
    link_filter = ""
    if link_types:
        link_patterns = "|".join([f":{lt.upper().replace(' ', '_')}" for lt in link_types])
        link_filter = f"AND type(rel) IN ({link_patterns})"
    
    cypher = f"""
    MATCH (center:{obj_type.neo4j_label} {{node_id: $node_id, tenant_id: $tenant_id}})
    OPTIONAL MATCH path = (center)-[r*1..{cypher_depth}]-(connected)
    WHERE NOT type(r) IN ['TENANT', 'CREATED_BY']
    WITH center, collect(DISTINCT nodes(path)) as all_nodes, collect(DISTINCT relationships(path)) as all_rels
    UNWIND all_nodes as n UNWIND all_rels as rel
    WITH center, collect(DISTINCT n) as nodes, collect(DISTINCT rel) as rels
    RETURN center, nodes, rels
    """
    
    try:
        graph_result = await neo4j_client.execute_query(
            cypher,
            {"node_id": obj.neo4j_node_id, "tenant_id": str(tenant_id)}
        )
    except Exception as e:
        logger.error(f"Subgraph query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Graph query failed: {str(e)}")
    
    nodes = []
    edges = []
    
    if graph_result and len(graph_result) > 0:
        record = graph_result[0]
        center = record.get("center", {})
        graph_nodes = record.get("nodes", []) or []
        graph_rels = record.get("rels", []) or []
        
        node_map = {}
        type_cache = {}
        
        for n in [center] + list(graph_nodes):
            if not n:
                continue
            nid = n.get("node_id", n.get("id", "unknown"))
            if nid in node_map:
                continue
            node_map[nid] = True
            
            obj_type_name = "Unknown"
            if n.get("object_type_id"):
                type_id = str(UUID(n["object_type_id"]))
                if type_id in type_cache:
                    obj_type_name = type_cache[type_id]
                else:
                    obj_type_result = await db.execute(
                        select(OntologyObjectType).where(OntologyObjectType.id == UUID(type_id))
                    )
                    ot = obj_type_result.scalar_one_or_none()
                    if ot:
                        obj_type_name = ot.name
                        type_cache[type_id] = obj_type_name
            
            label = n.get("object_key", n.get("name", n.get("id", "")))
            nodes.append(GraphNode(
                id=nid,
                object_id=n.get("object_id", n.get("id", "")),
                object_type=obj_type_name,
                label=label,
                properties=n
            ))
        
        for rel in graph_rels:
            if not rel:
                continue
            rel_id = rel.get("rel_id", rel.get("id", str(uuid.uuid4())))
            edges.append(GraphEdge(
                id=rel_id,
                source=rel.get("start", ""),
                target=rel.get("end", ""),
                type=rel.get("type", "RELATED"),
                properties=rel
            ))
    
    query_time_ms = int(time.time() * 1000) - start_time
    
    return SubgraphResponse(
        nodes=nodes,
        edges=edges,
        metadata=GraphMetadata(
            center_object_id=object_id,
            depth=depth,
            total_nodes=len(nodes),
            total_edges=len(edges),
            query_time_ms=query_time_ms
        )
    )


@router.post("/link-types", response_model=LinkTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_link_type(
    link_type_data: LinkTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new Link Type"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.id == link_type_data.source_object_type_id,
            OntologyObjectType.tenant_id == tenant_id
        )
    )
    source_type = result.scalar_one_or_none()
    if not source_type:
        raise HTTPException(status_code=404, detail="Source Object Type not found")
    
    result = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.id == link_type_data.target_object_type_id,
            OntologyObjectType.tenant_id == tenant_id
        )
    )
    target_type = result.scalar_one_or_none()
    if not target_type:
        raise HTTPException(status_code=404, detail="Target Object Type not found")
    
    existing = await db.execute(
        select(OntologyLinkType).where(
            OntologyLinkType.tenant_id == tenant_id,
            OntologyLinkType.name == link_type_data.name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Link Type '{link_type_data.name}' already exists")
    
    neo4j_edge = link_type_data.neo4j_edge_type or link_type_data.name.upper().replace(" ", "_")
    neo4j_props = [p.model_dump() for p in link_type_data.properties]
    
    link_type = OntologyLinkType(
        tenant_id=tenant_id,
        name=link_type_data.name,
        display_name=link_type_data.display_name,
        description=link_type_data.description,
        source_object_type_id=link_type_data.source_object_type_id,
        target_object_type_id=link_type_data.target_object_type_id,
        cardinality=link_type_data.cardinality,
        neo4j_edge_type=neo4j_edge,
        neo4j_properties=neo4j_props,
        status="active",
        created_by=UUID(current_user.id) if current_user.id else None
    )
    
    db.add(link_type)
    await db.flush()
    await db.refresh(link_type)
    
    return LinkTypeResponse(
        id=link_type.id,
        tenant_id=link_type.tenant_id,
        name=link_type.name,
        display_name=link_type.display_name,
        description=link_type.description,
        source_object_type_id=link_type.source_object_type_id,
        source_object_type_name=source_type.name,
        target_object_type_id=link_type.target_object_type_id,
        target_object_type_name=target_type.name,
        cardinality=link_type.cardinality,
        neo4j_edge_type=link_type.neo4j_edge_type,
        neo4j_properties=[PropertyDef(**p) for p in link_type.neo4j_properties],
        status=link_type.status,
        version=link_type.version,
        created_at=link_type.created_at,
        updated_at=link_type.updated_at
    )


@router.get("/link-types", response_model=LinkTypeListResponse)
async def list_link_types(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """List Link Types"""
    tenant_id = await _get_tenant_id(current_user)
    
    query = select(OntologyLinkType).where(OntologyLinkType.tenant_id == tenant_id)
    
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    query = query.order_by(OntologyLinkType.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    link_types = result.scalars().all()
    
    items = []
    for lt in link_types:
        source_result = await db.execute(
            select(OntologyObjectType.name).where(OntologyObjectType.id == lt.source_object_type_id)
        )
        target_result = await db.execute(
            select(OntologyObjectType.name).where(OntologyObjectType.id == lt.target_object_type_id)
        )
        source_name = source_result.scalar_one_or_none() or "Unknown"
        target_name = target_result.scalar_one_or_none() or "Unknown"
        
        items.append(LinkTypeResponse(
            id=lt.id,
            tenant_id=lt.tenant_id,
            name=lt.name,
            display_name=lt.display_name,
            description=lt.description,
            source_object_type_id=lt.source_object_type_id,
            source_object_type_name=source_name,
            target_object_type_id=lt.target_object_type_id,
            target_object_type_name=target_name,
            cardinality=lt.cardinality,
            neo4j_edge_type=lt.neo4j_edge_type,
            neo4j_properties=[PropertyDef(**p) for p in lt.neo4j_properties],
            status=lt.status,
            version=lt.version,
            created_at=lt.created_at,
            updated_at=lt.updated_at
        ))
    
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return LinkTypeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.post("/link-types/{link_type_id}/links", response_model=OntologyLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_ontology_link(
    link_type_id: UUID,
    link_data: OntologyLinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a relationship instance between two objects"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyLinkType).where(
            OntologyLinkType.id == link_type_id,
            OntologyLinkType.tenant_id == tenant_id
        )
    )
    link_type = result.scalar_one_or_none()
    
    if not link_type:
        raise HTTPException(status_code=404, detail="Link Type not found")
    
    source_result = await db.execute(
        select(OntologyObject).where(
            OntologyObject.id == link_data.source_object_id,
            OntologyObject.tenant_id == tenant_id
        )
    )
    source_obj = source_result.scalar_one_or_none()
    if not source_obj:
        raise HTTPException(status_code=404, detail="Source Object not found")
    
    target_result = await db.execute(
        select(OntologyObject).where(
            OntologyObject.id == link_data.target_object_id,
            OntologyObject.tenant_id == tenant_id
        )
    )
    target_obj = target_result.scalar_one_or_none()
    if not target_obj:
        raise HTTPException(status_code=404, detail="Target Object not found")
    
    rel_id = f"rel_{uuid.uuid4().hex[:12]}"
    
    source_type_result = await db.execute(
        select(OntologyObjectType).where(OntologyObjectType.id == source_obj.object_type_id)
    )
    source_type = source_type_result.scalar_one_or_none()
    
    target_type_result = await db.execute(
        select(OntologyObjectType).where(OntologyObjectType.id == target_obj.object_type_id)
    )
    target_type = target_type_result.scalar_one_or_none()
    
    cypher = f"""
    MATCH (source:{source_type.neo4j_label} {{node_id: $source_node_id, tenant_id: $tenant_id}})
    MATCH (target:{target_type.neo4j_label} {{node_id: $target_node_id, tenant_id: $tenant_id}})
    CREATE (source)-[r:{link_type.neo4j_edge_type} {{
        rel_id: $rel_id,
        properties: $properties,
        created_at: $created_at
    }}]->(target)
    RETURN r.rel_id as rel_id
    """
    
    try:
        await neo4j_client.execute_query(
            cypher,
            {
                "source_node_id": source_obj.neo4j_node_id,
                "target_node_id": target_obj.neo4j_node_id,
                "tenant_id": str(tenant_id),
                "rel_id": rel_id,
                "properties": link_data.properties,
                "created_at": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Neo4j relationship creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create relationship: {str(e)}")
    
    ontology_link = OntologyLink(
        tenant_id=tenant_id,
        link_type_id=link_type_id,
        source_object_id=link_data.source_object_id,
        target_object_id=link_data.target_object_id,
        properties=link_data.properties,
        neo4j_rel_id=rel_id,
        source_type="manual",
        created_by=UUID(current_user.id) if current_user.id else None
    )
    
    db.add(ontology_link)
    await db.flush()
    await db.refresh(ontology_link)
    
    return OntologyLinkResponse(
        id=ontology_link.id,
        tenant_id=ontology_link.tenant_id,
        link_type_id=link_type_id,
        link_type_name=link_type.name,
        source_object_id=link_data.source_object_id,
        target_object_id=link_data.target_object_id,
        properties=ontology_link.properties,
        neo4j_rel_id=ontology_link.neo4j_rel_id,
        created_at=ontology_link.created_at
    )


@router.post("/search", response_model=OntologySearchResponse)
async def search_ontology(
    search_request: OntologySearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Semantic search across Ontology objects"""
    from app.services.semantic_search import search_ontology as do_search
    tenant_id = await _get_tenant_id(current_user)
    return await do_search(db, tenant_id, search_request)


@router.post("/compile", response_model=CompileResult)
async def compile_ontology(
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Full compile of all Ontology definitions"""
    from app.services.ontology_compiler import compile_ontology as do_compile
    tenant_id = await _get_tenant_id(current_user)
    executed_by = UUID(current_user.id) if current_user.id else None
    return await do_compile(db, tenant_id, executed_by)


@router.post("/compile/validate", response_model=ValidationResponse)
async def validate_ontology(
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Run static validation on all ontology definitions."""
    from app.services.ontology_service import OntologyService
    tenant_id = await _get_tenant_id(current_user)
    service = OntologyService(db, tenant_id)
    errors = await service.validate_all()
    return ValidationResponse(
        is_valid=len(errors) == 0,
        errors=errors,
        error_count=len(errors),
        warning_count=0,
    )


@router.get("/dag/cycle", response_model=DAGCycleResponse)
async def detect_dag_cycle(
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Detect cycles in ontology dependencies."""
    from app.services.ontology_service import OntologyService
    tenant_id = await _get_tenant_id(current_user)
    service = OntologyService(db, tenant_id)
    cycle = await service.detect_cycles()
    if cycle:
        cycle_str = " -> ".join(str(n)[:8] for n in cycle)
        return DAGCycleResponse(
            has_cycle=True,
            cycle_path=[str(n) for n in cycle],
            cycle_description=f"Circular dependency detected: {cycle_str}",
        )
    return DAGCycleResponse(has_cycle=False)