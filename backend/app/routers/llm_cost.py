"""LLM cost dashboard + budget API — S4-1.

Two resource paths:

  - ``/aip/llm-cost``         — read-only aggregations + CSV export
  - ``/aip/llm-budgets``      — per-tenant budget CRUD (single row per tenant)

The cost endpoint never accepts a write. The budget endpoint is the only
place spend thresholds can change. ``LLMCostService`` is a pure read
helper for both.
"""

import csv
import io
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db
from app.services.llm_cost_service import LLMCostService
from app.models.aip_schemas import (
    LLMBudgetCreate,
    LLMBudgetResponse,
    LLMBudgetUpdate,
    LLMCostReport,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aip", tags=["AIP - Cost"])


def _tenant_id(request: Request) -> UUID:
    return getattr(request.state, "tenant_id", UUID(int=0))


def _service(request: Request, db: AsyncSession) -> LLMCostService:
    return LLMCostService(db, _tenant_id(request))


# ---------------------------------------------------------------------------
# Cost report
# ---------------------------------------------------------------------------


@router.get("/llm-cost", response_model=LLMCostReport)
async def get_llm_cost_report(
    request: Request,
    days: int = Query(30, ge=1, le=90),
    group_by: str = Query("day", pattern="^(day|hour)$"),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated LLM cost + usage for the cost dashboard."""
    return await _service(request, db).summary(days=days, group_by=group_by)


@router.get("/llm-cost/export")
async def export_llm_cost_csv(
    request: Request,
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Per-call CSV export — used by the dashboard's download button."""
    rows = await _service(request, db).csv_rows(days=days)

    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    else:
        # Always emit a header so the file is never a confusing blank doc
        buffer.write("id,created_at,model,provider,prompt_tokens,completion_tokens,total_tokens,estimated_cost_usd,status\n")

    buffer.seek(0)
    filename = f"llm-cost-{days}d.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Budget CRUD
# ---------------------------------------------------------------------------


@router.get("/llm-budgets", response_model=Optional[LLMBudgetResponse])
async def get_llm_budget(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return the tenant's current LLM budget, or ``null`` if none set."""
    return await _service(request, db).get_budget()


@router.post("/llm-budgets", response_model=LLMBudgetResponse)
async def create_llm_budget(
    request: Request,
    data: LLMBudgetCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create or replace the tenant's LLM budget (idempotent — only one row per tenant)."""
    return await _service(request, db).upsert_budget(
        monthly_budget_cents=data.monthly_budget_cents,
        alert_threshold_percent=data.alert_threshold_percent,
        model_overrides=data.model_overrides,
        notes=data.notes,
    )


@router.put("/llm-budgets", response_model=LLMBudgetResponse)
async def update_llm_budget(
    request: Request,
    data: LLMBudgetUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partial update. 404 if the tenant has no budget yet — use POST to create."""
    existing = await _service(request, db).get_budget()
    if existing is None:
        raise HTTPException(status_code=404, detail="No budget set for this tenant")
    return await _service(request, db).upsert_budget(
        monthly_budget_cents=data.monthly_budget_cents
        if data.monthly_budget_cents is not None
        else existing["monthly_budget_cents"],
        alert_threshold_percent=data.alert_threshold_percent
        if data.alert_threshold_percent is not None
        else existing["alert_threshold_percent"],
        model_overrides=data.model_overrides
        if data.model_overrides is not None
        else existing.get("model_overrides"),
        notes=data.notes if data.notes is not None else existing.get("notes"),
    )
