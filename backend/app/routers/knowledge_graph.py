from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
import logging
import re
import uuid
from datetime import datetime

from app.core.config import settings
from app.models.schemas import (
    EntityCreate, EntityResponse, EntityUpdate,
    RelationshipCreate, RelationshipResponse,
    GraphQueryRequest, GraphQueryResponse,
    SearchRequest, SearchResult
)
from app.services.neo4j_client import neo4j_client
from app.routers.auth import get_current_user, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-graph", tags=["Knowledge Graph"])


@router.post("/entities", response_model=EntityResponse, status_code=status.HTTP_201_CREATED)
async def create_entity(
    entity_data: EntityCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new entity in the knowledge graph"""
    entity_id = str(uuid.uuid4())
    
    try:
        # Create entity in Neo4j
        query = """
        CREATE (e:Entity {
            id: $id,
            name: $name,
            type: $type,
            description: $description,
            properties: $properties,
            created_at: $created_at,
            created_by: $created_by,
            tenant_id: $tenant_id
        })
        RETURN e
        """
        
        result = await neo4j_client.execute_query(
            query,
            {
                "id": entity_id,
                "name": entity_data.name,
                "type": entity_data.type,
                "description": entity_data.description or "",
                "properties": entity_data.properties or {},
                "created_at": datetime.utcnow().isoformat(),
                "created_by": current_user.username,
                "tenant_id": current_user.tenant_id
            }
        )
        
        logger.info(f"Entity created: {entity_id} ({entity_data.name})")
        
        return EntityResponse(
            id=entity_id,
            name=entity_data.name,
            type=entity_data.type,
            description=entity_data.description,
            properties=entity_data.properties or {},
            created_at=datetime.utcnow().isoformat(),
            created_by=current_user.username
        )
    except Exception as e:
        logger.error(f"Failed to create entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get an entity by ID"""
    try:
        query = """
        MATCH (e:Entity {id: $id, tenant_id: $tenant_id})
        RETURN e
        """
        
        result = await neo4j_client.execute_query(query, {"id": entity_id, "tenant_id": current_user.tenant_id})
        
        if not result or len(result) == 0:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        entity_data = result[0]["e"]
        return EntityResponse(
            id=entity_data["id"],
            name=entity_data["name"],
            type=entity_data["type"],
            description=entity_data.get("description"),
            properties=entity_data.get("properties", {}),
            created_at=entity_data.get("created_at"),
            created_by=entity_data.get("created_by")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/entities/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: str,
    entity_data: EntityUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update an existing entity"""
    try:
        query = """
        MATCH (e:Entity {id: $id, tenant_id: $tenant_id})
        SET e.name = COALESCE($name, e.name),
            e.description = COALESCE($description, e.description),
            e.properties = COALESCE($properties, e.properties),
            e.updated_at = $updated_at,
            e.updated_by = $updated_by
        RETURN e
        """
        
        result = await neo4j_client.execute_query(
            query,
            {
                "id": entity_id,
                "name": entity_data.name,
                "description": entity_data.description,
                "properties": entity_data.properties,
                "updated_at": datetime.utcnow().isoformat(),
                "updated_by": current_user.username,
                "tenant_id": current_user.tenant_id
            }
        )
        
        if not result or len(result) == 0:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        updated_entity = result[0]["e"]
        logger.info(f"Entity updated: {entity_id}")
        
        return EntityResponse(
            id=updated_entity["id"],
            name=updated_entity["name"],
            type=updated_entity["type"],
            description=updated_entity.get("description"),
            properties=updated_entity.get("properties", {}),
            created_at=updated_entity.get("created_at"),
            created_by=updated_entity.get("created_by")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    entity_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete an entity"""
    try:
        query = """
        MATCH (e:Entity {id: $id, tenant_id: $tenant_id})
        DETACH DELETE e
        """
        
        await neo4j_client.execute_query(query, {"id": entity_id, "tenant_id": current_user.tenant_id})
        logger.info(f"Entity deleted: {entity_id}")
    except Exception as e:
        logger.error(f"Failed to delete entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    relationship_data: RelationshipCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new relationship between entities"""
    relationship_id = str(uuid.uuid4())
    
    try:
        query = """
        MATCH (source:Entity {id: $source_id, tenant_id: $tenant_id})
        MATCH (target:Entity {id: $target_id, tenant_id: $tenant_id})
        CREATE (source)-[r:RELATIONSHIP {
            id: $id,
            type: $type,
            properties: $properties,
            created_at: $created_at,
            created_by: $created_by
        }]->(target)
        RETURN r
        """
        
        result = await neo4j_client.execute_query(
            query,
            {
                "id": relationship_id,
                "source_id": relationship_data.source_entity_id,
                "target_id": relationship_data.target_entity_id,
                "type": relationship_data.type,
                "properties": relationship_data.properties or {},
                "created_at": datetime.utcnow().isoformat(),
                "created_by": current_user.username,
                "tenant_id": current_user.tenant_id
            }
        )
        
        logger.info(f"Relationship created: {relationship_id}")
        
        return RelationshipResponse(
            id=relationship_id,
            source_entity_id=relationship_data.source_entity_id,
            target_entity_id=relationship_data.target_entity_id,
            type=relationship_data.type,
            properties=relationship_data.properties or {},
            created_at=datetime.utcnow().isoformat(),
            created_by=current_user.username
        )
    except Exception as e:
        logger.error(f"Failed to create relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/relationships/{relationship_id}", response_model=RelationshipResponse)
async def get_relationship(
    relationship_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a relationship by ID"""
    try:
        query = """
        MATCH ()-[r:RELATIONSHIP {id: $id}]-()
        RETURN r
        """
        
        result = await neo4j_client.execute_query(query, {"id": relationship_id})
        
        if not result or len(result) == 0:
            raise HTTPException(status_code=404, detail="Relationship not found")
        
        rel_data = result[0]["r"]
        return RelationshipResponse(
            id=rel_data["id"],
            source_entity_id=rel_data["source_id"],
            target_entity_id=rel_data["target_id"],
            type=rel_data["type"],
            properties=rel_data.get("properties", {}),
            created_at=rel_data.get("created_at"),
            created_by=rel_data.get("created_by")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relationship(
    relationship_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a relationship"""
    try:
        query = """
        MATCH ()-[r:RELATIONSHIP {id: $id}]-()
        DELETE r
        """
        
        await neo4j_client.execute_query(query, {"id": relationship_id})
        logger.info(f"Relationship deleted: {relationship_id}")
    except Exception as e:
        logger.error(f"Failed to delete relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Cypher whitelist: only these starting keywords are allowed in read-only endpoint
# This prevents ALL write operations, including those hidden in subqueries or comments
_CYPHER_ALLOWED_STARTS = {"MATCH", "WITH", "RETURN", "CALL", "UNWIND", "OPTIONAL"}

# Dangerous keywords that indicate write operations anywhere in the query
_CYPHER_FORBIDDEN_KEYWORDS = {"CREATE", "SET", "DELETE", "DETACH", "REMOVE", "MERGE", "DROP", "LOAD"}


def _validate_readonly_cypher(query: str) -> tuple[bool, str]:
    """
    Validate Cypher query using whitelist + blacklist approach.
    
    Whitelist: query MUST start with one of the allowed keywords.
    Blacklist: query MUST NOT contain any forbidden write-operation keywords.
    
    Returns (is_valid, error_message).
    """
    # Normalize: remove leading whitespace and comments (single-line comments after //)
    lines = query.strip().split('\n')
    cleaned_lines = []
    for line in lines:
        # Remove single-line comments (// style)
        if '//' in line:
            line = line[:line.index('//')]
        cleaned_lines.append(line)
    cleaned = ' '.join(cleaned_lines).strip()
    
    if not cleaned:
        return False, "Empty query"
    
    upper_cleaned = cleaned.upper()
    
    # Check 1: Must start with allowed keyword (whitelist)
    first_word = upper_cleaned.split()[0] if upper_cleaned.split() else ""
    # Handle OPTIONAL MATCH → first meaningful keyword is MATCH
    if first_word == "OPTIONAL":
        words = upper_cleaned.split()
        first_word = words[1] if len(words) > 1 else ""
    
    if first_word not in _CYPHER_ALLOWED_STARTS:
        return False, f"Query must start with one of: {', '.join(_CYPHER_ALLOWED_STARTS)}. Got: '{first_word}'"
    
    # Check 2: Must NOT contain forbidden keywords (blacklist as secondary defense)
    # We split on word boundaries to avoid false positives in property names
    words = re.findall(r'\b[A-Z]+\b', upper_cleaned)
    for keyword in _CYPHER_FORBIDDEN_KEYWORDS:
        if keyword in words:
            return False, f"Forbidden write operation detected: '{keyword}'. Only read operations are allowed."
    
    return True, ""


@router.post("/query", response_model=GraphQueryResponse)
async def query_graph(
    query_request: GraphQueryRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """Execute a custom read-only Cypher query on the knowledge graph"""
    is_valid, error_msg = _validate_readonly_cypher(query_request.cypher_query)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid Cypher query: {error_msg}"
        )
    
    try:
        result = await neo4j_client.execute_query(
            query_request.cypher_query,
            {**query_request.parameters, "tenant_id": current_user.tenant_id}
        )
        
        return GraphQueryResponse(
            data=result,
            total=len(result)
        )
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(status_code=400, detail=f"Query error: {str(e)}")


@router.post("/search", response_model=SearchResult)
async def search_knowledge(
    search_request: SearchRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """Search for entities and documents"""
    try:
        # Search entities
        entity_query = """
        MATCH (e:Entity {tenant_id: $tenant_id})
        WHERE e.name CONTAINS $query OR e.description CONTAINS $query OR e.type CONTAINS $query
        RETURN e
        LIMIT $limit
        """
        
        entities_result = await neo4j_client.execute_query(
            entity_query,
            {
                "query": search_request.query,
                "limit": search_request.limit,
                "tenant_id": current_user.tenant_id
            }
        )
        
        entities = []
        for record in entities_result:
            e = record["e"]
            entities.append(EntityResponse(
                id=e["id"],
                name=e["name"],
                type=e["type"],
                description=e.get("description"),
                properties=e.get("properties", {}),
                created_at=e.get("created_at"),
                created_by=e.get("created_by")
            ))
        
        # In production, also search documents from PostgreSQL/MinIO
        documents = []
        
        return SearchResult(
            entities=entities,
            documents=documents,
            total=len(entities) + len(documents)
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/explore/{entity_id}", response_model=Dict[str, Any])
async def explore_entity_connections(
    entity_id: str,
    depth: int = 2,
    current_user: UserResponse = Depends(get_current_user)
):
    """Explore connections of an entity up to specified depth"""
    try:
        query = """
        MATCH (e:Entity {id: $id, tenant_id: $tenant_id})
        OPTIONAL MATCH path = (e)-[*1..$depth]-(connected)
        WHERE connected.tenant_id = $tenant_id
        RETURN e, collect(DISTINCT connected) as connections, collect(DISTINCT path) as paths
        """
        
        result = await neo4j_client.execute_query(
            query,
            {"id": entity_id, "depth": depth, "tenant_id": current_user.tenant_id}
        )
        
        if not result or len(result) == 0:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        return {
            "entity": result[0]["e"],
            "connections": result[0]["connections"],
            "total_connections": len(result[0]["connections"])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to explore entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))