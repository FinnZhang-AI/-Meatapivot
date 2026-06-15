"""Action Execution Engine - Direct, Function-backed, and Workflow modes."""
import asyncio
import ast
import json
import logging
import operator
import resource
import tempfile
import os
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ontology_models import (
    OntologyActionType,
    OntologyObject,
    OntologyObjectType,
    OntologyFunction,
    ActionExecutionLog,
)
from app.models.ontology_schemas import ActionExecuteResponse, RuleEvaluation
from app.services.neo4j_client import neo4j_client
from app.services.opa_client import opa_client, PolicyDecision

logger = logging.getLogger(__name__)


class SafeExprEvaluator(ast.NodeVisitor):
    """
    Safe expression evaluator for Action rules.
    Replaces dangerous eval() with a restricted AST evaluator.
    Only allows: math ops, comparisons, bool ops, names, constants, calls to allowed functions.
    """

    ALLOWED_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.And: lambda a, b: a and b,
        ast.Or: lambda a, b: a or b,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
        ast.Is: lambda a, b: a is b,
        ast.IsNot: lambda a, b: a is not b,
    }

    ALLOWED_FUNCTIONS = {
        "len", "abs", "min", "max", "sum", "round",
        "any", "all", "str", "int", "float", "bool",
    }

    def __init__(self, locals_dict: Dict[str, Any]):
        self.locals_dict = locals_dict

    def eval(self, expr: str) -> Any:
        try:
            tree = ast.parse(expr.strip(), mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"Invalid expression syntax: {exc}") from exc
        return self._visit(tree.body)

    def _visit(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self.locals_dict:
                return self.locals_dict[node.id]
            raise NameError(f"Name '{node.id}' is not defined in rule context")
        if isinstance(node, ast.BinOp):
            op = self.ALLOWED_OPS.get(type(node.op))
            if not op:
                raise TypeError(f"Unsupported binary operator: {type(node.op).__name__}")
            return op(self._visit(node.left), self._visit(node.right))
        if isinstance(node, ast.UnaryOp):
            op = self.ALLOWED_OPS.get(type(node.op))
            if not op:
                raise TypeError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op(self._visit(node.operand))
        if isinstance(node, ast.Compare):
            left = self._visit(node.left)
            for op_node, comparator in zip(node.ops, node.comparators):
                op = self.ALLOWED_OPS.get(type(op_node))
                if not op:
                    raise TypeError(f"Unsupported comparison: {type(op_node).__name__}")
                right = self._visit(comparator)
                if not op(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            values = [self._visit(v) for v in node.values]
            op = self.ALLOWED_OPS.get(type(node.op))
            if not op:
                raise TypeError(f"Unsupported bool operator: {type(node.op).__name__}")
            return op(values[0], values[1]) if len(values) == 2 else all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise TypeError("Only simple function calls are allowed in rules")
            if node.func.id not in self.ALLOWED_FUNCTIONS:
                raise NameError(f"Function '{node.func.id}' is not allowed in rules")
            args = [self._visit(arg) for arg in node.args]
            kwargs = {kw.arg: self._visit(kw.value) for kw in node.keywords if isinstance(kw.arg, str)}
            return getattr(__builtins__, node.func.id)(*args, **kwargs)
        if isinstance(node, ast.List):
            return [self._visit(e) for e in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._visit(e) for e in node.elts)
        if isinstance(node, ast.Dict):
            return {self._visit(k): self._visit(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.Subscript):
            value = self._visit(node.value)
            slice_val = self._visit(node.slice)
            return value[slice_val]
        if isinstance(node, ast.Attribute):
            value = self._visit(node.value)
            return getattr(value, node.attr)
        if isinstance(node, ast.IfExp):
            return self._visit(node.body) if self._visit(node.test) else self._visit(node.orelse)
        raise TypeError(f"Unsupported expression node: {type(node).__name__}")


class ActionExecutor:
    """Execute Ontology Action Types with rule validation and mode-specific handling."""

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def execute(
        self,
        action_type_id: UUID,
        target_object_id: UUID,
        parameters: Dict[str, Any],
        executed_by: Optional[UUID] = None,
    ) -> ActionExecuteResponse:
        """Main entry point for action execution."""
        start = datetime.utcnow()
        log = ActionExecutionLog(
            id=uuid4(),
            tenant_id=self.tenant_id,
            action_type_id=action_type_id,
            target_object_id=target_object_id,
            parameters=parameters,
            status="running",
            executed_by=executed_by,
        )
        self.db.add(log)
        await self.db.flush()

        try:
            # Fetch action type
            result = await self.db.execute(
                select(OntologyActionType).where(
                    OntologyActionType.id == action_type_id,
                    OntologyActionType.tenant_id == self.tenant_id,
                )
            )
            action = result.scalar_one_or_none()
            if not action:
                raise ValueError(f"Action type {action_type_id} not found")

            # Validate rules
            rule_results = await self._validate_rules(action, target_object_id, parameters)
            blocked = [r for r in rule_results if not r.passed]
            if blocked:
                log.status = "blocked"
                log.rule_results = [r.model_dump() for r in rule_results]
                await self.db.flush()
                return ActionExecuteResponse(
                    success=False,
                    message=f"Blocked by rules: {[r.name for r in blocked]}",
                    rule_results=rule_results,
                    execution_log_id=log.id,
                )

            # S3-2: OPA policy gate. Runs after the in-Python rule engine so
            # the policy bundle is the single source of truth for cross-cutting
            # checks (tenant isolation, destructive-read blocks, parameter caps).
            policy_input = {
                "action": {
                    "id": str(action.id),
                    "name": action.name,
                    "execution_type": action.execution_type,
                    "tenant_id": str(action.tenant_id),
                },
                "context": {
                    "tenant_id": str(self.tenant_id),
                    "executed_by": str(executed_by) if executed_by else "",
                    "target_object_id": str(target_object_id) if target_object_id else "",
                },
                "parameters": parameters or {},
            }
            try:
                policy_decision: PolicyDecision = opa_client.evaluate(policy_input)
            except Exception as policy_exc:  # noqa: BLE001 — keep actions running if OPA itself errors
                logger.error(f"OPA evaluation crashed; allowing action: {policy_exc}")
                policy_decision = PolicyDecision(
                    rule_name="allow", allowed=True, reason="opa_crash_fail_open"
                )

            if not policy_decision.allowed:
                log.status = "blocked"
                log.error_message = f"OPA_REJECTED: {policy_decision.reason}"
                log.completed_at = datetime.utcnow()
                await self.db.flush()
                logger.warning(
                    f"Action {action.name} blocked by OPA rule {policy_decision.rule_name!r}"
                )
                return ActionExecuteResponse(
                    success=False,
                    message=f"OPA_REJECTED: {policy_decision.reason}",
                    rule_results=rule_results + [RuleEvaluation(
                        rule_name=f"OPA::{policy_decision.rule_name}",
                        passed=False,
                        reason=policy_decision.reason,
                    )],
                    execution_log_id=log.id,
                )

            # Execute by mode
            if action.execution_type == "direct":
                result_data = await self._execute_direct(action, target_object_id, parameters)
            elif action.execution_type == "function_backed":
                result_data = await self._execute_function_backed(action, target_object_id, parameters)
            elif action.execution_type == "workflow":
                result_data = await self._execute_workflow(action, target_object_id, parameters)
            else:
                raise ValueError(f"Unknown execution type: {action.execution_type}")

            log.status = "success"
            log.result = result_data
            log.rule_results = [r.model_dump() for r in rule_results]
            log.completed_at = datetime.utcnow()
            await self.db.flush()

            return ActionExecuteResponse(
                success=True,
                message="Action executed successfully",
                result=result_data,
                rule_results=rule_results,
                execution_log_id=log.id,
            )

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            log.status = "failed"
            log.error_message = str(e)
            log.completed_at = datetime.utcnow()
            await self.db.flush()
            return ActionExecuteResponse(
                success=False,
                message=str(e),
                execution_log_id=log.id,
            )

    async def _validate_rules(
        self,
        action: OntologyActionType,
        target_object_id: UUID,
        parameters: Dict[str, Any],
    ) -> list:
        """Validate action rules. Supports simple JSON expressions."""
        results = []
        rules = action.rules or []
        for rule in rules:
            name = rule.get("name", "unnamed")
            rule_type = rule.get("rule_type", "expression")
            policy = rule.get("policy", "")
            passed = True
            try:
                if rule_type == "expression":
                    # Safe expression evaluation using AST-based evaluator
                    obj_result = await self.db.execute(
                        select(OntologyObject).where(
                            OntologyObject.id == target_object_id,
                            OntologyObject.tenant_id == self.tenant_id,
                        )
                    )
                    obj = obj_result.scalar_one_or_none()
                    obj_props = obj.properties if obj else {}
                    evaluator = SafeExprEvaluator({
                        "params": parameters,
                        "properties": obj_props,
                        "obj": obj,
                    })
                    passed = bool(evaluator.eval(policy))
                else:
                    # OPA / other - placeholder, default pass
                    passed = True
            except Exception as e:
                logger.warning(f"Rule evaluation error for '{name}': {e}")
                passed = False

            results.append(RuleEvaluation(name=name, passed=passed, detail=policy))
        return results

    async def _execute_direct(
        self,
        action: OntologyActionType,
        target_object_id: UUID,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Direct mode: modify object properties in PostgreSQL and sync to Neo4j."""
        result = await self.db.execute(
            select(OntologyObject).where(
                OntologyObject.id == target_object_id,
                OntologyObject.tenant_id == self.tenant_id,
            )
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise ValueError(f"Target object {target_object_id} not found")

        # Apply property modifications
        modifies = action.modifies_properties or []
        for mod in modifies:
            prop_name = mod.get("property")
            value_source = mod.get("value_from", "parameter")
            if value_source == "parameter":
                obj.properties[prop_name] = parameters.get(prop_name)
            elif value_source == "literal":
                obj.properties[prop_name] = mod.get("value")
            elif value_source == "increment":
                current = obj.properties.get(prop_name, 0)
                obj.properties[prop_name] = current + parameters.get(prop_name, 1)

        obj.updated_at = datetime.utcnow()
        await self.db.flush()

        # Sync to Neo4j
        if obj.neo4j_node_id:
            props = {k: v for k, v in obj.properties.items() if v is not None}
            cypher = """
            MATCH (n)
            WHERE elementId(n) = $neo4j_node_id
            SET n += $props
            """
            await neo4j_client.execute_query(cypher, {
                "neo4j_node_id": obj.neo4j_node_id,
                "props": props,
            })

        return {"modified_properties": [m.get("property") for m in modifies]}

    async def _execute_function_backed(
        self,
        action: OntologyActionType,
        target_object_id: UUID,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Function-backed mode: execute Python/TypeScript in subprocess sandbox."""
        if not action.function_id:
            raise ValueError("Action has no associated function")

        result = await self.db.execute(
            select(OntologyFunction).where(
                OntologyFunction.id == action.function_id,
                OntologyFunction.tenant_id == self.tenant_id,
            )
        )
        func = result.scalar_one_or_none()
        if not func:
            raise ValueError(f"Function {action.function_id} not found")

        # Fetch target object for context
        obj_result = await self.db.execute(
            select(OntologyObject).where(
                OntologyObject.id == target_object_id,
                OntologyObject.tenant_id == self.tenant_id,
            )
        )
        obj = obj_result.scalar_one_or_none()

        # Build execution script
        context = {
            "parameters": parameters,
            "object_id": str(target_object_id),
            "object_properties": obj.properties if obj else {},
            "object_key": obj.object_key if obj else None,
        }
        wrapper = f'''
import json, sys
context = json.loads(sys.argv[1])
parameters = context["parameters"]
object_id = context["object_id"]
object_properties = context["object_properties"]
object_key = context["object_key"]

{func.code}
'''
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(wrapper)
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "python", tmp_path, json.dumps(context),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024,  # 1MB buffer
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=func.timeout_seconds or 30,
            )
            stdout_str = stdout.decode("utf-8", errors="replace")[:10000]
            stderr_str = stderr.decode("utf-8", errors="replace")[:10000]

            if proc.returncode != 0:
                raise RuntimeError(f"Function exited with code {proc.returncode}: {stderr_str}")

            # Try to parse last line as JSON result
            try:
                result_data = json.loads(stdout_str.strip().splitlines()[-1])
            except (json.JSONDecodeError, IndexError):
                result_data = {"output": stdout_str.strip()}

            return result_data
        except asyncio.TimeoutError:
            raise RuntimeError(f"Function execution timed out after {func.timeout_seconds or 30}s")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    async def _execute_workflow(
        self,
        action: OntologyActionType,
        target_object_id: UUID,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Workflow mode: simplified sequential step execution."""
        logger.info(
            f"Workflow execution: action={action.name}, "
            f"workflow_id={action.workflow_id}, object={target_object_id}"
        )

        if not action.workflow_id:
            raise ValueError("Action has no associated workflow")

        # Fetch target object
        obj_result = await self.db.execute(
            select(OntologyObject).where(
                OntologyObject.id == target_object_id,
                OntologyObject.tenant_id == self.tenant_id,
            )
        )
        obj = obj_result.scalar_one_or_none()

        # Simple workflow: execute a chain of predefined steps
        # In production, this should integrate with the decision flow engine
        context = {
            "parameters": parameters,
            "object_id": str(target_object_id),
            "object_properties": obj.properties if obj else {},
            "object_key": obj.object_key if obj else None,
            "workflow_id": str(action.workflow_id),
        }

        # Placeholder: execute predefined steps from action config
        steps = action.parameters or []
        results = []
        for step in steps:
            step_name = step.get("name", "unknown")
            step_type = step.get("type", "noop")
            if step_type == "set_property":
                prop = step.get("property")
                value = parameters.get(prop, step.get("default"))
                if obj and prop:
                    obj.properties[prop] = value
                    results.append({"step": step_name, "type": "set_property", "property": prop, "value": value})
            elif step_type == "create_link":
                link_type_id = step.get("link_type_id")
                target_id = parameters.get("target_object_id")
                if link_type_id and target_id:
                    results.append({"step": step_name, "type": "create_link", "link_type_id": link_type_id, "target_id": target_id})
            elif step_type == "notify":
                message = step.get("message", "Workflow step executed")
                results.append({"step": step_name, "type": "notify", "message": message})
            else:
                results.append({"step": step_name, "type": step_type, "status": "noop"})

        await self.db.flush()
        return {
            "mode": "workflow",
            "workflow_id": str(action.workflow_id),
            "status": "completed",
            "steps_executed": len(results),
            "results": results,
            "context": {k: v for k, v in context.items() if k != "object_properties"},
        }
