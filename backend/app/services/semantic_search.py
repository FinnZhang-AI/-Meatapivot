import logging
import time
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ontology_models import OntologyObject, OntologyObjectType
from app.models.ontology_schemas import (
    OntologySearchRequest, OntologySearchResponse, SearchResultItem
)
from app.services.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


class SemanticSearchService:
    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
    
    async def search(
        self,
        query: str,
        object_types: Optional[List[str]] = None,
        search_mode: str = "hybrid",
        top_k: int = 20,
        explain: bool = False
    ) -> OntologySearchResponse:
        """Hybrid search combining vector and graph retrieval"""
        start_time = int(time.time() * 1000)
        
        vector_results = []
        graph_results = []
        
        if search_mode in ("vector", "hybrid"):
            vector_results = await self._vector_search(query, object_types, top_k)
        
        if search_mode in ("graph", "hybrid", "keyword"):
            graph_results = await self._graph_search(query, object_types, top_k)
        
        combined = self._merge_results(vector_results, graph_results)
        
        if len(combined) > top_k:
            combined = combined[:top_k]
        
        reranked = False
        if len(vector_results) > 0 and len(graph_results) > 0:
            combined = self._rerank_rrf(combined)
            reranked = True
        
        duration_ms = int(time.time() * 1000) - start_time
        
        return OntologySearchResponse(
            query=query,
            results=combined,
            total=len(combined),
            vector_hits=len(vector_results),
            graph_hits=len(graph_results),
            reranked=reranked,
            duration_ms=duration_ms
        )
    
    async def _vector_search(
        self,
        query: str,
        object_types: Optional[List[str]],
        top_k: int
    ) -> List[SearchResultItem]:
        """Vector similarity search (placeholder for Milvus integration)"""
        logger.info(f"Vector search called with query: {query}, types: {object_types}")
        
        return []
    
    async def _graph_search(
        self,
        query: str,
        object_types: Optional[List[str]],
        top_k: int
    ) -> List[SearchResultItem]:
        """Graph-based keyword + relationship search"""
        results = []
        
        tenant_id_str = str(self.tenant_id)
        
        type_filter = ""
        params = {
            "query": query.lower(),
            "tenant_id": tenant_id_str,
            "limit": top_k
        }
        
        if object_types:
            type_placeholders = [f":{ot.upper()}" for ot in object_types]
            type_filter = f"AND coalesce(n._object_type, n.label) IN ({','.join(type_placeholders)})"
        
        cypher = f"""
        MATCH (n)
        WHERE n.tenant_id = $tenant_id
          AND (
            toLower(coalesce(n.object_key, n.name, '')) CONTAINS $query
            OR toLower(coalesce(n.description, '')) CONTAINS $query
          )
          {type_filter}
        RETURN n, n.object_key as object_key, labels(n)[0] as object_type
        LIMIT $limit
        """
        
        try:
            graph_result = await neo4j_client.execute_query(cypher, params)
            
            for record in graph_result:
                n = record.get("n", {})
                if not n:
                    continue
                
                object_type = record.get("object_type", "Unknown")
                object_key = record.get("object_key", n.get("object_key", n.get("name", "")))
                
                obj_id = n.get("object_id", n.get("id", ""))
                
                score = 0.5
                if query.lower() in str(object_key).lower():
                    score = 0.9
                elif query.lower() in str(n.get("description", "")).lower():
                    score = 0.6
                
                results.append(SearchResultItem(
                    object_id=obj_id,
                    object_type=object_type,
                    object_key=object_key,
                    label=object_key,
                    score=score,
                    source="graph",
                    explanation=f"Matched keyword '{query}' in {'object_key' if score > 0.7 else 'description'}",
                    properties_preview=n
                ))
                
        except Exception as e:
            logger.error(f"Graph search failed: {e}")
        
        return results
    
    def _merge_results(
        self,
        vector_results: List[SearchResultItem],
        graph_results: List[SearchResultItem]
    ) -> List[SearchResultItem]:
        """Merge vector and graph results, deduplicating by object_id"""
        merged = {}
        
        for item in vector_results:
            key = f"{item.object_type}:{item.object_key}"
            if key not in merged or item.score > merged[key].score:
                merged[key] = item
        
        for item in graph_results:
            key = f"{item.object_type}:{item.object_key}"
            if key not in merged or item.score > merged[key].score:
                merged[key] = item
        
        return list(merged.values())
    
    def _rerank_rrf(self, results: List[SearchResultItem], k: int = 60) -> List[SearchResultItem]:
        """Reciprocal Rank Fusion for result re-ranking"""
        if not results:
            return results
        
        rrf_scores: Dict[str, float] = {}
        
        for idx, item in enumerate(results):
            key = f"{item.object_type}:{item.object_key}"
            rank = idx + 1
            
            source_weight = 1.0
            if item.source == "vector":
                source_weight = 1.2
            elif item.source == "graph":
                source_weight = 1.0
            
            rrf_score = source_weight / (k + rank)
            
            if key in rrf_scores:
                rrf_scores[key] += rrf_score
            else:
                rrf_scores[key] = rrf_score
        
        for item in results:
            key = f"{item.object_type}:{item.object_key}"
            item.score = rrf_scores[key]
        
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results


async def search_ontology(
    db: AsyncSession,
    tenant_id: UUID,
    request: OntologySearchRequest
) -> OntologySearchResponse:
    """Public API for Ontology semantic search"""
    search_service = SemanticSearchService(db, tenant_id)
    return await search_service.search(
        query=request.query,
        object_types=request.object_types,
        search_mode=request.search_mode,
        top_k=request.top_k,
        explain=request.explain
    )