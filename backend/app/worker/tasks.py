"""Celery tasks for Meatapivot.

Task status flow:
PENDING → STARTED → SUCCESS / FAILURE / RETRY
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


# Maximum size we will pull from MinIO in one go for document parsing.
# Anything bigger should be chunked by the caller; we don't ship a
# chunker in v2.4.
_MAX_DOC_BYTES = 25 * 1024 * 1024  # 25 MiB


def _publish_interface_validation(tenant_id: str, payload: Dict[str, Any]) -> None:
    """Best-effort publish of validation result to Redis pub/sub channel.

    Channel: ``interface_validation:{tenant_id}``

    The FastAPI WebSocket endpoint subscribes to this channel and pushes
    the payload to all connected clients for the tenant. If Redis is
    unavailable the call is a no-op — the WebSocket layer falls back to
    a 5 s poll of the ``interface_validation:latest:{tenant_id}`` key.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis  # sync client is fine for short publish calls

        client = redis.Redis.from_url(redis_url, decode_responses=True)
        channel = f"interface_validation:{tenant_id}"
        key = f"interface_validation:latest:{tenant_id}"
        body = json.dumps(payload, default=str)
        client.setex(key, 300, body)
        client.publish(channel, body)
        client.close()
    except Exception as exc:  # pragma: no cover - degraded path
        logger.warning(f"Failed to publish interface validation result: {exc}")


@celery_app.task(bind=True, max_retries=3)
def validate_all_interfaces(self, tenant_id: str) -> Dict[str, Any]:
    """Re-validate every Interface in a tenant and publish the result.

    This is the S3-1 async validation task. The actual validation logic
    lives in :class:`app.services.ontology_service.OntologyService` so
    we keep one source of truth between the synchronous HTTP
    ``/{id}/validate`` endpoint and this background job.
    """
    try:
        logger.info(f"Async interface validation started for tenant {tenant_id}")

        from app.services.database import async_session_maker
        from app.services.ontology_service import OntologyService

        tenant_uuid = UUID(tenant_id)

        async def _run() -> Dict[str, Any]:
            async with async_session_maker() as db:
                service = OntologyService(db, tenant_uuid)
                report = await service.validate_all_interfaces()
                report["completed_at"] = datetime.utcnow().isoformat()
                return report

        report = asyncio.run(_run())
        _publish_interface_validation(tenant_id, report)
        return report
    except Exception as exc:
        logger.error(f"Interface validation failed for tenant {tenant_id}: {exc}")
        _publish_interface_validation(
            tenant_id,
            {
                "status": "failed",
                "error": str(exc),
                "tenant_id": tenant_id,
                "completed_at": datetime.utcnow().isoformat(),
            },
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ---------------------------------------------------------------------------
# V4-3: process_document implementation
# ---------------------------------------------------------------------------


def _parse_text_from_bytes(
    content: bytes,
    mime_type: str | None,
    filename: str,
) -> Dict[str, Any]:
    """Extract plain text from a downloaded document.

    Supports the formats the upload UI advertises. Unknown inputs
    fall back to UTF-8 decode with errors='replace'. We never raise —
    a parser failure is recorded in the result so the caller can
    decide whether to retry.

    Returns ``{"text": str, "char_count": int, "parser": str, ...}``.
    """
    import io

    name = (filename or "").lower()
    mime = (mime_type or "").lower()

    if mime.startswith("text/") or name.endswith((".txt", ".md", ".csv")):
        return {
            "text": content.decode("utf-8", errors="replace"),
            "char_count": len(content),
            "parser": "text",
        }

    if mime == "application/pdf" or name.endswith(".pdf"):
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError:
            return {
                "text": content.decode("utf-8", errors="replace"),
                "char_count": len(content),
                "parser": "text-fallback",
                "warning": "pypdf not installed; fell back to UTF-8 decode",
            }
        try:
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
            return {
                "text": text,
                "char_count": len(text),
                "parser": "pypdf",
            }
        except Exception as exc:  # noqa: BLE001 — never raise
            return {
                "text": "",
                "char_count": 0,
                "parser": "pypdf",
                "error": str(exc)[:500],
            }

    if name.endswith(".docx") or mime.endswith("wordprocessingml.document"):
        try:
            from docx import Document  # type: ignore
        except ImportError:
            return {
                "text": content.decode("utf-8", errors="replace"),
                "char_count": len(content),
                "parser": "text-fallback",
                "warning": "python-docx not installed; fell back to UTF-8 decode",
            }
        try:
            doc = Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs)
            return {
                "text": text,
                "char_count": len(text),
                "parser": "python-docx",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "text": "",
                "char_count": 0,
                "parser": "python-docx",
                "error": str(exc)[:500],
            }

    return {
        "text": content.decode("utf-8", errors="replace"),
        "char_count": len(content),
        "parser": "text-fallback",
        "warning": f"unknown mime={mime!r} name={name!r}",
    }


@celery_app.task(bind=True, max_retries=3)
def process_document(self, document_id: str, object_key: str, bucket_name: str) -> Dict[str, Any]:
    """V4-3: download → parse → store text on the Document row.

    The Document ORM has no ``content_text`` column yet; we use the
    JSONB ``metadata_`` field so this commit is purely additive and
    does not require a DDL migration. The result is keyed under
    ``metadata_['content_text']``, ``metadata_['char_count']``, and
    ``metadata_['parser']``. ``Document.status`` is moved to
    ``processed`` or ``failed`` accordingly.
    """
    try:
        logger.info(f"Processing document {document_id} from {bucket_name}/{object_key}")

        from app.services.minio_client import minio_client  # type: ignore
        from app.services.database import async_session_maker
        from app.models.database_models import Document

        client = getattr(minio_client, "client", minio_client)
        if client is None:
            return {
                "document_id": document_id,
                "status": "skipped",
                "warning": "MinIO not configured",
            }

        response = client.get_object(bucket_name, object_key)
        try:
            content = response.read(_MAX_DOC_BYTES + 1)
        finally:
            response.close()
            response.release_conn()

        if len(content) > _MAX_DOC_BYTES:
            return {
                "document_id": document_id,
                "status": "skipped",
                "warning": f"document larger than {_MAX_DOC_BYTES} bytes",
            }

        parsed = _parse_text_from_bytes(content, mime_type=None, filename=object_key)

        doc_uuid = UUID(document_id)

        async def _persist() -> Dict[str, Any]:
            async with async_session_maker() as db:
                row = await db.get(Document, doc_uuid)
                if row is None:
                    return {"document_id": document_id, "status": "skipped",
                            "warning": "document row not found"}
                md = dict(row.metadata_ or {})
                md["content_text"] = parsed["text"]
                md["char_count"] = parsed["char_count"]
                md["parser"] = parsed["parser"]
                if parsed.get("warning"):
                    md["parser_warning"] = parsed["warning"]
                if parsed.get("error"):
                    md["parser_error"] = parsed["error"]
                row.metadata_ = md
                row.status = "processed" if parsed.get("text") else "failed"
                await db.flush()
                return {
                    "document_id": document_id,
                    "status": row.status,
                    "char_count": parsed["char_count"],
                    "parser": parsed["parser"],
                }

        return asyncio.run(_persist())
    except Exception as exc:
        logger.exception(f"Document processing failed for {document_id}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ---------------------------------------------------------------------------
# V4-3: execute_function_action implementation
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, max_retries=3)
def execute_function_action(self, function_id: str, action_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """V4-3: load a function's code from the DB and run it through
    the RestrictedPython sandbox.

    The user code must define ``handler(parameters)`` (or ``main``).
    The sandbox re-uses the existing
    :mod:`app.services.sandbox_restricted` helpers so we don't fork
    the security boundary — anything reaching this task has already
    been hardened by the synchronous ``ActionExecutor`` path that
    v3.2 shipped.
    """
    try:
        from app.services.database import async_session_maker
        from app.models.ontology_models import OntologyFunction
        from app.services.sandbox_restricted import (
            ALLOWED_BUILTINS,
            FORBIDDEN_NAMES,
            _check_forbidden_names,
            compile_restricted,
        )
        from RestrictedPython import safe_globals  # type: ignore

        fn_uuid = UUID(function_id)
        timeout_seconds = int(context.get("timeout_seconds") or 30)

        async def _load_and_run() -> Dict[str, Any]:
            async with async_session_maker() as db:
                fn = await db.get(OntologyFunction, fn_uuid)
                if fn is None:
                    return {"function_id": function_id, "status": "error",
                            "error": "function not found"}
                code = fn.code or ""
                lang = (fn.language or "python").lower()
                if lang != "python":
                    return {"function_id": function_id, "status": "error",
                            "error": f"unsupported language: {lang}"}

            # Scan the source for forbidden names (os.system, __import__, ...)
            # BEFORE we compile; a hit here is a hard fail.
            forbidden = _check_forbidden_names(code)
            if forbidden:
                # The helper returns a list of human-readable messages.
                forbidden_msg = "; ".join(forbidden) if isinstance(forbidden, list) else str(forbidden)
                return {
                    "function_id": function_id,
                    "status": "error",
                    "error": f"forbidden name in code: {forbidden_msg}",
                }

            # Make sure the FORBIDDEN_NAMES list is also in the runtime
            # env so attribute access like getattr(__builtins__, ...)
            # is blocked at exec time.
            try:
                compiled = compile_restricted(code, filename=f"<fn:{function_id}>")
            except Exception as exc:  # noqa: BLE001
                return {"function_id": function_id, "status": "error",
                        "error": f"compile error: {exc}"}

            env: Dict[str, Any] = dict(safe_globals)
            env.update(ALLOWED_BUILTINS)
            env["FORBIDDEN_NAMES"] = FORBIDDEN_NAMES
            env["input"] = context.get("parameters", {})

            def _runner() -> Dict[str, Any]:
                # RestrictedPython compiles to a code object; we exec
                # it in the prepared env. This is the documented entry
                # point for the sandbox — see v3.2 sprint1 P0-SEC-02.
                exec(compiled.code, env)  # noqa: S102 — restricted env only
                handler = env.get("handler") or env.get("main")
                if handler is None:
                    return {"output": None,
                            "warning": "no handler()/main() defined in code"}
                if not callable(handler):
                    return {"output": None,
                            "warning": "handler is not callable"}
                return {"output": handler(context.get("parameters", {}))}

            try:
                inner = await asyncio.to_thread(_runner)
            except Exception as exc:  # noqa: BLE001
                return {"function_id": function_id, "status": "error",
                        "error": f"runtime error: {exc}"}

            inner.setdefault("function_id", function_id)
            inner.setdefault("action_id", action_id)
            if "status" not in inner:
                inner["status"] = "success" if "error" not in inner else "error"
            return inner

        try:
            return asyncio.run(asyncio.wait_for(_load_and_run(), timeout=timeout_seconds))
        except asyncio.TimeoutError:
            return {
                "function_id": function_id,
                "action_id": action_id,
                "status": "error",
                "error": f"timeout after {timeout_seconds}s",
            }
    except Exception as exc:
        logger.exception(f"Function action execution failed: {function_id}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ---------------------------------------------------------------------------
# Deferred to v2.4.1: compile_ontology, execute_decision_flow
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, max_retries=3)
def compile_ontology(self, tenant_id: str, compile_type: str = "incremental") -> Dict[str, Any]:
    """V4-3: deferred — v2.2.0 Sprint 3 already moved compilation onto
    the synchronous pipeline (``/ontology/compile``), so this Celery
    variant isn't on the critical path. v2.4.1 will either remove it
    or wire it up to the existing ``CompilationPipeline``."""
    raise NotImplementedError("compile_ontology is deferred to v2.4.1")


@celery_app.task(bind=True, max_retries=3)
def execute_decision_flow(self, flow_id: str, execution_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """V4-3: deferred — decision flows currently run synchronously via
    the decision_flow router. v2.4.1 will move them to Celery when we
    need long-running execution isolation."""
    raise NotImplementedError("execute_decision_flow is deferred to v2.4.1")


__all__ = [
    "validate_all_interfaces",
    "process_document",
    "execute_function_action",
    "compile_ontology",
    "execute_decision_flow",
    "_parse_text_from_bytes",
]
