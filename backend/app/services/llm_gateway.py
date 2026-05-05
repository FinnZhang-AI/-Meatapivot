"""LLM Gateway - Unified interface to One API / OpenAI-compatible endpoints"""
import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID, uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from app.core.config import settings
from app.services.redis_client import redis_client

logger = logging.getLogger(__name__)


class LLMGateway:
    """Async LLM Gateway with rate limiting, logging, and model routing."""

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=settings.ONE_API_URL.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.ONE_API_KEY}"} if settings.ONE_API_KEY else {},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        self.default_model = settings.DEFAULT_LLM_MODEL
        self.rate_limit = settings.LLM_RATE_LIMIT_PER_MINUTE

    async def _check_rate_limit(self, model: str) -> bool:
        """Check if request is within rate limit using Redis or in-memory fallback."""
        key = f"llm_rate:{model}:{int(time.time()) // 60}"
        try:
            if redis_client.connected:
                count = await redis_client.get(key)
                if count is None:
                    await redis_client.set(key, "1", expire=120)
                    return True
                if int(count) >= self.rate_limit:
                    return False
                await redis_client.set(key, str(int(count) + 1), expire=120)
                return True
        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}")
        # Fallback: allow if no Redis
        return True

    async def _log_call(
        self,
        db: Optional[AsyncSession],
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        status: str,
        error_msg: Optional[str] = None,
    ) -> None:
        """Log LLM call to database (best-effort)."""
        if db is None:
            return
        try:
            # Import here to avoid circular deps at module level
            from app.models.ontology_models import AIPLLMCall
            log = AIPLLMCall(
                id=uuid4(),
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=duration_ms,
                status=status,
                error_message=error_msg,
            )
            db.add(log)
            await db.flush()
        except Exception as e:
            logger.warning(f"Failed to log LLM call: {e}")

    def _resolve_model(self, model: Optional[str]) -> str:
        """Resolve model alias to actual model ID."""
        if model and model.strip():
            return model.strip()
        return self.default_model

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Non-streaming chat completion."""
        model = self._resolve_model(model)

        if not await self._check_rate_limit(model):
            await self._log_call(db, model, 0, 0, 0, "rate_limited")
            raise httpx.HTTPStatusError(
                "Rate limit exceeded",
                request=None,
                response=httpx.Response(429),
            )

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        start = time.time()
        try:
            resp = await self.client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            duration_ms = int((time.time() - start) * 1000)

            usage = data.get("usage", {})
            await self._log_call(
                db,
                model,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                duration_ms,
                "success",
            )
            return data
        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start) * 1000)
            await self._log_call(db, model, 0, 0, duration_ms, "error", str(e))
            raise
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            await self._log_call(db, model, 0, 0, duration_ms, "error", str(e))
            raise

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completion (SSE). Yields JSON strings."""
        model = self._resolve_model(model)

        if not await self._check_rate_limit(model):
            yield json.dumps({"error": "Rate limit exceeded"})
            return

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with self.client.stream("POST", "/chat/completions", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            yield json.dumps({"done": True})
                            break
                        try:
                            parsed = json.loads(data)
                            delta = parsed["choices"][0].get("delta", {}).get("content", "")
                            finish = parsed["choices"][0].get("finish_reason")
                            yield json.dumps({"delta": delta, "finish_reason": finish})
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except httpx.HTTPStatusError as e:
            logger.error(f"Streaming chat error: {e}")
            yield json.dumps({"error": str(e)})
        except Exception as e:
            logger.error(f"Streaming chat unexpected error: {e}")
            yield json.dumps({"error": str(e)})

    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Fetch available models from One API."""
        try:
            resp = await self.client.get("/models")
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"Failed to fetch models: {e}")
            # Return fallback list
            return [
                {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai"},
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai"},
                {"id": "claude-3-5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "anthropic"},
                {"id": "llama-3.1-70b", "name": "Llama 3.1 70B", "provider": "ollama"},
            ]

    async def close(self):
        await self.client.aclose()


# Singleton instance
llm_gateway = LLMGateway()
