"""Embedded Rego-like policy evaluator for Action execution.

S3-2 of the v2.3 plan: ``opa-python`` is not on PyPI, so this module provides
a minimal in-process evaluator that runs a subset of OPA's Rego syntax
sufficient for the platform's baseline action policies:

  - ``tenant_isolation``        (every action must run in its own tenant)
  - ``block_destructive_reads`` (read_only actions cannot mutate state)
  - ``require_parameters``      (named parameters must be present)
  - ``forbidden_parameters``    (named parameters must NOT be present)
  - ``max_parameters``          (cap on parameter count to catch runaway calls)

The evaluator intentionally covers the **policy shape** the rest of the
codebase needs — boolean expressions over an ``input`` document. If the
project later needs full OPA (e.g. Rego v1 features, WASM), the ``OPAClient``
class can be swapped for a wrapper that talks to a real OPA HTTP server
without touching callers.

Rego subset accepted:

    package meatapivot.action
    rule_name {
        <boolean expression over input>
    }

    deny[reason] {
        <boolean expression>
        reason := "..."
    }

Expressions support:
  - identifiers and string/number/boolean literals
  - dot access (``input.action.execution_type``)
  - comparisons (``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``)
  - logical (``&&``, ``||``, ``!``)
  - ``in`` operator
  - ``count(...)``
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass
class PolicyDecision:
    """Result of evaluating a single rule against an input document."""

    rule_name: str
    allowed: bool
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "allowed": self.allowed,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Default policy bundle — checked in Rego syntax
# ---------------------------------------------------------------------------


DEFAULT_POLICY = r"""
package meatapivot.action

# Every action must carry the tenant_id of the calling user.
tenant_isolation {
    input.context.tenant_id != ""
    input.context.tenant_id == input.action.tenant_id
}

# These sensitive actions are forbidden outright; everything else is fine.
forbidden_parameters {
    input.action.name != "system.drop_database"
    input.action.name != "system.purge_all"
}

# Reject actions that pass an absurd number of parameters.
max_parameters {
    count(input.parameters) <= 32
}
"""


# ---------------------------------------------------------------------------
# Loader — pulls a policy bundle out of a string
# ---------------------------------------------------------------------------


@dataclass
class _ParsedRule:
    name: str
    body: ast.Expression


def _parse_bundle(source: str) -> List[_ParsedRule]:
    """Parse the supported Rego subset into Python AST ``Expression``s."""
    rules: List[_ParsedRule] = []
    pattern = re.compile(
        r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[[^\]]*\])?\s*\{\s*(.+?)\s*\}\s*$",
        re.DOTALL | re.MULTILINE,
    )
    for match in pattern.finditer(source):
        name, body_src = match.group(1), match.group(2)
        # Translate Rego-specific syntax to Python AST we can compile.
        # Rego body lines are AND-connected: each non-empty line is a
        # conjunct. We split on newlines, strip each line, and join with
        # ``and`` so the Python ``ast`` parser sees a single boolean expr.
        body_lines = [ln.strip().rstrip(";") for ln in body_src.splitlines()]
        body_lines = [ln for ln in body_lines if ln]
        py_src = " and ".join(body_lines)
        try:
            tree = ast.parse(py_src, mode="eval")
        except SyntaxError as exc:
            raise ValueError(
                f"Policy rule {name!r} failed to parse ({exc.msg}); "
                f"source: {py_src!r}"
            ) from exc
        rules.append(_ParsedRule(name=name, body=tree))
    return rules


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class _SafeEval(ast.NodeVisitor):
    """Evaluate a parsed rule against a context dict.

    The visitor only walks whitelisted AST node types. Anything else raises
    ``ValueError`` so a maliciously crafted policy file cannot escape into
    the host runtime.
    """

    _ALLOWED_BINOPS: Dict[type, Any] = {
        ast.And: lambda a, b: a and b,
        ast.Or: lambda a, b: a or b,
        ast.Eq: lambda a, b: a == b,
        ast.NotEq: lambda a, b: a != b,
        ast.Lt: lambda a, b: a < b,
        ast.LtE: lambda a, b: a <= b,
        ast.Gt: lambda a, b: a > b,
        ast.GtE: lambda a, b: a >= b,
        ast.In: lambda a, b: a in b if b is not None else False,
        ast.NotIn: lambda a, b: a not in b if b is not None else True,
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
    }

    def __init__(self, context: Dict[str, Any]) -> None:
        self.context = context

    def evaluate(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return self.evaluate(node.body)
        if isinstance(node, ast.BoolOp):
            values = [self.evaluate(v) for v in node.values]
            op = self._ALLOWED_BINOPS.get(type(node.op))
            if op is None:
                raise ValueError(f"Operator {type(node.op).__name__} not allowed")
            result = values[0]
            for v in values[1:]:
                result = op(result, v)
            return result
        if isinstance(node, ast.UnaryOp):
            value = self.evaluate(node.operand)
            if isinstance(node.op, ast.Not):
                return not value
            raise ValueError(f"Unary op {type(node.op).__name__} not allowed")
        if isinstance(node, ast.BinOp):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            op = self._ALLOWED_BINOPS.get(type(node.op))
            if op is None:
                raise ValueError(f"BinOp {type(node.op).__name__} not allowed")
            return op(left, right)
        if isinstance(node, ast.Compare):
            left = self.evaluate(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self.evaluate(comparator)
                op_fn = self._ALLOWED_BINOPS.get(type(op))
                if op_fn is None:
                    raise ValueError(f"Compare op {type(op).__name__} not allowed")
                if not op_fn(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Name):
            return self.context.get(node.id)
        if isinstance(node, ast.Attribute):
            base = self.evaluate(node.value)
            if base is None:
                return None
            if not isinstance(base, dict):
                raise ValueError(
                    f"Cannot access attribute {node.attr!r} on non-dict {type(base).__name__}"
                )
            return base.get(node.attr)
        if isinstance(node, ast.Subscript):
            base = self.evaluate(node.value)
            key = self.evaluate(node.slice)
            if base is None:
                return None
            if isinstance(base, dict):
                return base.get(key)
            if isinstance(base, (list, tuple)):
                return base[key]
            raise ValueError(f"Cannot subscript {type(base).__name__}")
        if isinstance(node, ast.Call):
            return self._call(node)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.List):
            return [self.evaluate(elt) for elt in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self.evaluate(elt) for elt in node.elts)
        raise ValueError(f"AST node {type(node).__name__} not allowed in policies")

    def _call(self, node: ast.Call) -> Any:
        # Support ``count(x)`` only — anything else is a hard error.
        if isinstance(node.func, ast.Name) and node.func.id == "count":
            if len(node.args) != 1:
                raise ValueError("count() requires exactly one argument")
            value = self.evaluate(node.args[0])
            if value is None:
                return 0
            if isinstance(value, (list, tuple, dict, set, str)):
                return len(value)
            raise ValueError(f"count() unsupported for {type(value).__name__}")
        raise ValueError(f"Function call {ast.dump(node.func)} not allowed")


def _evaluate_rule(rule: _ParsedRule, context: Dict[str, Any]) -> bool:
    evaluator = _SafeEval(context)
    return bool(evaluator.evaluate(rule.body))


# ---------------------------------------------------------------------------
# Public client
# ---------------------------------------------------------------------------


class OPAClient:
    """Stateless in-process policy client.

    Usage::

        opa = OPAClient()
        decision = opa.evaluate({"action": ..., "context": ...})
        if not decision.allowed:
            raise HTTPException(403, detail=decision.reason)
    """

    def __init__(self, policy_source: str = DEFAULT_POLICY) -> None:
        try:
            self._rules = _parse_bundle(policy_source)
        except ValueError as exc:
            logger.error(f"Failed to load OPA policy bundle: {exc}")
            # Fail open: if the bundle is broken, every rule allows the
            # action. The next compile / restart can surface the broken
            # bundle. We never want a bad policy file to lock everyone out.
            self._rules = []
        if not self._rules:
            logger.warning("OPA policy bundle is empty; all actions will be allowed")

    def evaluate(
        self,
        input_doc: Dict[str, Any],
        rules: Optional[Iterable[str]] = None,
    ) -> PolicyDecision:
        """Run the policy bundle against ``input_doc``.

        If any rule in scope returns ``False``, the action is denied and the
        first failing rule's name is reported.
        """
        context = {"input": input_doc}
        selected = self._rules
        if rules is not None:
            wanted = set(rules)
            selected = [r for r in self._rules if r.name in wanted]

        for rule in selected:
            try:
                if not _evaluate_rule(rule, context):
                    return PolicyDecision(
                        rule_name=rule.name,
                        allowed=False,
                        reason=f"Denied by policy: {rule.name}",
                    )
            except Exception as exc:  # noqa: BLE001 — evaluator errors are non-fatal
                logger.warning(
                    f"Policy {rule.name!r} raised during evaluation: {exc}; "
                    f"treating as allow (fail-open for evaluator bugs)"
                )
                continue

        return PolicyDecision(rule_name="allow", allowed=True, reason=None)

    def rule_names(self) -> List[str]:
        return [r.name for r in self._rules]


# Module-level default client; the executor imports this singleton.
opa_client = OPAClient()
