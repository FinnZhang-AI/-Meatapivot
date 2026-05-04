from neo4j import AsyncGraphDatabase
from app.core.config import settings
import logging
from typing import List, Dict, Any, Optional
import json

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self):
        self.driver = None
        self.connected = False
    
    async def connect(self):
        """Initialize Neo4j connection"""
        try:
            self.driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_pool_size=50
            )
            # Verify connection
            await self.driver.verify_connectivity()
            self.connected = True
            logger.info(f"Connected to Neo4j at {settings.NEO4J_URI}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    async def close(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()
            self.connected = False
            logger.info("Neo4j connection closed")
    
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute Cypher query and return results"""
        if not self.connected:
            raise RuntimeError("Neo4j not connected")
        
        try:
            async with self.driver.session() as session:
                result = await session.run(query, params or {})
                records = []
                async for record in result:
                    records.append(dict(record))
                return records
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    async def create_entity(self, entity_id: str, entity_type: str, properties: Dict[str, Any], tenant_id: str) -> Dict:
        """Create a node in knowledge graph"""
        query = """
        MERGE (n:Entity {id: $entity_id, tenant_id: $tenant_id})
        SET n += $properties
        SET n.entity_type = $entity_type
        SET n.created_at = datetime()
        SET n.updated_at = datetime()
        RETURN n
        """
        results = await self.execute_query(query, {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "properties": properties,
            "tenant_id": tenant_id
        })
        return results[0]['n'] if results else None
    
    async def create_relationship(self, source_id: str, target_id: str, rel_type: str, 
                                  properties: Dict[str, Any], tenant_id: str) -> Dict:
        """Create a relationship between two nodes"""
        query = """
        MATCH (source:Entity {id: $source_id, tenant_id: $tenant_id})
        MATCH (target:Entity {id: $target_id, tenant_id: $tenant_id})
        CALL apoc.merge.relationship(source, $rel_type, {}, $properties, target) YIELD rel
        SET rel.created_at = datetime()
        RETURN rel
        """
        results = await self.execute_query(query, {
            "source_id": source_id,
            "target_id": target_id,
            "rel_type": rel_type,
            "properties": properties,
            "tenant_id": tenant_id
        })
        return results[0]['r'] if results else None
    
    async def get_entity(self, entity_id: str, tenant_id: str) -> Optional[Dict]:
        """Get entity by ID"""
        query = """
        MATCH (n:Entity {id: $entity_id, tenant_id: $tenant_id})
        OPTIONAL MATCH (n)-[r]-(connected)
        RETURN n, collect(DISTINCT {
            id: connected.id,
            type: labels(connected)[0],
            relationship: type(r),
            direction: CASE WHEN id(n) < id(connected) THEN 'outgoing' ELSE 'incoming' END
        }) as relationships
        """
        results = await self.execute_query(query, {"entity_id": entity_id, "tenant_id": tenant_id})
        if results:
            return results[0]
        return None
    
    async def search_entities(self, query_text: str, tenant_id: str, limit: int = 20) -> List[Dict]:
        """Full-text search for entities"""
        query = """
        CALL db.index.fulltext.queryNodes('entity_fulltext', $query_text) YIELD node, score
        WHERE node.tenant_id = $tenant_id
        RETURN node, score
        ORDER BY score DESC
        LIMIT $limit
        """
        results = await self.execute_query(query, {
            "query_text": query_text,
            "tenant_id": tenant_id,
            "limit": limit
        })
        return results
    
    async def get_graph_data(self, tenant_id: str, entity_types: Optional[List[str]] = None, 
                             limit: int = 100) -> Dict[str, Any]:
        """Get graph data for visualization"""
        type_filter = ""
        if entity_types:
            type_filter = "AND n.entity_type IN $entity_types"
            
        query = f"""
        MATCH (n:Entity {{tenant_id: $tenant_id}})
        WHERE true {type_filter}
        WITH n LIMIT $limit
        MATCH (n)-[r]-(connected:Entity {{tenant_id: $tenant_id}})
        RETURN 
            collect(DISTINCT {{
                id: n.id,
                label: n.name,
                type: n.entity_type,
                properties: n {{ .*, id: '', tenant_id: '', created_at: '', updated_at: '' }}
            }}) as nodes,
            collect(DISTINCT {{
                source: startNode(r).id,
                target: endNode(r).id,
                type: type(r),
                properties: r {{ .*, created_at: '' }}
            }}) as edges
        """
        params = {"tenant_id": tenant_id, "limit": limit}
        if entity_types:
            params["entity_types"] = entity_types
            
        results = await self.execute_query(query, params)
        if results:
            return {
                "nodes": results[0].get('nodes', []),
                "edges": results[0].get('edges', [])
            }
        return {"nodes": [], "edges": []}
    
    async def create_fulltext_index(self):
        """Create full-text index for entity search"""
        query = """
        CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
        FOR (n:Entity) ON EACH [n.name, n.description]
        """
        try:
            await self.execute_query(query)
            logger.info("Full-text index created successfully")
        except Exception as e:
            logger.warning(f"Index creation note: {e}")


# Global Neo4j client instance
neo4j_client = Neo4jClient()