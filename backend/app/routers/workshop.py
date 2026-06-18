"""Workshop App Builder API — S3-3, V4-1.

A Workshop is a saved layout of React Flow nodes (Tables, Charts, Action
buttons, etc.) wired together. This router persists the graph state
and (V4-1) runs the graph on demand.
"""

import math
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db
from app.models.workshop_models import WorkshopApp, WorkshopExecution
from app.models.workshop_schemas import (
    WorkshopAppCreate,
    WorkshopAppListResponse,
    WorkshopAppResponse,
    WorkshopAppUpdate,
    WorkshopExecutionListItem,
    WorkshopExecutionListResponse,
    WorkshopExecutionRequest,
    WorkshopExecutionResponse,
)
from app.services.workshop_executor import run_workshop

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workshop/apps", tags=["Workshop"])


@router.post("", response_model=WorkshopAppResponse, status_code=status.HTTP_201_CREATED)
async def create_workshop_app(
    request: Request,
    data: WorkshopAppCreate,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    app = WorkshopApp(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        graph=data.graph,
        status="draft",
        created_by=UUID(int=0),
    )
    db.add(app)
    await db.flush()
    await db.refresh(app)
    return _to_response(app)


@router.get("", response_model=WorkshopAppListResponse)
async def list_workshop_apps(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))

    count_q = select(func.count()).select_from(WorkshopApp).where(WorkshopApp.tenant_id == tenant_id)
    q = select(WorkshopApp).where(WorkshopApp.tenant_id == tenant_id)

    if status_filter:
        count_q = count_q.where(WorkshopApp.status == status_filter)
        q = q.where(WorkshopApp.status == status_filter)

    total = (await db.execute(count_q)).scalar() or 0

    q = q.order_by(WorkshopApp.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    items = [_to_response(a) for a in result.scalars().all()]

    pages = math.ceil(total / page_size) if total > 0 else 1
    return WorkshopAppListResponse(
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


@router.get("/{app_id}", response_model=WorkshopAppResponse)
async def get_workshop_app(
    request: Request,
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    result = await db.execute(
        select(WorkshopApp).where(
            WorkshopApp.id == app_id, WorkshopApp.tenant_id == tenant_id
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Workshop app not found")
    return _to_response(app)


@router.put("/{app_id}", response_model=WorkshopAppResponse)
async def update_workshop_app(
    request: Request,
    app_id: UUID,
    data: WorkshopAppUpdate,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    result = await db.execute(
        select(WorkshopApp).where(
            WorkshopApp.id == app_id, WorkshopApp.tenant_id == tenant_id
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Workshop app not found")

    updates = data.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(app, k, v)

    await db.flush()
    await db.refresh(app)
    return _to_response(app)


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workshop_app(
    request: Request,
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    result = await db.execute(
        select(WorkshopApp).where(
            WorkshopApp.id == app_id, WorkshopApp.tenant_id == tenant_id
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Workshop app not found")
    await db.delete(app)
    await db.flush()


# ---------------------------------------------------------------------------
# V4-1: runtime execution
# ---------------------------------------------------------------------------


@router.post("/{app_id}/run", response_model=WorkshopExecutionResponse)
async def run_workshop_app(
    request: Request,
    app_id: UUID,
    data: WorkshopExecutionRequest = WorkshopExecutionRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Execute a workshop app once and return the per-node results.

    Synchronous — the graph is small enough that we run inline. V4.1
    will move this to a Celery + SSE path if real apps need it.
    """
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    triggered_by = getattr(request.state, "user_id", None)
    try:
        execution = await run_workshop(
            db=db,
            tenant_id=tenant_id,
            app_id=app_id,
            triggered_by=triggered_by,
            node_overrides=data.node_overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _execution_to_response(execution)


@router.get("/{app_id}/executions", response_model=WorkshopExecutionListResponse)
async def list_workshop_executions(
    request: Request,
    app_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of historical runs for a workshop app."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))

    count_q = (
        select(func.count())
        .select_from(WorkshopExecution)
        .where(
            WorkshopExecution.tenant_id == tenant_id,
            WorkshopExecution.app_id == app_id,
        )
    )
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(WorkshopExecution)
        .where(
            WorkshopExecution.tenant_id == tenant_id,
            WorkshopExecution.app_id == app_id,
        )
        .order_by(WorkshopExecution.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    items = [
        WorkshopExecutionListItem(
            id=ex.id,
            app_id=ex.app_id,
            status=ex.status,
            started_at=ex.started_at,
            completed_at=ex.completed_at,
            duration_ms=ex.duration_ms,
        )
        for ex in result.scalars().all()
    ]
    pages = math.ceil(total / page_size) if total > 0 else 1
    return WorkshopExecutionListResponse(
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


@router.get("/{app_id}/executions/{execution_id}", response_model=WorkshopExecutionResponse)
async def get_workshop_execution(
    request: Request,
    app_id: UUID,
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetch one historical run, including per-node results."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))
    result = await db.execute(
        select(WorkshopExecution).where(
            WorkshopExecution.id == execution_id,
            WorkshopExecution.app_id == app_id,
            WorkshopExecution.tenant_id == tenant_id,
        )
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return _execution_to_response(execution)


def _to_response(app: WorkshopApp) -> WorkshopAppResponse:
    return WorkshopAppResponse(
        id=app.id,
        tenant_id=app.tenant_id,
        name=app.name,
        description=app.description,
        graph=app.graph or {},
        status=app.status,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


def _execution_to_response(execution: WorkshopExecution) -> WorkshopExecutionResponse:
    # ``results`` is a JSONB dict of node_id -> {status, output, error, ...}.
    # The schema wraps it in WorkshopNodeResult for type fidelity.
    from app.models.workshop_schemas import WorkshopNodeResult

    raw_results = execution.results or {}
    wrapped: Dict[str, WorkshopNodeResult] = {}
    for nid, payload in raw_results.items():
        if not isinstance(payload, dict):
            continue
        wrapped[nid] = WorkshopNodeResult(
            node_id=payload.get("node_id", nid),
            node_type=payload.get("node_type", "unknown"),
            status=payload.get("status", "pending"),
            output=payload.get("output"),
            error=payload.get("error"),
            duration_ms=payload.get("duration_ms"),
        )
    return WorkshopExecutionResponse(
        id=execution.id,
        app_id=execution.app_id,
        tenant_id=execution.tenant_id,
        status=execution.status,
        results=wrapped,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        duration_ms=execution.duration_ms,
        error_message=execution.error_message,
    )
