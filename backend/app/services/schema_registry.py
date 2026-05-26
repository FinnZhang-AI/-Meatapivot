"""SchemaRegistry with Redis-backed Pydantic model cache.

P0-ONT-06: Redis-backed schema cache; invalidated on compile.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.services.redis_client import redis_client

logger = logging.getLogger(__name__)


class SchemaRegistry:
    """Registry for caching compiled ontology schemas.
    
    Uses Redis as primary cache with in-memory fallback.
    Key format: schema:{tenant_id}:{type}:{type_id}
    """
    
    CACHE_PREFIX = "schema"
    DEFAULT_TTL = 3600  # 1 hour
    
    def __init__(self):
        self._local_cache: Dict[str, Any] = {}
    
    def _cache_key(self, tenant_id: UUID, type_name: str, type_id: UUID) -> str:
        """Generate Redis cache key."""
        return f"{self.CACHE_PREFIX}:{tenant_id}:{type_name}:{type_id}"
    
    async def get(
        self,
        tenant_id: UUID,
        type_name: str,
        type_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """Get cached schema definition.
        
        Checks local cache first, then Redis.
        """
        key = self._cache_key(tenant_id, type_name, type_id)
        
        # Check local cache
        if key in self._local_cache:
            return self._local_cache[key]
        
        # Check Redis
        try:
            if redis_client.client:
                data = await redis_client.client.get(key)
                if data:
                    schema = json.loads(data)
                    self._local_cache[key] = schema
                    return schema
        except Exception as e:
            logger.warning(f"Redis get failed for {key}: {e}")
        
        return None
    
    async def set(
        self,
        tenant_id: UUID,
        type_name: str,
        type_id: UUID,
        schema: Dict[str, Any],
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """Cache a schema definition."""
        key = self._cache_key(tenant_id, type_name, type_id)
        
        # Update local cache
        self._local_cache[key] = schema
        
        # Update Redis
        try:
            if redis_client.client:
                await redis_client.client.setex(
                    key,
                    ttl,
                    json.dumps(schema, default=str),
                )
        except Exception as e:
            logger.warning(f"Redis set failed for {key}: {e}")
    
    async def invalidate(
        self,
        tenant_id: UUID,
        type_name: Optional[str] = None,
        type_id: Optional[UUID] = None,
    ) -> int:
        """Invalidate cached schemas.
        
        If type_name and type_id provided, invalidate specific entry.
        If only type_name provided, invalidate all of that type for tenant.
        If neither provided, invalidate all schemas for tenant.
        
        Returns number of keys invalidated.
        """
        pattern = f"{self.CACHE_PREFIX}:{tenant_id}"
        if type_name:
            pattern += f":{type_name}"
            if type_id:
                pattern += f":{type_id}"
            else:
                pattern += ":*"
        else:
            pattern += ":*"
        
        # Clear local cache matches
        local_keys = [k for k in self._local_cache if k.startswith(pattern.rstrip("*"))]
        for k in local_keys:
            del self._local_cache[k]
        
        # Clear Redis matches
        try:
            if redis_client.client:
                keys = []
                async for key in redis_client.client.scan_iter(match=pattern):
                    keys.append(key)
                if keys:
                    await redis_client.client.delete(*keys)
                return len(keys)
        except Exception as e:
            logger.warning(f"Redis invalidate failed for pattern {pattern}: {e}")
        
        return len(local_keys)
    
    async def invalidate_all(self) -> None:
        """Invalidate all schemas across all tenants."""
        self._local_cache.clear()
        
        try:
            if redis_client.client:
                keys = []
                async for key in redis_client.client.scan_iter(match=f"{self.CACHE_PREFIX}:*"):
                    keys.append(key)
                if keys:
                    await redis_client.client.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis invalidate_all failed: {e}")
    
    async def get_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get cache statistics for a tenant."""
        pattern = f"{self.CACHE_PREFIX}:{tenant_id}:*"
        count = 0
        
        try:
            if redis_client.client:
                async for _ in redis_client.client.scan_iter(match=pattern):
                    count += 1
        except Exception as e:
            logger.warning(f"Redis stats failed: {e}")
        
        local_count = sum(1 for k in self._local_cache if k.startswith(pattern.rstrip("*")))
        
        return {
            "tenant_id": str(tenant_id),
            "redis_keys": count,
            "local_keys": local_count,
            "total_cached": count + local_count,
        }
    
    async def get_many(
        self,
        tenant_id: UUID,
        type_name: str,
        type_ids: List[UUID],
    ) -> Dict[UUID, Optional[Dict[str, Any]]]:
        """Get multiple schemas in one call."""
        results = {}
        for type_id in type_ids:
            results[type_id] = await self.get(tenant_id, type_name, type_id)
        return results
    
    async def set_many(
        self,
        tenant_id: UUID,
        type_name: str,
        schemas: Dict[UUID, Dict[str, Any]],
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """Cache multiple schemas."""
        for type_id, schema in schemas.items():
            await self.set(tenant_id, type_name, type_id, schema, ttl)


# Global registry instance
schema_registry = SchemaRegistry()
