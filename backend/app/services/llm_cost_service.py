"""LLM cost aggregation service — S4-1.

Three layers:

  - ``summary()``  — one-shot aggregation: total tokens / cost / calls
    across the last N days for a tenant, with per-model breakdown and a
    daily trend.
  - ``budget_state()`` — given a ``LLMBudget`` and the current month's
    spend, classify as ok / warning / exceeded.
  - ``csv_rows()`` — flatten per-call rows for CSV export. Uses the
    stored ``estimated_cost_cents`` when present and recomputes from
    ``total_tokens`` otherwise (see ``llm_pricing.compute_cost_cents``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_budget_models import LLMBudget
from app.models.ontology_models import AIPLLMCall
from app.services.llm_pricing import compute_cost_cents, format_usd

logger = logging.getLogger(__name__)


class LLMCostService:
    def __init__(self, db: AsyncSession, tenant_id: UUID) -> None:
        self.db = db
        self.tenant_id = tenant_id

    # ------------------------------------------------------------------
    # Aggregations
    # ------------------------------------------------------------------

    async def summary(self, days: int = 30, group_by: str = "day") -> Dict[str, Any]:
        """Return a dict matching the LLMCostReport schema, populated.

        ``group_by`` may be ``"day"`` or ``"hour"`` — controls the trend
        bucket size. ``days`` is clamped to [1, 90] to keep the SQL
        window sane.
        """
        days = max(1, min(days, 90))
        group_by = "hour" if group_by not in ("day", "hour") else group_by
        bucket_seconds = 3600 if group_by == "hour" else 86400
        bucket_count = days * (24 if group_by == "hour" else 1)

        cutoff_expr = func.now() - func.make_interval(0, 0, 0, 0, 0, 0, days)
        epoch = func.extract("epoch", AIPLLMCall.created_at)
        bucket_idx = func.floor(epoch / bucket_seconds).cast(AIPLLMCall.id.type)
        bucket_start = func.to_timestamp(bucket_idx * bucket_seconds)

        # Per-model breakdown
        by_model_rows = await self.db.execute(
            select(
                AIPLLMCall.model,
                func.count().label("call_count"),
                func.coalesce(func.sum(AIPLLMCall.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(AIPLLMCall.estimated_cost_cents), 0).label(
                    "estimated_cost_cents"
                ),
            )
            .where(AIPLLMCall.tenant_id == self.tenant_id)
            .where(AIPLLMCall.created_at >= cutoff_expr)
            .group_by(AIPLLMCall.model)
            .order_by(func.sum(AIPLLMCall.estimated_cost_cents).desc())
        )
        by_model = [
            {
                "model": row[0] or "unknown",
                "call_count": int(row[1] or 0),
                "total_tokens": int(row[2] or 0),
                "estimated_cost_cents": int(row[3] or 0),
            }
            for row in by_model_rows.all()
        ]

        # Trend buckets
        trend_rows = await self.db.execute(
            select(
                bucket_start.label("bucket"),
                func.count().label("call_count"),
                func.coalesce(func.sum(AIPLLMCall.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(AIPLLMCall.estimated_cost_cents), 0).label(
                    "estimated_cost_cents"
                ),
            )
            .where(AIPLLMCall.tenant_id == self.tenant_id)
            .where(AIPLLMCall.created_at >= cutoff_expr)
            .group_by("bucket")
            .order_by("bucket")
        )
        seen: Dict[str, Dict[str, int]] = {}
        for row in trend_rows.all():
            bucket_dt = row.bucket
            if hasattr(bucket_dt, "isoformat"):
                key = bucket_dt.isoformat(timespec="minutes")
            else:
                key = str(bucket_dt)
            seen[key] = {
                "call_count": int(row.call_count or 0),
                "total_tokens": int(row.total_tokens or 0),
                "estimated_cost_cents": int(row.estimated_cost_cents or 0),
            }

        # Fill empty buckets so the chart axis is contiguous
        now = datetime.utcnow()
        if group_by == "day":
            anchor = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            anchor = now.replace(minute=0, second=0, microsecond=0)
        trend: List[Dict[str, Any]] = []
        for offset in range(bucket_count - 1, -1, -1):
            ts = anchor - timedelta(seconds=bucket_seconds * offset)
            key = ts.isoformat(timespec="minutes")
            point = seen.get(key, {"call_count": 0, "total_tokens": 0, "estimated_cost_cents": 0})
            trend.append({"bucket": key, **point})

        # Totals
        total_calls = sum(m["call_count"] for m in by_model)
        total_tokens = sum(m["total_tokens"] for m in by_model)
        total_cost = sum(m["estimated_cost_cents"] for m in by_model)

        # Budget lookup + state
        budget = await self.get_budget()
        budget_state = self.budget_state(budget, total_cost) if budget else "no_budget"

        return {
            "tenant_id": str(self.tenant_id),
            "days": days,
            "group_by": group_by,
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "total_cost_cents": total_cost,
            "by_model": by_model,
            "trend": trend,
            "budget": budget,
            "budget_state": budget_state,
        }

    # ------------------------------------------------------------------
    # Budget
    # ------------------------------------------------------------------

    async def get_budget(self) -> Optional[Dict[str, Any]]:
        result = await self.db.execute(
            select(LLMBudget).where(LLMBudget.tenant_id == self.tenant_id)
        )
        budget = result.scalar_one_or_none()
        if not budget:
            return None
        return _budget_to_dict(budget)

    async def upsert_budget(
        self,
        monthly_budget_cents: int,
        alert_threshold_percent: int = 80,
        model_overrides: Optional[Dict[str, int]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self.db.execute(
            select(LLMBudget).where(LLMBudget.tenant_id == self.tenant_id)
        )
        budget = result.scalar_one_or_none()
        if budget is None:
            budget = LLMBudget(
                tenant_id=self.tenant_id,
                monthly_budget_cents=monthly_budget_cents,
                alert_threshold_percent=alert_threshold_percent,
                model_overrides=json.dumps(model_overrides) if model_overrides else None,
                notes=notes,
            )
            self.db.add(budget)
        else:
            budget.monthly_budget_cents = monthly_budget_cents
            budget.alert_threshold_percent = alert_threshold_percent
            if model_overrides is not None:
                budget.model_overrides = json.dumps(model_overrides)
            if notes is not None:
                budget.notes = notes

        await self.db.flush()
        await self.db.refresh(budget)
        return _budget_to_dict(budget)

    @staticmethod
    def budget_state(budget: Dict[str, Any], current_cost_cents: int) -> str:
        """Classify current spend vs. budget.

        Returns one of ``ok`` / ``warning`` / ``exceeded``.
        """
        if not budget or not budget.get("monthly_budget_cents"):
            return "no_budget"
        cap = budget["monthly_budget_cents"]
        threshold_pct = budget.get("alert_threshold_percent", 80) / 100.0
        ratio = current_cost_cents / cap if cap else 0
        if ratio >= 1.0:
            return "exceeded"
        if ratio >= threshold_pct:
            return "warning"
        return "ok"

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    async def csv_rows(self, days: int = 30) -> List[Dict[str, Any]]:
        """Return per-call rows for the CSV export endpoint."""
        days = max(1, min(days, 90))
        cutoff_expr = func.now() - func.make_interval(0, 0, 0, 0, 0, 0, days)
        result = await self.db.execute(
            select(
                AIPLLMCall.id,
                AIPLLMCall.created_at,
                AIPLLMCall.model,
                AIPLLMCall.provider,
                AIPLLMCall.prompt_tokens,
                AIPLLMCall.completion_tokens,
                AIPLLMCall.total_tokens,
                AIPLLMCall.estimated_cost_cents,
                AIPLLMCall.status,
            )
            .where(AIPLLMCall.tenant_id == self.tenant_id)
            .where(AIPLLMCall.created_at >= cutoff_expr)
            .order_by(AIPLLMCall.created_at.desc())
            .limit(10000)  # hard cap to keep the CSV from melting the browser
        )
        rows: List[Dict[str, Any]] = []
        for row in result.all():
            stored_cents = int(row.estimated_cost_cents or 0)
            if stored_cents == 0 and int(row.total_tokens or 0) > 0:
                stored_cents = compute_cost_cents(row.model or "default", int(row.total_tokens))
            rows.append({
                "id": str(row.id),
                "created_at": row.created_at.isoformat() if row.created_at else "",
                "model": row.model or "",
                "provider": row.provider or "",
                "prompt_tokens": int(row.prompt_tokens or 0),
                "completion_tokens": int(row.completion_tokens or 0),
                "total_tokens": int(row.total_tokens or 0),
                "estimated_cost_usd": f"{stored_cents / 100:.6f}",
                "status": row.status or "",
            })
        return rows


def _budget_to_dict(budget: LLMBudget) -> Dict[str, Any]:
    overrides: Optional[Dict[str, int]] = None
    if budget.model_overrides:
        try:
            overrides = json.loads(budget.model_overrides)
            # Coerce to int in case the operator stored them as strings
            overrides = {k: int(v) for k, v in overrides.items()}
        except (ValueError, TypeError, json.JSONDecodeError):
            logger.warning(
                f"Could not parse model_overrides for budget {budget.id}; returning null"
            )
            overrides = None
    return {
        "id": budget.id,
        "tenant_id": budget.tenant_id,
        "monthly_budget_cents": int(budget.monthly_budget_cents),
        "alert_threshold_percent": int(budget.alert_threshold_percent),
        "model_overrides": overrides,
        "notes": budget.notes,
        "created_at": budget.created_at,
        "updated_at": budget.updated_at,
    }


__all__ = ["LLMCostService", "format_usd"]
