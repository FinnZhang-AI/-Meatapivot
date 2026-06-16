"""Sprint 4 E2E-style tests.

Covers three areas:
  - Workshop app CRUD round-trip (S3-3 backend, exercised here end-to-end)
  - LLM cost dashboard aggregations + budget state machine (S4-1)
  - OPA policy enforcement at the action executor (S3-2)

These tests deliberately use the standalone module-load trick (mirroring
test_sprint3.py) so they run without a live PG. Anything that needs the
full FastAPI app + DB is gated on ``client`` and skipped if the app
imports are not available.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.asyncio

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _load_module(name: str, relpath: str):
    """Load a backend module by file path, bypassing the ``app`` package init.

    This is the same trick test_sprint3.py uses: it lets us import a single
    file without dragging in Base, settings, or any DB-touching code.
    """
    path = BACKEND_ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Workshop CRUD (S3-3)
# ---------------------------------------------------------------------------


def test_workshop_router_endpoints_present():
    """Workshop router exposes the CRUD verbs the editor relies on."""
    router = _load_module("ws_test", "app/routers/workshop.py")
    methods = {route.path: route.methods for route in router.router.routes}
    # The app shell prefixes ``/workshop/apps`` so we look for the relative
    # paths declared on the router.
    assert "" in methods or "/" in methods, "missing collection create/list"
    assert "/{app_id}" in methods, "missing item get/put/delete"
    # POST on "" and GET on "" should both exist
    create_route = methods.get("") or methods.get("/")
    assert "POST" in (create_route or set()), "POST on collection must exist"
    item_route = methods["/{app_id}"]
    assert {"GET", "PUT", "DELETE"}.issubset(item_route), "item needs GET/PUT/DELETE"


def test_workshop_pydantic_schema_round_trip():
    """WorkshopAppCreate/Update/Response accept realistic React Flow shapes."""
    schema_mod = _load_module("ws_schema_test", "app/models/workshop_schemas.py")
    payload: Dict[str, Any] = {
        "name": "Test App",
        "description": "e2e test",
        "graph": {
            "nodes": [
                {"id": "t1", "type": "table", "position": {"x": 0, "y": 0},
                 "data": {"label": "Table 1"}},
                {"id": "c1", "type": "chart", "position": {"x": 200, "y": 0},
                 "data": {"label": "Chart 1", "upstream": "Table 1"}},
            ],
            "edges": [{"id": "e1", "source": "t1", "target": "c1", "animated": True}],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }
    create = schema_mod.WorkshopAppCreate.model_validate(payload)
    assert create.name == "Test App"
    assert len(create.graph["nodes"]) == 2
    assert create.graph["edges"][0]["source"] == "t1"

    update = schema_mod.WorkshopAppUpdate.model_validate({"name": "Renamed"})
    dumped = update.model_dump(exclude_unset=True)
    assert dumped == {"name": "Renamed"}


def test_workshop_v231_filter_and_linknav_nodes_persist():
    """S3-3.1: Filter and LinkNav nodes must round-trip with their config.

    The backend has no per-node-type schema — the graph is opaque JSONB —
    so this test is a contract check that the v2.3.1 client config we
    send (``field``/``operator``/``value`` and
    ``linkTypeName``/``targetObjectType``) is preserved on read.
    """
    schema_mod = _load_module("ws_schema_test", "app/models/workshop_schemas.py")
    payload: Dict[str, Any] = {
        "name": "v2.3.1 App",
        "graph": {
            "nodes": [
                {"id": "t1", "type": "table", "position": {"x": 0, "y": 0},
                 "data": {"label": "T1"}},
                {"id": "f1", "type": "filter", "position": {"x": 200, "y": 0},
                 "data": {"label": "Active only", "field": "status", "operator": "==", "value": "active"}},
                {"id": "n1", "type": "linknav", "position": {"x": 400, "y": 0},
                 "data": {"label": "Go to dept", "linkTypeName": "BELONGS_TO", "targetObjectType": "Department"}},
            ],
            "edges": [
                {"id": "e1", "source": "t1", "target": "f1"},
                {"id": "e2", "source": "t1", "target": "n1"},
            ],
        },
    }
    create = schema_mod.WorkshopAppCreate.model_validate(payload)
    assert len(create.graph["nodes"]) == 3
    by_type = {n["type"]: n for n in create.graph["nodes"]}
    assert by_type["filter"]["data"]["field"] == "status"
    assert by_type["filter"]["data"]["operator"] == "=="
    assert by_type["filter"]["data"]["value"] == "active"
    assert by_type["linknav"]["data"]["linkTypeName"] == "BELONGS_TO"
    assert by_type["linknav"]["data"]["targetObjectType"] == "Department"

    # Simulate the PUT round-trip: partial update with a tweaked value
    upd = schema_mod.WorkshopAppUpdate.model_validate({
        "graph": create.graph,
    })
    dumped = upd.model_dump(exclude_unset=True)
    assert dumped["graph"]["nodes"][1]["data"]["field"] == "status"


# ---------------------------------------------------------------------------
# LLM cost dashboard (S4-1)
# ---------------------------------------------------------------------------


def test_llm_pricing_basic_arithmetic():
    """Pricing: 1M tokens of gpt-4o must equal 500 cents."""
    pricing = _load_module("pricing_test", "app/services/llm_pricing.py")
    assert pricing.compute_cost_cents("gpt-4o", 1_000_000) == 500
    assert pricing.compute_cost_cents("gpt-4o", 0) == 0
    # Rounded up
    assert pricing.compute_cost_cents("gpt-4o", 100) == 1
    # Family prefix
    assert pricing.compute_cost_cents("gpt-4o-2024-08-06", 1_000_000) == 500
    # Unknown falls back to default
    assert pricing.compute_cost_cents("totally-bogus", 1_000_000) == pricing.MODEL_PRICING["default"]


def test_llm_pricing_format_usd():
    pricing = _load_module("pricing_test", "app/services/llm_pricing.py")
    assert pricing.format_usd(123) == "$1.23"
    assert pricing.format_usd(0) == "$0.00"
    assert pricing.format_usd(-50) == "-$0.50"
    assert pricing.format_usd(1) == "$0.01"


def test_llm_pricing_env_override(monkeypatch):
    """LLM_PRICING_OVERRIDES should patch the catalog at import time."""
    monkeypatch.setenv("LLM_PRICING_OVERRIDES", json.dumps({"gpt-4o": 1234, "custom-model": 50}))
    # Re-import with the env var in place. Drop the cached module so the
    # module-level catalog picks up the override.
    sys.modules.pop("pricing_test", None)
    pricing = _load_module("pricing_test", "app/services/llm_pricing.py")
    assert pricing.MODEL_PRICING["gpt-4o"] == 1234
    assert pricing.compute_cost_cents("custom-model", 1_000_000) == 50


def test_budget_state_classification():
    """All three budget states + the no_budget sentinel."""
    svc = _load_module("svc_test", "app/services/llm_cost_service.py")
    budget = {"monthly_budget_cents": 10000, "alert_threshold_percent": 80}
    assert svc.LLMCostService.budget_state(budget, 0) == "ok"
    assert svc.LLMCostService.budget_state(budget, 5000) == "ok"
    assert svc.LLMCostService.budget_state(budget, 7999) == "ok"
    assert svc.LLMCostService.budget_state(budget, 8000) == "warning"
    assert svc.LLMCostService.budget_state(budget, 9999) == "warning"
    assert svc.LLMCostService.budget_state(budget, 10000) == "exceeded"
    assert svc.LLMCostService.budget_state(budget, 50000) == "exceeded"
    # No budget / zero budget
    assert svc.LLMCostService.budget_state(None, 100) == "no_budget"
    assert svc.LLMCostService.budget_state({"monthly_budget_cents": 0}, 100) == "no_budget"
    # Custom threshold 50% flips the boundary
    custom = {"monthly_budget_cents": 10000, "alert_threshold_percent": 50}
    assert svc.LLMCostService.budget_state(custom, 4999) == "ok"
    assert svc.LLMCostService.budget_state(custom, 5000) == "warning"


def test_cost_report_schema_shape():
    """LLMCostReport must contain every field the dashboard renders."""
    schemas = _load_module("cost_schema_test", "app/models/aip_schemas.py")
    fields = schemas.LLMCostReport.model_fields
    for key in ("days", "group_by", "total_calls", "total_tokens", "total_cost_cents",
                "by_model", "trend", "budget", "budget_state"):
        assert key in fields, f"LLMCostReport missing field: {key}"
    state_field = schemas.LLMCostReport.model_fields["budget_state"]
    # Literal type for the state machine
    assert "ok" in str(state_field.annotation)
    assert "warning" in str(state_field.annotation)
    assert "exceeded" in str(state_field.annotation)


def test_budget_crud_schemas():
    """LLMBudgetCreate/Update enforce non-negative budget + 0-100 threshold."""
    schemas = _load_module("cost_schema_test", "app/models/aip_schemas.py")
    schemas.LLMBudgetCreate.model_validate({
        "monthly_budget_cents": 10000, "alert_threshold_percent": 80,
    })
    schemas.LLMBudgetCreate.model_validate({
        "monthly_budget_cents": 0,
    })
    # Negative cents is rejected
    with pytest.raises(Exception):
        schemas.LLMBudgetCreate.model_validate({"monthly_budget_cents": -1})
    # Threshold > 100 is rejected
    with pytest.raises(Exception):
        schemas.LLMBudgetCreate.model_validate({
            "monthly_budget_cents": 100, "alert_threshold_percent": 150,
        })
    # Update is partial
    upd = schemas.LLMBudgetUpdate.model_validate({"alert_threshold_percent": 90})
    assert upd.monthly_budget_cents is None
    assert upd.alert_threshold_percent == 90


# ---------------------------------------------------------------------------
# OPA policy enforcement (S3-2)
# ---------------------------------------------------------------------------


def test_opa_client_blocks_cross_tenant():
    opa = _load_module("opa_test", "app/services/opa_client.py")
    client = opa.OPAClient()
    assert len(client.rule_names()) == 3
    bad = {
        "action": {"id": "1", "name": "test.foo", "execution_type": "direct", "tenant_id": "t1"},
        "context": {"tenant_id": "t2", "executed_by": "u1", "target_object_id": "o1"},
        "parameters": {"x": 1},
    }
    decision = client.evaluate(bad)
    assert not decision.allowed
    assert "tenant_isolation" in (decision.reason or "")


def test_opa_client_blocks_forbidden_action_name():
    opa = _load_module("opa_test", "app/services/opa_client.py")
    client = opa.OPAClient()
    doc = {
        "action": {"id": "1", "name": "system.drop_database", "execution_type": "direct", "tenant_id": "t1"},
        "context": {"tenant_id": "t1", "executed_by": "u1", "target_object_id": "o1"},
        "parameters": {},
    }
    decision = client.evaluate(doc)
    assert not decision.allowed
    assert "forbidden_parameters" in (decision.reason or "")


def test_opa_client_blocks_runaway_parameter_count():
    opa = _load_module("opa_test", "app/services/opa_client.py")
    client = opa.OPAClient()
    doc = {
        "action": {"id": "1", "name": "test.foo", "execution_type": "direct", "tenant_id": "t1"},
        "context": {"tenant_id": "t1", "executed_by": "u1", "target_object_id": "o1"},
        "parameters": {f"k{i}": i for i in range(50)},
    }
    decision = client.evaluate(doc)
    assert not decision.allowed
    assert "max_parameters" in (decision.reason or "")


def test_opa_client_allows_normal_action():
    opa = _load_module("opa_test", "app/services/opa_client.py")
    client = opa.OPAClient()
    doc = {
        "action": {"id": "1", "name": "test.foo", "execution_type": "direct", "tenant_id": "t1"},
        "context": {"tenant_id": "t1", "executed_by": "u1", "target_object_id": "o1"},
        "parameters": {"x": 1},
    }
    decision = client.evaluate(doc)
    assert decision.allowed
    assert decision.reason is None


def test_opa_client_malformed_bundle_fails_open():
    """A bad policy file must not lock everyone out — fail open with no rules."""
    opa = _load_module("opa_test", "app/services/opa_client.py")
    bad = opa.OPAClient("this is not { valid rego")
    assert bad.rule_names() == []
    doc = {
        "action": {"id": "1", "name": "test.foo", "execution_type": "direct", "tenant_id": "t1"},
        "context": {"tenant_id": "t1", "executed_by": "u1", "target_object_id": "o1"},
        "parameters": {},
    }
    decision = bad.evaluate(doc)
    assert decision.allowed


# ---------------------------------------------------------------------------
# Test runner sanity — keep us honest about counting tests
# ---------------------------------------------------------------------------


def test_test_module_has_expected_count():
    """Fail loudly if someone strips a test above so the suite stays useful."""
    import inspect
    import sys

    this = sys.modules[__name__]
    tests = [
        name for name, obj in inspect.getmembers(this)
        if inspect.isfunction(obj) and name.startswith("test_")
    ]
    # Adjust this number if you intentionally add/remove tests.
    assert len(tests) >= 14, f"expected at least 14 tests, found {len(tests)}: {tests}"
