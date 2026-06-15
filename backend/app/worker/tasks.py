"""Celery tasks for Meatapivot.

Task status flow:
PENDING → STARTED → SUCCESS / FAILURE / RETRY
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _publish_interface_validation(tenant_id: str, payload: Dict[str, Any]) -> None:
    """Best-effort publish of validation result to Redis pub/sub channel.

    Channel: ``interface_validation:{tenant_id}``

    The FastAPI WebSocket endpoint subscribes to this channel and pushes the
    payload to all connected clients for the tenant. If Redis is unavailable
    the call is a no-op — the WebSocket layer falls back to a 5s poll of the
    ``interface_validation:latest:{tenant_id}`` key.
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

    This is the S3-1 async validation task. The actual validation logic lives
    in :class:`app.services.ontology_service.OntologyService` so we keep one
    source of truth between the synchronous HTTP ``/{id}/validate`` endpoint
    and this background job.
    """
    try:
        logger.info(f"Async interface validation started for tenant {tenant_id}")

        # Run the async service from inside Celery's sync worker.
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
        # Publish a failure payload so the WS clients can render an error toast
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


@celery_app.task(bind=True, max_retries=3)
def process_document(self, document_id: str, object_key: str, bucket_name: str) -> Dict[str, Any]:
    """
    Process uploaded document asynchronously.
    
    Args:
        document_id: Document UUID
        object_key: MinIO object key
        bucket_name: MinIO bucket name
    
    Returns:
        dict with processing results
    """
    try:
        logger.info(f"Processing document {document_id}")
        
        # TODO: Implement document parsing logic
        # 1. Download from MinIO
        # 2. Extract text/content
        # 3. Generate embeddings
        # 4. Store metadata
        
        return {
            "document_id": document_id,
            "status": "success",
            "message": "Document processed successfully",
        }
    except Exception as exc:
        logger.error(f"Document processing failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=3)
def compile_ontology(self, tenant_id: str, compile_type: str = "incremental") -> Dict[str, Any]:
    """
    Compile ontology definitions asynchronously.
    
    Args:
        tenant_id: Tenant UUID
        compile_type: "full" or "incremental"
    
    Returns:
        dict with compilation results
    """
    try:
        logger.info(f"Compiling ontology for tenant {tenant_id} ({compile_type})")
        
        # TODO: Implement ontology compilation
        # 1. Load ontology definitions from PostgreSQL
        # 2. Build DAG
        # 3. Run validation
        # 4. Generate Neo4j constraints
        # 5. Generate Pydantic schemas
        
        return {
            "tenant_id": tenant_id,
            "compile_type": compile_type,
            "status": "success",
            "affected_count": 0,
        }
    except Exception as exc:
        logger.error(f"Ontology compilation failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=3)
def execute_decision_flow(self, flow_id: str, execution_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute decision flow asynchronously.
    
    Args:
        flow_id: Decision flow UUID
        execution_id: Execution UUID
        parameters: Flow input parameters
    
    Returns:
        dict with execution results
    """
    try:
        logger.info(f"Executing decision flow {flow_id} (execution: {execution_id})")
        
        # TODO: Implement decision flow execution
        
        return {
            "flow_id": flow_id,
            "execution_id": execution_id,
            "status": "success",
            "result": {},
        }
    except Exception as exc:
        logger.error(f"Decision flow execution failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=3)
def execute_function_action(self, function_id: str, action_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute function-backed action asynchronously.
    
    Args:
        function_id: Function UUID
        action_id: Action execution UUID
        context: Execution context (parameters, object_id, etc.)
    
    Returns:
        dict with execution results
    """
    try:
        logger.info(f"Executing function {function_id} for action {action_id}")
        
        # TODO: Implement function execution using RestrictedPython sandbox
        
        return {
            "function_id": function_id,
            "action_id": action_id,
            "status": "success",
            "output": None,
        }
    except Exception as exc:
        logger.error(f"Function action execution failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
