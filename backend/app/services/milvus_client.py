import logging
import os
from typing import Dict, List, Optional
from uuid import UUID

from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility

logger = logging.getLogger(__name__)

# Embedding model - lazy loaded
_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Try BGE-M3 first, fallback to all-MiniLM-L6-v2
            try:
                _embedding_model = SentenceTransformer("BAAI/bge-m3")
                logger.info("Loaded embedding model: BAAI/bge-m3")
            except Exception:
                _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Loaded embedding model: all-MiniLM-L6-v2 (fallback)")
        except ImportError:
            logger.error("sentence-transformers not installed. Vector search will be unavailable.")
            raise
    return _embedding_model


class MilvusClient:
    """Tenant-aware Milvus vector database client."""

    _instance: Optional["MilvusClient"] = None
    _collection_name = "ontology_objects"
    _dim = 1024  # BGE-M3 dimension (1024); all-MiniLM-L6-v2 uses 384, will adjust dynamically

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def _connect(self):
        uri = os.getenv("MILVUS_URI", "http://localhost:19530")
        alias = "meatapivot_default"
        try:
            if connections.has_connection(alias):
                return
            connections.connect(alias=alias, uri=uri)
            logger.info(f"Connected to Milvus at {uri}")
        except Exception as e:
            logger.warning(f"Milvus connection failed: {e}. Vector search will be unavailable.")
            raise

    def _ensure_collection(self):
        alias = "meatapivot_default"
        if utility.has_collection(self._collection_name, using=alias):
            return Collection(self._collection_name, using=alias)

        # Detect actual embedding dimension
        model = _get_embedding_model()
        self._dim = model.get_sentence_embedding_dimension()

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="object_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="object_type", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self._dim),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="metadata", dtype=DataType.JSON),
        ]
        schema = CollectionSchema(fields, description="Ontology object embeddings")
        collection = Collection(self._collection_name, schema, using=alias)

        # Create index
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        }
        collection.create_index("embedding", index_params)
        collection.load()
        logger.info(f"Created Milvus collection '{self._collection_name}' with dim={self._dim}")
        return collection

    def upsert(
        self,
        tenant_id: UUID,
        object_id: str,
        object_type: str,
        text: str,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Upsert a vector record for an ontology object."""
        try:
            self._connect()
            collection = self._ensure_collection()
            model = _get_embedding_model()
            embedding = model.encode(text, normalize_embeddings=True).tolist()

            record_id = f"{str(tenant_id)}:{object_id}"
            data = [
                [record_id],
                [str(tenant_id)],
                [object_id],
                [object_type],
                [embedding],
                [text[:4096]],
                [metadata or {}],
            ]
            collection.insert(data)
            collection.flush()
            logger.info(f"Upserted vector for object {object_id} (tenant {tenant_id})")
            return True
        except Exception as e:
            logger.error(f"Milvus upsert failed: {e}")
            return False

    def search(
        self,
        tenant_id: UUID,
        query_text: str,
        top_k: int = 10,
        object_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Search vectors by text query, filtered by tenant."""
        try:
            self._connect()
            collection = self._ensure_collection()
            model = _get_embedding_model()
            embedding = model.encode(query_text, normalize_embeddings=True).tolist()

            expr = f'tenant_id == "{str(tenant_id)}"'
            if object_types:
                # Use Milvus 'in' expression to avoid string escaping issues
                types_expr = "object_type in [" + ",".join(f'"{ot}"' for ot in object_types) + "]"
                expr = f"({expr}) && ({types_expr})"

            results = collection.search(
                data=[embedding],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"nprobe": 16}},
                limit=top_k,
                expr=expr,
                output_fields=["object_id", "object_type", "text", "metadata", "tenant_id"],
            )

            hits = []
            for result_group in results:
                for hit in result_group:
                    hits.append({
                        "object_id": hit.entity.get("object_id"),
                        "object_type": hit.entity.get("object_type"),
                        "text": hit.entity.get("text"),
                        "metadata": hit.entity.get("metadata"),
                        "score": hit.distance,
                    })
            return hits
        except Exception as e:
            logger.error(f"Milvus search failed: {e}")
            return []

    def delete_by_object_id(self, tenant_id: UUID, object_id: str) -> bool:
        """Delete vector record for a specific object."""
        try:
            self._connect()
            collection = self._ensure_collection()
            record_id = f"{str(tenant_id)}:{object_id}"
            collection.delete(f'id == "{record_id}"')
            return True
        except Exception as e:
            logger.error(f"Milvus delete failed: {e}")
            return False


# Global singleton
milvus_client = MilvusClient()
