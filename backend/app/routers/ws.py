"""WebSocket endpoints for live notifications.

S3-1: clients subscribe to ``/ws/interfaces/{tenant_id}`` to receive
interface validation reports. Backed by Redis pub/sub when available; falls
back to a 5 second poll of ``interface_validation:latest:{tenant_id}`` when
Redis is unreachable.
"""

import asyncio
import json
import logging
import os
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


class _InterfaceChannel:
    """Per-tenant WebSocket connection registry + Redis subscriber."""

    POLL_INTERVAL_SECONDS = 5.0

    def __init__(self) -> None:
        self._clients: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._last_payload: Dict[str, str] = {}

    async def register(self, tenant_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.setdefault(tenant_id, set()).add(websocket)

    async def unregister(self, tenant_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._clients.get(tenant_id)
            if not conns:
                return
            conns.discard(websocket)
            if not conns:
                self._clients.pop(tenant_id, None)

    async def broadcast(self, tenant_id: str, payload: str) -> None:
        async with self._lock:
            conns = list(self._clients.get(tenant_id, ()))
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception as exc:
                logger.debug(f"WebSocket send failed; dropping client: {exc}")
                await self.unregister(tenant_id, ws)

    def remember(self, tenant_id: str, payload: str) -> None:
        self._last_payload[tenant_id] = payload

    def last(self, tenant_id: str) -> str | None:
        return self._last_payload.get(tenant_id)


_channel = _InterfaceChannel()


def _redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def _subscribe_loop(tenant_id: str) -> None:
    """Subscribe to ``interface_validation:{tenant_id}`` and forward.

    Runs until cancelled. The Celery task publishes to the same channel
    (see ``app.worker.tasks._publish_interface_validation``).
    """
    try:
        import redis.asyncio as aioredis
    except ImportError:
        aioredis = None  # type: ignore

    if aioredis is None:
        logger.debug("redis package unavailable; WS subscription loop disabled")
        return

    backoff = 1.0
    while True:
        try:
            client = aioredis.from_url(_redis_url(), decode_responses=True)
            async with client.pubsub() as pubsub:
                await pubsub.subscribe(f"interface_validation:{tenant_id}")
                backoff = 1.0  # reset on successful connect
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if not data:
                        continue
                    _channel.remember(tenant_id, data)
                    await _channel.broadcast(tenant_id, data)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                f"WS subscribe loop dropped (tenant={tenant_id}): {exc}; "
                f"reconnecting in {backoff:.1f}s"
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


async def _poll_loop(tenant_id: str) -> None:
    """Fallback when Redis pub/sub is unavailable.

    Polls ``interface_validation:latest:{tenant_id}`` every 5s. If the value
    changed since the last poll, broadcast it. The Celery task always writes
    that key (with a 5 min TTL) regardless of pub/sub health.
    """
    try:
        import redis.asyncio as aioredis
    except ImportError:
        aioredis = None  # type: ignore

    if aioredis is None:
        # No Redis at all — nothing to do. Client will time out and reconnect.
        return

    while True:
        try:
            client = aioredis.from_url(_redis_url(), decode_responses=True)
            key = f"interface_validation:latest:{tenant_id}"
            while True:
                value = await client.get(key)
                if value and value != _channel.last(tenant_id):
                    _channel.remember(tenant_id, value)
                    await _channel.broadcast(tenant_id, value)
                await asyncio.sleep(_InterfaceChannel.POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"WS poll loop error (tenant={tenant_id}): {exc}")
            await asyncio.sleep(2.0)


@router.websocket("/ws/interfaces/{tenant_id}")
async def interface_validation_ws(websocket: WebSocket, tenant_id: str) -> None:
    """Push interface validation results to subscribed clients.

    On connect, immediately replays the most recent report (if any) so a
    freshly opened tab doesn't have to wait for the next change. Then runs
    both the pub/sub loop and the poll loop concurrently; whichever fires
    first wins, the other becomes a no-op for that tick.
    """
    await websocket.accept()
    await _channel.register(tenant_id, websocket)

    # Replay the most recent report so the client doesn't see an empty state
    last = _channel.last(tenant_id)
    if last:
        try:
            await websocket.send_text(last)
        except Exception:
            await _channel.unregister(tenant_id, websocket)
            return

    sub_task = asyncio.create_task(_subscribe_loop(tenant_id))
    poll_task = asyncio.create_task(_poll_loop(tenant_id))

    try:
        # The server is push-only; we just keep the connection alive by
        # reading and discarding any client frames (heartbeats / close).
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug(f"WebSocket closed unexpectedly: {exc}")
    finally:
        await _channel.unregister(tenant_id, websocket)
        sub_task.cancel()
        poll_task.cancel()
        for t in (sub_task, poll_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass


__all__ = ["router"]
