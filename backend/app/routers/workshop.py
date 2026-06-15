"""Workshop App Builder API — S3-3.

A Workshop is a saved layout of React Flow nodes (Tables, Charts, Action
buttons, etc.) wired together. This router is intentionally minimal: it
just persists the graph state and lets the frontend drive composition.
Runtime data binding (e.g. a Chart node consuming a Table node's query
result) happens in the frontend ``workshopStore``; we don't try to be a
general execution engine here.
"""

import math
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db
from app.models.workshop_models import WorkshopApp
from app.models.workshop_schemas import (
    WorkshopAppCreate,
    WorkshopAppListResponse,
    WorkshopAppResponse,
    WorkshopAppUpdate,
)

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
