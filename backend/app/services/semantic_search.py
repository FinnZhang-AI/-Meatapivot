import json
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
from app.services.milvus_client import milvus_client
from app.services.llm_gateway import llm_gateway
from app.core.config import settings

logger = logging.getLogger(__name__)

# Optional BGE-Reranker dependency - import with fallback
try:
    from sentence_transformers import CrossEncoder
    _RERANKER_AVAILABLE = True
except Exception as e:
    logger.debug(f"sentence-transformers not available: {e}")
    CrossEncoder = None
    _RERANKER_AVAILABLE = False

# Optional llama-index dependency - import with fallback
try:
    from llama_index.core import Settings
    _LLAMA_INDEX_AVAILABLE = True
except Exception as e:
    logger.debug(f"llama-index not available: {e}")
    Settings = None
    _LLAMA_INDEX_AVAILABLE = False


class SemanticSearchService:
    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self._reranker: Optional[Any] = None
        self._init_reranker()
    
    def _init_reranker(self) -> None:
        """Lazy-load BGE-Reranker-v2-m3 with graceful fallback."""
        if not _RERANKER_AVAILABLE or CrossEncoder is None:
            return
        try:
            # Use a small, commonly cached reranker model
            self._reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")
            logger.debug("BGE-Reranker initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize BGE-Reranker: {e}")
            self._reranker = None
    
    async def search(
        self,
        query: str,
        object_types: Optional[List[str]] = None,
        search_mode: str = "hybrid",
        top_k: int = 20,
        explain: bool = False,
        use_reranker: bool = True,
    ) -> OntologySearchResponse:
        """Hybrid search combining vector, graph, LLM entity extraction, and BGE reranking."""
        start_time = int(time.time() * 1000)
        
        # Optional: extract ontology object types from the query
        inferred_types = await self._infer_object_types(query)
        if inferred_types:
            object_types = object_types or inferred_types
        
        vector_results = []
        graph_results = []
        
        if search_mode in ("vector", "hybrid"):
            vector_results = await self._vector_search(query, object_types, top_k)
        
        if search_mode in ("graph", "hybrid", "keyword"):
            graph_results = await self._graph_search(query, object_types, top_k)
        
        combined = self._merge_results(vector_results, graph_results)
        reranked = False
        
        if use_reranker and self._reranker is not None and combined:
            try:
                combined = self._rerank_with_bge(query, combined)
                reranked = True
            except Exception as e:
                logger.warning(f"BGE reranking failed, falling back to RRF: {e}")
                combined = self._rerank_rrf(combined)
                reranked = True
        elif len(vector_results) > 0 and len(graph_results) > 0:
            combined = self._rerank_rrf(combined)
            reranked = True
        
        if len(combined) > top_k:
            combined = combined[:top_k]
        
        # Enrich explanations with source info
        for item in combined:
            item.explanation = self._build_explanation(item, reranked)
        
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
    
    async def _infer_object_types(self, query: str) -> Optional[List[str]]:
        """Use LLM to extract relevant Ontology Object Types from the query."""
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an ontology analyzer. Given a user query, return a JSON array "
                        "of ontology object type names that are most relevant. Return [] if none. "
                        "Example: [\"Customer\", \"Order\"]"
                    ),
                },
                {"role": "user", "content": f"Query: {query}\nObject types:"},
            ]
            result = await llm_gateway.chat(
                messages=messages,
                model=settings.DEFAULT_LLM_MODEL,
                temperature=0.0,
                max_tokens=128,
            )
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "[]")
            # Strip markdown code fences if present
            content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            types = json.loads(content)
            if isinstance(types, list):
                return [str(t).strip() for t in types if t]
        except Exception as e:
            logger.debug(f"Object type inference failed: {e}")
        return None
    
    async def _vector_search(
        self,
        query: str,
        object_types: Optional[List[str]],
        top_k: int
    ) -> List[SearchResultItem]:
        """Vector similarity search via Milvus"""
        logger.info(f"Vector search called with query: {query}, types: {object_types}")
        results = []
        try:
            hits = milvus_client.search(
                tenant_id=self.tenant_id,
                query_text=query,
                top_k=top_k,
                object_types=object_types,
            )
            for hit in hits:
                results.append(SearchResultItem(
                    object_id=hit["object_id"],
                    object_type=hit["object_type"],
                    object_key=hit["metadata"].get("object_key", hit["object_id"]),
                    label=hit["metadata"].get("object_key", hit["object_id"]),
                    score=hit["score"],
                    source="vector",
                    explanation=f"Vector similarity score {hit['score']:.3f}",
                    properties_preview=hit["metadata"],
                ))
        except Exception as e:
            logger.warning(f"Vector search unavailable (Milvus error): {e}")
        return results
    
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
    
    def _rerank_with_bge(self, query: str, results: List[SearchResultItem]) -> List[SearchResultItem]:
        """Rerank results using BGE-Reranker-v2-m3."""
        if not self._reranker or not results:
            return results
        
        pairs = [
            (query, f"{r.object_type} {r.object_key} {json.dumps(r.properties_preview, ensure_ascii=False)[:500]}")
            for r in results
        ]
        scores = self._reranker.predict(pairs)
        for item, score in zip(results, scores):
            item.score = float(score)
            item.source = f"{item.source}+rerank"
        results.sort(key=lambda x: x.score, reverse=True)
        return results
    
    def _rerank_rrf(self, results: List[SearchResultItem], k: int = 60) -> List[SearchResultItem]:
        """Reciprocal Rank Fusion fallback for result re-ranking"""
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
    
    def _build_explanation(self, item: SearchResultItem, reranked: bool) -> str:
        """Build human-readable explanation for a search result."""
        source = item.source
        if reranked:
            return f"Reranked {source} match (score {item.score:.3f})"
        return item.explanation or f"{source} match (score {item.score:.3f})"


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
