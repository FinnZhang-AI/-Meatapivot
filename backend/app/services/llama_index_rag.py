"""LlamaIndex RAG integration - optional enhanced RAG pipeline.

This module provides a LlamaIndex-based query engine that can be used as an
optional backend for RAG. It falls back to the native pipeline if dependencies
are unavailable.
"""

import asyncio
import logging
from typing import List, Optional

from app.models.ontology_schemas import SearchResultItem

logger = logging.getLogger(__name__)

# Optional llama-index dependencies - import with fallback
try:
    from llama_index.core import Document, Settings, VectorStoreIndex
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core.schema import TextNode
    _LLAMA_INDEX_AVAILABLE = True
except Exception as e:
    logger.debug(f"llama-index not available: {e}")
    Document = None
    Settings = None
    VectorStoreIndex = None
    SentenceSplitter = None
    TextNode = None
    _LLAMA_INDEX_AVAILABLE = False


def is_available() -> bool:
    return _LLAMA_INDEX_AVAILABLE


async def query_with_llama_index(
    query: str,
    search_results: List[SearchResultItem],
    system_prompt: Optional[str] = None,
) -> Optional[str]:
    """Use LlamaIndex to synthesize an answer from retrieved ontology objects.

    Falls back to None if llama-index is not available or fails, so the caller
    can use the native RAG pipeline instead.
    """
    if not _LLAMA_INDEX_AVAILABLE or not VectorStoreIndex or not Document:
        return None

    def _run_query() -> Optional[str]:
        try:
            # Build Documents from search results
            documents = []
            for item in search_results:
                text = f"Object Type: {item.object_type}\nObject Key: {item.object_key}\n"
                if item.properties_preview:
                    import json
                    text += f"Properties: {json.dumps(item.properties_preview, ensure_ascii=False)}\n"
                text += f"Explanation: {item.explanation}"
                documents.append(
                    Document(
                        text=text,
                        metadata={
                            "object_id": item.object_id,
                            "object_type": item.object_type,
                            "object_key": item.object_key,
                            "score": item.score,
                        },
                    )
                )

            if not documents:
                return None

            # Build an in-memory index from retrieved documents
            index = VectorStoreIndex.from_documents(documents)
            query_engine = index.as_query_engine()

            final_query = query
            if system_prompt:
                # LlamaIndex query engine does not take a raw system prompt directly;
                # we wrap the query with instructions as a simple approximation.
                final_query = f"{system_prompt}\n\nQuestion: {query}\nAnswer:"

            response = query_engine.query(final_query)
            return str(response)
        except Exception as e:
            logger.warning(f"LlamaIndex RAG query failed: {e}")
            return None

    try:
        return await asyncio.to_thread(_run_query)
    except Exception as e:
        logger.warning(f"LlamaIndex RAG thread failed: {e}")
        return None
