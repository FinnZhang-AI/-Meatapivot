"""Pure helpers for the Workshop runtime — V4-1.

These have **no database / framework dependencies** so they can be
unit-tested in isolation. ``workshop_executor.py`` re-imports them
and combines them with SQLAlchemy-backed dispatch.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Topological order
# ---------------------------------------------------------------------------


def topological_order(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Tuple[List[str], bool]:
    """DFS-based topological sort. Returns ``(order, has_cycle)``.

    A back-edge into a gray node is a cycle. Cyclic graphs return
    ``has_cycle=True`` and an empty order list; callers short-circuit
    the rest of the run.

    We record each node's *post-order* number, then sort by that number
    ascending — the result is a topologically valid sequence (sources
    before targets) without needing to reverse an in-place append.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {n.get("id"): WHITE for n in nodes if n.get("id")}
    counter = [0]
    post: Dict[str, int] = {}
    has_cycle = False

    def visit(nid: str) -> None:
        nonlocal has_cycle
        c = color.get(nid, WHITE)
        if c == GRAY:
            has_cycle = True
            return
        if c == BLACK:
            return
        color[nid] = GRAY
        for e in edges:
            if e.get("source") == nid:
                visit(e.get("target"))
        color[nid] = BLACK
        post[nid] = counter[0]
        counter[0] += 1

    # Visit roots first so a linear chain executes in the user's
    # intended order.
    has_incoming = {e.get("target") for e in edges if e.get("target")}
    for n in nodes:
        nid = n.get("id")
        if not nid:
            continue
        if nid not in has_incoming:
            visit(nid)
    for n in nodes:
        nid = n.get("id")
        if not nid:
            continue
        if color.get(nid) == WHITE:
            visit(nid)

    if has_cycle:
        return [], True
    # Sort by post-order index *descending*: the first node to be
    # fully visited is the deepest leaf, so the highest number is a
    # root. Ascending would put the leaf first and reverse execution.
    order = sorted(post.keys(), key=lambda nid: post[nid], reverse=True)
    return order, False


# ---------------------------------------------------------------------------
# Filter evaluation
# ---------------------------------------------------------------------------


def coerce_compare(value: Any) -> Any:
    """Best-effort coercion for the Filter node's string-typed value.

    The Filter node stores ``value`` as a string (it comes from a text
    input), so ``"active" == "active"`` matches but ``"123" == 123``
    would miss in a strict comparison. We try int/float/bool coercion
    on the right-hand side and on the property's value before the
    comparison.
    """
    if isinstance(value, str):
        s = value.strip()
        if s.lower() in ("true", "false"):
            return s.lower() == "true"
        try:
            return int(s)
        except ValueError:
            pass
        try:
            return float(s)
        except ValueError:
            pass
        return s
    return value


def eval_filter(item: Dict[str, Any], field: str, operator: str, value: Any) -> bool:
    """Apply a single ``field operator value`` filter against ``item``.

    The ``item`` is the raw ``properties`` dict (plus ``object_key`` and
    ``status`` flattened on top so a Filter on ``status`` works without
    configuration gymnastics).
    """
    haystack_raw = (item or {}).get(field)
    needle = coerce_compare(value)
    haystack = coerce_compare(haystack_raw)

    try:
        if operator == "==":
            return haystack == needle
        if operator == "!=":
            return haystack != needle
        if operator == ">":
            return haystack > needle
        if operator == ">=":
            return haystack >= needle
        if operator == "<":
            return haystack < needle
        if operator == "<=":
            return haystack <= needle
        if operator == "contains":
            if haystack is None or needle is None:
                return False
            return str(needle) in str(haystack)
        if operator == "in":
            if needle is None:
                return False
            if isinstance(needle, str):
                return needle in str(haystack or "")
            return haystack == needle
    except TypeError:
        # Comparing different types is a non-match.
        return False
    return False


def first_upstream_id(
    node_id: str,
    raw_edges: List[Dict[str, Any]],
    raw_nodes: List[Dict[str, Any]],
) -> Optional[str]:
    """Return the first upstream node id (the only one we connect right now)."""
    node_ids = {n.get("id") for n in raw_nodes}
    for e in raw_edges:
        target = e.get("target")
        source = e.get("source")
        if target == node_id and source in node_ids:
            return source
    return None


__all__ = [
    "topological_order",
    "coerce_compare",
    "eval_filter",
    "first_upstream_id",
]
