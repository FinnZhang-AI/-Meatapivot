"""Workshop graph runtime executor — V4-1.

The executor is intentionally **stateless per call**: it loads the
graph from the database, snapshots it, and walks the nodes in a
topological order (DFS, with cycle protection). For each node it
dispatches to a handler keyed on the React Flow ``type`` string:

  - ``table``    — query ontology_objects by the configured
                   object_type_id (looked up by name)
  - ``filter``   — apply field/operator/value against the upstream
                   node's output (a list of objects)
  - ``chart``    — group_by + count the upstream output; emit a
                   chart-ready summary
  - ``linknav``  — locate the LinkType by name and emit the target
                   ObjectType's instance list
  - ``action``   — delegate to the existing ActionExecutor (S3-2
                   OPA path applies)

Errors are isolated: a single node failure does not block the rest of
the graph. The final ``WorkshopExecution`` row reflects ``partial``
when at least one node errored but the rest completed.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ontology_models import (
    ActionExecutionLog,
    OntologyActionType,
    OntologyLinkType,
    OntologyObject,
    OntologyObjectType,
)
from app.models.workshop_models import WorkshopApp, WorkshopExecution
from app.services.action_executor import ActionExecutor
from app.services.workshop_runtime_helpers import (
    topological_order,
    coerce_compare,
    eval_filter,
    first_upstream_id,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_workshop(
    db: AsyncSession,
    tenant_id: UUID,
    app_id: UUID,
    triggered_by: Optional[UUID] = None,
    node_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
) -> WorkshopExecution:
    """Execute a workshop app once. Returns the persisted ``WorkshopExecution``.

    The function is synchronous from the caller's POV: the graph is small
    enough (we cap execution time implicitly by per-node timeouts the
    underlying services already enforce) that streaming is unnecessary
    in v2.4. V4.1 will replace this with a Celery + SSE path if real
    apps turn out to be slow.
    """
    started_at = time.time()
    node_overrides = node_overrides or {}

    # Load the app
    app_row = await db.execute(
        select(WorkshopApp).where(
            WorkshopApp.id == app_id, WorkshopApp.tenant_id == tenant_id
        )
    )
    app = app_row.scalar_one_or_none()
    if app is None:
        raise ValueError(f"Workshop app {app_id} not found")

    graph = app.graph or {}
    raw_nodes: List[Dict[str, Any]] = list(graph.get("nodes") or [])
    raw_edges: List[Dict[str, Any]] = list(graph.get("edges") or [])

    # Create the execution row up front so the caller can poll its id.
    execution = WorkshopExecution(
        tenant_id=tenant_id,
        app_id=app_id,
        status="running",
        graph_snapshot={"nodes": raw_nodes, "edges": raw_edges},
        results={},
        triggered_by=triggered_by,
    )
    db.add(execution)
    await db.flush()

    # Topological order
    order, has_cycle = topological_order(raw_nodes, raw_edges)

    # Per-node results keyed by id
    results: Dict[str, Dict[str, Any]] = {}
    upstream_cache: Dict[str, Any] = {}  # node_id -> emitted output

    # Start with "skipped" entries for everything; we'll overwrite as we go.
    for n in raw_nodes:
        nid = n.get("id")
        if nid:
            results[nid] = {
                "node_id": nid,
                "node_type": n.get("type") or "unknown",
                "status": "skipped" if has_cycle else "pending",
                "output": None,
                "error": None,
                "duration_ms": None,
            }

    if has_cycle:
        for nid in results:
            results[nid]["status"] = "error"
            results[nid]["error"] = "Graph contains a cycle; cannot execute"
        execution.status = "failed"
        execution.error_message = "Graph contains a cycle"
        execution.results = results
        execution.completed_at = _now()
        execution.duration_ms = int((time.time() - started_at) * 1000)
        await db.flush()
        return execution

    # Walk in topo order
    any_error = False
    for nid in order:
        node = next((n for n in raw_nodes if n.get("id") == nid), None)
        if node is None:
            continue
        node_type = node.get("type") or "unknown"
        node_data = dict(node.get("data") or {})
        # Apply caller overrides on top of saved config
        if nid in node_overrides:
            node_data.update(node_overrides[nid])

        result = results[nid]
        result["status"] = "running"
        result["node_type"] = node_type
        node_start = time.time()

        try:
            output = await _dispatch_node(
                db=db,
                tenant_id=tenant_id,
                node_id=nid,
                node_type=node_type,
                node_data=node_data,
                upstream=upstream_cache,
                raw_nodes=raw_nodes,
                raw_edges=raw_edges,
            )
            result["output"] = output
            result["status"] = "done"
            # Chart nodes don't propagate (they're sinks); Filter and Table
            # do. LinkNav emits a list of dicts; Action emits a result dict.
            if node_type in ("table", "filter", "linknav"):
                upstream_cache[nid] = output
        except Exception as exc:  # noqa: BLE001 — errors are isolated
            any_error = True
            result["status"] = "error"
            result["error"] = str(exc)[:1000]
            logger.exception(f"Workshop node {nid} ({node_type}) failed")

        result["duration_ms"] = int((time.time() - node_start) * 1000)

    duration_ms = int((time.time() - started_at) * 1000)
    if any_error:
        # Partial if at least one succeeded; failed if all failed.
        any_done = any(r["status"] == "done" for r in results.values())
        execution.status = "partial" if any_done else "failed"
    else:
        execution.status = "completed"

    execution.results = results
    execution.completed_at = _now()
    execution.duration_ms = duration_ms
    await db.flush()
    return execution


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


async def _dispatch_node(
    db: AsyncSession,
    tenant_id: UUID,
    node_id: str,
    node_type: str,
    node_data: Dict[str, Any],
    upstream: Dict[str, Any],
    raw_nodes: List[Dict[str, Any]],
    raw_edges: List[Dict[str, Any]],
) -> Any:
    handler = _HANDLERS.get(node_type)
    if handler is None:
        # Unknown node type is a soft error, not a hard raise — the editor
        # may have a node the runtime doesn't know about yet.
        return {
            "node_id": node_id,
            "node_type": node_type,
            "warning": f"Unknown node type: {node_type}",
        }
    return await handler(
        db=db,
        tenant_id=tenant_id,
        node_id=node_id,
        node_data=node_data,
        upstream=upstream,
        raw_nodes=raw_nodes,
        raw_edges=raw_edges,
    )


async def _run_table(
    db: AsyncSession,
    tenant_id: UUID,
    node_id: str,
    node_data: Dict[str, Any],
    upstream: Dict[str, Any],
    raw_nodes: List[Dict[str, Any]],
    raw_edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Emit the list of ontology_objects of the configured ObjectType.

    The Table node stores ``objectTypeName`` (display label) so we
    resolve that to an id and then call the repository. ``object_type_id``
    is the alternative path when the editor persists a raw UUID.
    """
    ot_id = node_data.get("objectTypeId") or node_data.get("object_type_id")
    ot_name = node_data.get("objectTypeName") or node_data.get("objectType")
    if not ot_id and not ot_name:
        return {"node_id": node_id, "items": [], "count": 0,
                "warning": "Table node has no objectTypeName configured"}

    if not ot_id:
        ot_row = await db.execute(
            select(OntologyObjectType.id).where(
                OntologyObjectType.tenant_id == tenant_id,
                OntologyObjectType.name == ot_name,
            )
        )
        ot_id = ot_row.scalar_one_or_none()
        if ot_id is None:
            return {"node_id": node_id, "items": [], "count": 0,
                    "warning": f"ObjectType {ot_name!r} not found"}

    items = await _list_objects(db, tenant_id, ot_id)
    return {
        "node_id": node_id,
        "object_type_id": str(ot_id),
        "items": items,
        "count": len(items),
    }


async def _run_filter(
    db: AsyncSession,
    tenant_id: UUID,
    node_id: str,
    node_data: Dict[str, Any],
    upstream: Dict[str, Any],
    raw_nodes: List[Dict[str, Any]],
    raw_edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Filter the upstream node's items list using a field/operator/value triple."""
    source_id = first_upstream_id(node_id, raw_edges, raw_nodes)
    upstream_output = upstream.get(source_id) if source_id else None
    if upstream_output is None:
        return {"node_id": node_id, "items": [], "count": 0,
                "warning": "Filter has no upstream Table"}

    items = list(upstream_output.get("items") or [])
    field = node_data.get("field")
    operator = node_data.get("operator") or "=="
    value = node_data.get("value")
    if not field:
        return {"node_id": node_id, "items": items, "count": len(items),
                "warning": "Filter has no field configured"}

    kept = [it for it in items if eval_filter(it, field, operator, value)]
    return {
        "node_id": node_id,
        "items": kept,
        "count": len(kept),
        "filter": {"field": field, "operator": operator, "value": value},
    }


async def _run_chart(
    db: AsyncSession,
    tenant_id: UUID,
    node_id: str,
    node_data: Dict[str, Any],
    upstream: Dict[str, Any],
    raw_nodes: List[Dict[str, Any]],
    raw_edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Group upstream items by a field and emit chart-ready series.

    Optional ``groupBy`` field on the chart config controls the
    dimension. If unset, we fall back to a "type" field if present,
    else a single bucket of the count.
    """
    source_id = first_upstream_id(node_id, raw_edges, raw_nodes)
    upstream_output = upstream.get(source_id) if source_id else None
    if upstream_output is None:
        return {"node_id": node_id, "series": [], "warning": "Chart has no upstream"}

    items = upstream_output.get("items") or []
    group_by = node_data.get("groupBy") or node_data.get("group_by")
    if not group_by:
        # Try common fields
        for candidate in ("status", "type", "category", "object_type"):
            if any(candidate in (it or {}) for it in items):
                group_by = candidate
                break

    if not group_by:
        return {
            "node_id": node_id,
            "series": [{"name": "All", "value": len(items)}],
            "total": len(items),
        }

    buckets: Dict[str, int] = {}
    for it in items:
        key = str((it or {}).get(group_by, "unknown"))
        buckets[key] = buckets.get(key, 0) + 1
    series = [{"name": k, "value": v} for k, v in
              sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)]
    return {"node_id": node_id, "group_by": group_by, "series": series, "total": len(items)}


async def _run_linknav(
    db: AsyncSession,
    tenant_id: UUID,
    node_id: str,
    node_data: Dict[str, Any],
    upstream: Dict[str, Any],
    raw_nodes: List[Dict[str, Any]],
    raw_edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Find the LinkType and emit a sample of the target ObjectType's instances.

    The MVP does not actually traverse a specific source object — it
    just shows the first N instances of the target ObjectType as a
    preview. v2.4.1 will pick a real source object from upstream.
    """
    link_name = node_data.get("linkTypeName") or node_data.get("linkType")
    target_name = node_data.get("targetObjectType") or node_data.get("targetType")
    if not link_name:
        return {"node_id": node_id, "items": [], "count": 0,
                "warning": "LinkNav has no linkTypeName configured"}

    lt_row = await db.execute(
        select(OntologyLinkType).where(
            OntologyLinkType.tenant_id == tenant_id,
            OntologyLinkType.name == link_name,
        )
    )
    lt = lt_row.scalar_one_or_none()
    if lt is None:
        return {"node_id": node_id, "items": [], "count": 0,
                "warning": f"LinkType {link_name!r} not found"}

    # Resolve target OT (configured or fall back to link_type's target)
    target_ot_id = lt.target_object_type_id
    if target_name:
        ot_row = await db.execute(
            select(OntologyObjectType.id).where(
                OntologyObjectType.tenant_id == tenant_id,
                OntologyObjectType.name == target_name,
            )
        )
        resolved = ot_row.scalar_one_or_none()
        if resolved is not None:
            target_ot_id = resolved

    sample = await _list_objects(db, tenant_id, target_ot_id, limit=20)
    return {
        "node_id": node_id,
        "link_type_id": str(lt.id),
        "link_type_name": lt.name,
        "target_object_type_id": str(target_ot_id),
        "items": sample,
        "count": len(sample),
    }


async def _run_action(
    db: AsyncSession,
    tenant_id: UUID,
    node_id: str,
    node_data: Dict[str, Any],
    upstream: Dict[str, Any],
    raw_nodes: List[Dict[str, Any]],
    raw_edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Delegate to the existing ActionExecutor.

    The action node stores ``actionTypeName`` (and optionally
    ``targetObjectKey`` from upstream). We resolve the action type by
    name, look up the target object from upstream Table's first item,
    and run the executor.
    """
    action_name = node_data.get("actionTypeName") or node_data.get("actionType")
    if not action_name:
        return {"node_id": node_id, "warning": "Action has no actionTypeName configured"}

    at_row = await db.execute(
        select(OntologyActionType).where(
            OntologyActionType.tenant_id == tenant_id,
            OntologyActionType.name == action_name,
        )
    )
    at = at_row.scalar_one_or_none()
    if at is None:
        return {"node_id": node_id, "warning": f"ActionType {action_name!r} not found"}

    # Pick the first upstream object as the target
    source_id = first_upstream_id(node_id, raw_edges, raw_nodes)
    upstream_output = upstream.get(source_id) if source_id else None
    items = (upstream_output or {}).get("items") or []
    target_object_id = items[0]["id"] if items and isinstance(items[0], dict) and "id" in items[0] else None

    if target_object_id is None:
        return {"node_id": node_id, "warning": "Action has no upstream object to act on"}

    parameters = node_data.get("parameters") or {}
    executor = ActionExecutor(db, tenant_id)
    result = await executor.execute(
        action_type_id=at.id,
        target_object_id=UUID(str(target_object_id)),
        parameters=parameters,
    )
    # ActionExecutor returns ActionExecuteResponse with success/result/message
    return {
        "node_id": node_id,
        "action_type_id": str(at.id),
        "action_type_name": at.name,
        "success": getattr(result, "success", None),
        "message": getattr(result, "message", None),
        "result": getattr(result, "result", None),
        "blocked": not bool(getattr(result, "success", False)),
    }


_HANDLERS = {
    "table": _run_table,
    "filter": _run_filter,
    "chart": _run_chart,
    "linknav": _run_linknav,
    "action": _run_action,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now():
    from datetime import datetime
    return datetime.utcnow()


async def _list_objects(
    db: AsyncSession,
    tenant_id: UUID,
    object_type_id: UUID,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    rows = await db.execute(
        select(OntologyObject)
        .where(
            OntologyObject.tenant_id == tenant_id,
            OntologyObject.object_type_id == object_type_id,
            OntologyObject.status != "archived",
        )
        .order_by(OntologyObject.created_at.desc())
        .limit(limit)
    )
    out: List[Dict[str, Any]] = []
    for row in rows.scalars().all():
        out.append({
            "id": str(row.id),
            "object_key": row.object_key,
            "properties": row.properties or {},
            "status": row.status,
        })
    return out


__all__ = [
    "run_workshop",
]
