"""V4-1 tests for the Workshop runtime.

Tests target the **pure** helpers in ``workshop_runtime_helpers`` so we
can run them without a database. The SQL-bound executor is exercised
in the CI workflow against a live PostgreSQL.
"""

import importlib.util
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(
        name, str(BACKEND_ROOT / relpath)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _helpers():
    return _load("ws_helpers", "app/services/workshop_runtime_helpers.py")


def test_topological_order_linear_chain():
    h = _helpers()
    nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]
    order, has_cycle = h.topological_order(nodes, edges)
    assert has_cycle is False
    assert order == ["a", "b", "c"]


def test_topological_order_branching_tree():
    h = _helpers()
    nodes = [{"id": "root"}, {"id": "l"}, {"id": "r"}, {"id": "leaf"}]
    edges = [
        {"source": "root", "target": "l"},
        {"source": "root", "target": "r"},
        {"source": "l", "target": "leaf"},
    ]
    order, has_cycle = h.topological_order(nodes, edges)
    assert has_cycle is False
    assert order.index("root") < order.index("l")
    assert order.index("l") < order.index("leaf")
    assert order.index("root") < order.index("r")


def test_topological_order_cycle_detected():
    h = _helpers()
    nodes = [{"id": "a"}, {"id": "b"}]
    edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]
    order, has_cycle = h.topological_order(nodes, edges)
    assert has_cycle is True
    assert order == []


def test_topological_order_self_loop_detected():
    h = _helpers()
    nodes = [{"id": "a"}]
    edges = [{"source": "a", "target": "a"}]
    order, has_cycle = h.topological_order(nodes, edges)
    assert has_cycle is True


def test_filter_equality_string():
    h = _helpers()
    item = {"status": "active", "name": "Alice"}
    assert h.eval_filter(item, "status", "==", "active") is True
    assert h.eval_filter(item, "status", "==", "inactive") is False


def test_filter_inequality_and_comparisons():
    h = _helpers()
    item = {"count": 10, "score": 95}
    assert h.eval_filter(item, "count", "!=", 0) is True
    assert h.eval_filter(item, "count", ">", 5) is True
    assert h.eval_filter(item, "count", ">", 100) is False
    assert h.eval_filter(item, "score", ">=", 95) is True
    assert h.eval_filter(item, "score", "<", 100) is True
    assert h.eval_filter(item, "score", "<=", 95) is True


def test_filter_contains():
    h = _helpers()
    item = {"name": "engineering"}
    assert h.eval_filter(item, "name", "contains", "engineer") is True
    assert h.eval_filter(item, "name", "contains", "marketing") is False


def test_filter_in():
    h = _helpers()
    # The MVP "in" operator checks substring containment (the value
    # field is single-valued; full set-membership is v2.4.1).
    assert h.eval_filter({"name": "engineering"}, "name", "in", "engineer") is True
    assert h.eval_filter({"name": "engineering"}, "name", "in", "marketing") is False


def test_filter_coerces_string_literals():
    """Filter values come from a text input — they should match typed properties."""
    h = _helpers()
    # The user typed "123" into the value field; the property is an int.
    assert h.eval_filter({"count": 123}, "count", "==", "123") is True
    assert h.eval_filter({"flag": True}, "flag", "==", "true") is True
    assert h.eval_filter({"flag": False}, "flag", "==", "false") is True


def test_filter_type_mismatch_returns_false_not_raises():
    h = _helpers()
    # Comparing a string to an int via ">" would raise TypeError; we
    # treat that as a non-match (no false positives).
    assert h.eval_filter({"name": "alice"}, "name", ">", 5) is False


def test_coerce_compare_basic():
    h = _helpers()
    assert h.coerce_compare("42") == 42
    assert h.coerce_compare("3.14") == 3.14
    assert h.coerce_compare("true") is True
    assert h.coerce_compare("false") is False
    assert h.coerce_compare("hello") == "hello"
    assert h.coerce_compare(7) == 7  # non-strings pass through


def test_first_upstream_id_returns_none_when_no_edge():
    h = _helpers()
    assert h.first_upstream_id("c", [], [{"id": "c"}]) is None
    assert h.first_upstream_id("c", [{"source": "a", "target": "c"}], []) is None
    # Both nodes known
    assert h.first_upstream_id("c",
        [{"source": "a", "target": "c"}],
        [{"id": "a"}, {"id": "c"}]) == "a"
