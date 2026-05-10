import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self):
        self.client: Optional[Any] = None
        self.connected = False
        self._fallback: Dict[str, Any] = {}

    async def connect(self):
        if not REDIS_AVAILABLE:
            logger.warning("redis package not installed; using in-memory fallback")
            self.connected = False
            return
        try:
            redis_url = settings.REDIS_URL if hasattr(settings, "REDIS_URL") else "redis://localhost:6379/0"
            self.client = await aioredis.from_url(redis_url, decode_responses=True)
            await self.client.ping()
            self.connected = True
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}; using in-memory fallback")
            self.connected = False

    async def close(self):
        if self.client:
            await self.client.close()
            self.connected = False
            logger.info("Redis connection closed")

    def _key(self, tenant_id: str, execution_id: str) -> str:
        return f"flow_exec:{tenant_id}:{execution_id}"

    async def set_flow_execution(self, tenant_id: str, execution_id: str, data: Dict[str, Any]) -> None:
        if self.connected and self.client:
            await self.client.setex(
                self._key(tenant_id, execution_id),
                86400,  # TTL 24 hours
                json.dumps(data, default=str)
            )
        else:
            self._fallback[execution_id] = data

    async def get_flow_execution(self, tenant_id: str, execution_id: str) -> Optional[Dict[str, Any]]:
        if self.connected and self.client:
            raw = await self.client.get(self._key(tenant_id, execution_id))
            if raw:
                return json.loads(raw)
            return None
        return self._fallback.get(execution_id)

    async def update_flow_execution(self, tenant_id: str, execution_id: str, data: Dict[str, Any]) -> None:
        existing = await self.get_flow_execution(tenant_id, execution_id)
        if existing:
            existing.update(data)
            await self.set_flow_execution(tenant_id, execution_id, existing)
        else:
            await self.set_flow_execution(tenant_id, execution_id, data)

    async def get(self, key: str) -> Optional[str]:
        """Generic key-value get (used by LLM Gateway rate limiter)."""
        if self.connected and self.client:
            return await self.client.get(key)
        return self._fallback.get(key)

    async def set(self, key: str, value: str, expire: int = 0) -> None:
        """Generic key-value set with optional TTL (used by LLM Gateway rate limiter)."""
        if self.connected and self.client:
            if expire > 0:
                await self.client.setex(key, expire, value)
            else:
                await self.client.set(key, value)
        else:
            self._fallback[key] = value


redis_client = RedisClient()
