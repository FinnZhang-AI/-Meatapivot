"""Agent Engine - Workflow-based agent orchestration for the AIP layer.

Design: Custom async workflow engine integrated with existing services.
- Supports workflow graphs with node types: llm, action, search, human, condition, end
- Supports sequential, branching (condition), and looping (edge back-links) workflows
- Uses LLMGateway for LLM calls
- Uses ActionExecutor for ontology actions
- Uses SemanticSearchService for knowledge retrieval
- Uses Redis for session state persistence
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.llm_gateway import llm_gateway
from app.services.redis_client import redis_client
from app.services.semantic_search import SemanticSearchService
from app.services.action_executor import ActionExecutor

logger = logging.getLogger(__name__)


class Tool:
    """A tool that an Agent can call."""

    def __init__(self, name: str, description: str, func: Callable):
        self.name = name
        self.description = description
        self.func = func

    async def execute(self, **kwargs) -> str:
        try:
            result = self.func(**kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            return str(result)
        except Exception as e:
            return f"Tool error: {e}"


class WorkflowNodeConfig:
    """Runtime wrapper for workflow node configuration."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def __getattr__(self, item: str) -> Any:
        return self._config.get(item)


class AgentDefinition:
    """Configuration for an agent."""

    def __init__(
        self,
        agent_id: UUID,
        name: str,
        system_prompt: str,
        tools: Optional[List[Tool]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_iterations: int = 10,
        workflow_mode: str = "sequential",
        human_in_the_loop: bool = False,
        human_prompt: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
        description: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.description = description or ""
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model = model or settings.DEFAULT_LLM_MODEL
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.workflow_mode = workflow_mode
        self.human_in_the_loop = human_in_the_loop
        self.human_prompt = human_prompt or (
            "The agent needs your confirmation before proceeding. "
            "Please review the proposed action and reply 'yes' to continue or provide feedback."
        )
        self.nodes = nodes or []
        self.edges = edges or []

    @property
    def has_workflow(self) -> bool:
        return len(self.nodes) > 0

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        for node in self.nodes:
            if node.get("id") == node_id:
                return node
        return None

    def get_start_node(self) -> Optional[Dict[str, Any]]:
        if not self.nodes:
            return None
        return self.nodes[0]

    def get_outgoing_edges(self, node_id: str) -> List[Dict[str, Any]]:
        return [e for e in self.edges if e.get("source") == node_id]

    def to_schema_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.agent_id),
            "name": self.name,
            "workflow_mode": self.workflow_mode,
            "model": self.model,
            "description": self.description,
            "tools": [{"name": t.name, "description": t.description} for t in self.tools],
            "nodes": self.nodes,
            "edges": self.edges,
            "human_in_the_loop": self.human_in_the_loop,
        }


class AgentSession:
    """Redis-backed session state."""

    PREFIX = "agent_session"
    TTL = 3600

    def __init__(self, session_id: UUID, agent_id: UUID, tenant_id: Optional[UUID]):
        self.session_id = session_id
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self._messages: List[Dict[str, str]] = []
        self._status = "pending"
        self._last_output = ""
        self._steps: List[Dict[str, Any]] = []
        self._prompt: Optional[str] = None
        self._current_node_id: Optional[str] = None
        self._variables: Dict[str, Any] = {}

    @property
    def key(self) -> str:
        return f"{self.PREFIX}:{self.tenant_id}:{self.session_id}"

    def _serialize(self) -> str:
        return json.dumps({
            "session_id": str(self.session_id),
            "agent_id": str(self.agent_id),
            "messages": json.dumps(self._messages),
            "status": self._status,
            "last_output": self._last_output,
            "steps": json.dumps(self._steps, default=str),
            "prompt": self._prompt,
            "current_node_id": self._current_node_id,
            "variables": json.dumps(self._variables, default=str),
        })

    async def save(self) -> None:
        try:
            if redis_client.client:
                await redis_client.client.setex(self.key, self.TTL, self._serialize())
        except Exception as e:
            logger.warning(f"Agent session save failed: {e}")

    async def load(self) -> bool:
        try:
            if redis_client.client:
                raw = await redis_client.client.get(self.key)
                if raw:
                    data = json.loads(raw)
                    self._messages = json.loads(data.get("messages", "[]"))
                    self._status = data.get("status", "pending")
                    self._last_output = data.get("last_output", "")
                    self._steps = json.loads(data.get("steps", "[]"))
                    self._prompt = data.get("prompt")
                    self._current_node_id = data.get("current_node_id")
                    self._variables = json.loads(data.get("variables", "{}"))
                    return True
        except Exception as e:
            logger.warning(f"Agent session load failed: {e}")
        return False

    def add_message(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})

    def get_messages(self) -> List[Dict[str, str]]:
        return list(self._messages)

    def set_status(self, status: str) -> None:
        self._status = status

    def get_status(self) -> str:
        return self._status

    def set_output(self, output: str) -> None:
        self._last_output = output

    def get_output(self) -> str:
        return self._last_output

    def add_step(self, step: Dict[str, Any]) -> None:
        self._steps.append(step)

    def get_steps(self) -> List[Dict[str, Any]]:
        return list(self._steps)

    def set_prompt(self, prompt: Optional[str]) -> None:
        self._prompt = prompt

    def get_prompt(self) -> Optional[str]:
        return self._prompt

    def set_current_node(self, node_id: Optional[str]) -> None:
        self._current_node_id = node_id

    def get_current_node(self) -> Optional[str]:
        return self._current_node_id

    def set_variable(self, key: str, value: Any) -> None:
        self._variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        return self._variables.get(key, default)

    def get_variables(self) -> Dict[str, Any]:
        return dict(self._variables)


class AgentEngine:
    """Core agent orchestration engine."""

    def __init__(self, db: AsyncSession, tenant_id: Optional[UUID], definition: AgentDefinition):
        self.db = db
        self.tenant_id = tenant_id
        self.definition = definition
        self._should_interrupt = False
        self._steps: List[Dict[str, Any]] = []

    def new_trace_id(self) -> UUID:
        return uuid4()

    def interrupt(self) -> None:
        self._should_interrupt = True

    def _make_tools(self) -> List[Tool]:
        """Build runtime tools bound to the current DB session and tenant."""
        tools: List[Tool] = []

        async def search_ontology(query: str, object_types: Optional[str] = None, top_k: int = 5) -> str:
            try:
                service = SemanticSearchService(self.db, self.tenant_id)
                types_list = object_types.split(",") if object_types else None
                result = await service.search(query=query, object_types=types_list, top_k=top_k)
                items = [
                    f"[{r.object_type}] {r.object_key}: {json.dumps(r.properties_preview, ensure_ascii=False)}"
                    for r in result.results
                ]
                return "\n".join(items) if items else "No relevant ontology objects found."
            except Exception as e:
                return f"Search error: {e}"

        async def execute_action(action_type_id: str, target_object_id: str, parameters: Optional[str] = None) -> str:
            try:
                executor = ActionExecutor(self.db, self.tenant_id or uuid4())
                params = json.loads(parameters) if parameters else {}
                result = await executor.execute(
                    action_type_id=UUID(action_type_id),
                    target_object_id=UUID(target_object_id),
                    parameters=params,
                )
                return json.dumps(result.model_dump(), default=str, ensure_ascii=False)
            except Exception as e:
                return f"Action error: {e}"

        tools.append(Tool(
            name="search_ontology",
            description="Search the ontology for relevant objects. Args: query (str), object_types (optional comma-separated str), top_k (int).",
            func=search_ontology,
        ))
        tools.append(Tool(
            name="execute_action",
            description="Execute an ontology action on a target object. Args: action_type_id (str UUID), target_object_id (str UUID), parameters (JSON str).",
            func=execute_action,
        ))
        tools.extend(self.definition.tools)
        return tools

    async def run(
        self,
        user_input: str,
        session: Optional[AgentSession] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        trace_id = uuid4()
        session = session or AgentSession(
            session_id=trace_id,
            agent_id=self.definition.agent_id,
            tenant_id=self.tenant_id,
        )
        existing = await session.load()
        if not existing:
            session.add_message("system", self.definition.system_prompt)

        session.add_message("user", user_input)
        if context:
            ctx = json.dumps(context, default=str, ensure_ascii=False)
            session._messages[-1]["content"] += f"\n[Context: {ctx}]"

        session.set_status("running")
        session.set_variable("user_input", user_input)
        session.set_variable("context", context or {})
        await session.save()

        try:
            if self.definition.has_workflow:
                result = await self._run_workflow(session, trace_id)
            else:
                result = await self._run_loop(session, trace_id)
            return result
        except Exception as e:
            logger.error(f"Agent run failed: {e}")
            session.set_status("failed")
            await session.save()
            return {
                "output": f"Execution failed: {e}",
                "steps": self._steps,
                "status": "failed",
                "trace_id": str(trace_id),
            }

    async def run_stream(
        self,
        user_input: str,
        session: Optional[AgentSession] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream agent execution events for SSE."""
        trace_id = session.session_id if session else uuid4()
        session = session or AgentSession(
            session_id=trace_id,
            agent_id=self.definition.agent_id,
            tenant_id=self.tenant_id,
        )
        existing = await session.load()
        if not existing:
            session.add_message("system", self.definition.system_prompt)

        session.add_message("user", user_input)
        if context:
            ctx = json.dumps(context, default=str, ensure_ascii=False)
            session._messages[-1]["content"] += f"\n[Context: {ctx}]"

        session.set_status("running")
        session.set_variable("user_input", user_input)
        session.set_variable("context", context or {})
        await session.save()

        yield {"event": "status", "data": {"status": "running", "trace_id": str(trace_id)}}

        try:
            if self.definition.has_workflow:
                async for event in self._run_workflow_stream(session, trace_id):
                    yield event
            else:
                async for event in self._run_loop_stream(session, trace_id):
                    yield event
        except Exception as e:
            logger.error(f"Agent stream failed: {e}")
            session.set_status("failed")
            await session.save()
            yield {"event": "failed", "data": {"error": str(e), "trace_id": str(trace_id)}}

    # -----------------------------------------------------------------------
    # Workflow graph executor
    # -----------------------------------------------------------------------

    async def _run_workflow(self, session: AgentSession, trace_id: UUID) -> Dict[str, Any]:
        current_node = self.definition.get_start_node()
        if not current_node:
            return {"output": "No workflow nodes defined.", "steps": [], "status": "failed", "trace_id": str(trace_id)}

        if session.get_current_node():
            # Resume from saved node (e.g., after human input)
            current_node = self.definition.get_node(session.get_current_node()) or current_node

        max_steps = 50
        for _ in range(max_steps):
            if self._should_interrupt:
                session.set_status("interrupted")
                await session.save()
                return {"output": session.get_output() or "Interrupted by user.", "steps": self._steps, "status": "interrupted", "trace_id": str(trace_id)}

            node_id = current_node.get("id")
            node_type = current_node.get("type")
            config = WorkflowNodeConfig(current_node.get("config", {}))
            session.set_current_node(node_id)

            if node_type == "end":
                output = config.get("output", session.get_output()) or "Workflow completed."
                session.set_output(output)
                session.set_status("completed")
                await session.save()
                return {"output": output, "steps": self._steps, "status": "completed", "trace_id": str(trace_id)}

            if node_type == "llm":
                current_node = await self._execute_llm_node(session, trace_id, current_node, config)
            elif node_type == "search":
                current_node = await self._execute_search_node(session, current_node, config)
            elif node_type == "action":
                current_node = await self._execute_action_node(session, current_node, config)
            elif node_type == "human":
                return await self._execute_human_node(session, trace_id, current_node, config)
            elif node_type == "condition":
                current_node = await self._execute_condition_node(session, current_node, config)
            else:
                raise ValueError(f"Unknown node type: {node_type}")

            if current_node is None:
                session.set_status("completed")
                await session.save()
                return {"output": session.get_output() or "Workflow ended.", "steps": self._steps, "status": "completed", "trace_id": str(trace_id)}

        session.set_status("completed")
        await session.save()
        return {"output": session.get_output() or "Max workflow steps reached.", "steps": self._steps, "status": "completed", "trace_id": str(trace_id)}

    async def _run_workflow_stream(
        self, session: AgentSession, trace_id: UUID
    ) -> AsyncGenerator[Dict[str, Any], None]:
        current_node = self.definition.get_start_node()
        if not current_node:
            yield {"event": "failed", "data": {"error": "No workflow nodes defined.", "trace_id": str(trace_id)}}
            return

        if session.get_current_node():
            current_node = self.definition.get_node(session.get_current_node()) or current_node

        max_steps = 50
        for _ in range(max_steps):
            if self._should_interrupt:
                session.set_status("interrupted")
                await session.save()
                yield {"event": "interrupted", "data": {"output": session.get_output() or "Interrupted by user.", "trace_id": str(trace_id)}}
                return

            node_id = current_node.get("id")
            node_type = current_node.get("type")
            config = WorkflowNodeConfig(current_node.get("config", {}))
            session.set_current_node(node_id)

            if node_type == "end":
                output = config.get("output", session.get_output()) or "Workflow completed."
                session.set_output(output)
                session.set_status("completed")
                await session.save()
                yield {"event": "completed", "data": {"output": output, "trace_id": str(trace_id)}}
                return

            if node_type == "llm":
                current_node = await self._execute_llm_node(session, trace_id, current_node, config)
                if self._steps:
                    yield {"event": "step", "data": self._steps[-1]}
            elif node_type == "search":
                current_node = await self._execute_search_node(session, current_node, config)
                if self._steps:
                    yield {"event": "step", "data": self._steps[-1]}
            elif node_type == "action":
                current_node = await self._execute_action_node(session, current_node, config)
                if self._steps:
                    yield {"event": "step", "data": self._steps[-1]}
            elif node_type == "human":
                result = await self._execute_human_node(session, trace_id, current_node, config)
                yield {"event": "human_input_required", "data": {"output": result["output"], "trace_id": str(trace_id), "prompt": result.get("prompt")}}
                return
            elif node_type == "condition":
                current_node = await self._execute_condition_node(session, current_node, config)
            else:
                yield {"event": "failed", "data": {"error": f"Unknown node type: {node_type}", "trace_id": str(trace_id)}}
                return

            if current_node is None:
                session.set_status("completed")
                await session.save()
                yield {"event": "completed", "data": {"output": session.get_output() or "Workflow ended.", "trace_id": str(trace_id)}}
                return

        session.set_status("completed")
        await session.save()
        yield {"event": "completed", "data": {"output": session.get_output() or "Max workflow steps reached.", "trace_id": str(trace_id)}}

    async def _execute_llm_node(
        self,
        session: AgentSession,
        trace_id: UUID,
        node: Dict[str, Any],
        config: WorkflowNodeConfig,
    ) -> Optional[Dict[str, Any]]:
        system_prompt = config.get("system_prompt") or self.definition.system_prompt
        messages = [{"role": "system", "content": system_prompt}] + session.get_messages()

        step_start = time.time()
        try:
            llm_response = await llm_gateway.chat(
                messages=messages,
                model=self.definition.model,
                temperature=self.definition.temperature,
                max_tokens=2048,
                db=self.db,
            )
            choice = llm_response.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            duration_ms = int((time.time() - step_start) * 1000)

            step: Dict[str, Any] = {"type": "llm", "thought": content, "duration_ms": duration_ms}
            session.add_message("assistant", content)

            if tool_calls:
                step["tool_calls"] = []
                for tc in tool_calls:
                    func = tc.get("function", {})
                    tname = func.get("name", "")
                    targs = json.loads(func.get("arguments", "{}"))
                    tresult = await self._execute_tool(tname, **targs)
                    step["tool_calls"].append({"tool": tname, "args": targs, "result": tresult})
                    session.add_message("tool", f"[{tname}]: {tresult}")

            self._steps.append(step)
            session.add_step(step)
            session.set_output(content)

            # If HITL enabled and tool calls made, pause
            if self.definition.human_in_the_loop and tool_calls:
                session.set_status("awaiting_input")
                session.set_prompt(self.definition.human_prompt)
                await session.save()
                return None
        except Exception as e:
            step = {"type": "llm_error", "error": str(e), "duration_ms": int((time.time() - step_start) * 1000)}
            self._steps.append(step)
            session.add_step(step)
            session.set_status("failed")
            await session.save()
            raise

        return self._next_node(node.get("id"))

    async def _execute_search_node(
        self,
        session: AgentSession,
        node: Dict[str, Any],
        config: WorkflowNodeConfig,
    ) -> Optional[Dict[str, Any]]:
        query_template = config.get("query_template") or "{user_input}"
        query = query_template.format(
            user_input=session.get_variable("user_input", ""),
            **session.get_variables(),
        )
        object_types = config.get("object_types")
        top_k = config.get("top_k", 5)

        step_start = time.time()
        try:
            service = SemanticSearchService(self.db, self.tenant_id)
            result = await service.search(query=query, object_types=object_types, top_k=top_k)
            items = [
                f"[{r.object_type}] {r.object_key}: {json.dumps(r.properties_preview, ensure_ascii=False)}"
                for r in result.results
            ]
            output = "\n".join(items) if items else "No relevant ontology objects found."
            duration_ms = int((time.time() - step_start) * 1000)
            step = {"type": "search", "thought": query, "content": output, "duration_ms": duration_ms}
            self._steps.append(step)
            session.add_step(step)
            session.set_output(output)
            session.set_variable("search_results", result.model_dump() if hasattr(result, "model_dump") else {})
        except Exception as e:
            step = {"type": "search_error", "error": str(e)}
            self._steps.append(step)
            session.add_step(step)

        return self._next_node(node.get("id"))

    async def _execute_action_node(
        self,
        session: AgentSession,
        node: Dict[str, Any],
        config: WorkflowNodeConfig,
    ) -> Optional[Dict[str, Any]]:
        action_type_id = config.get("action_type_id")
        target_object_id = config.get("target_object_id")
        parameters = config.get("parameters") or {}

        step_start = time.time()
        try:
            if action_type_id and target_object_id and self.tenant_id:
                executor = ActionExecutor(self.db, self.tenant_id)
                result = await executor.execute(
                    action_type_id=UUID(action_type_id),
                    target_object_id=UUID(target_object_id),
                    parameters=parameters,
                )
                output = json.dumps(result.model_dump(), default=str, ensure_ascii=False)
            else:
                output = "Action node missing action_type_id or target_object_id"
            duration_ms = int((time.time() - step_start) * 1000)
            step = {"type": "action", "content": output, "duration_ms": duration_ms}
            self._steps.append(step)
            session.add_step(step)
            session.set_output(output)
            session.set_variable("action_result", output)
        except Exception as e:
            step = {"type": "action_error", "error": str(e)}
            self._steps.append(step)
            session.add_step(step)

        return self._next_node(node.get("id"))

    async def _execute_human_node(
        self,
        session: AgentSession,
        trace_id: UUID,
        node: Dict[str, Any],
        config: WorkflowNodeConfig,
    ) -> Dict[str, Any]:
        prompt = config.get("prompt") or self.definition.human_prompt
        session.set_status("awaiting_input")
        session.set_prompt(prompt)
        await session.save()
        return {
            "output": session.get_output() or "Waiting for human input.",
            "steps": self._steps,
            "status": "awaiting_input",
            "trace_id": str(trace_id),
            "requires_input": True,
            "prompt": prompt,
        }

    async def _execute_condition_node(
        self,
        session: AgentSession,
        node: Dict[str, Any],
        config: WorkflowNodeConfig,
    ) -> Optional[Dict[str, Any]]:
        expression = config.get("condition_expression") or "true"
        variables = session.get_variables()
        try:
            # Safe evaluation with limited builtins
            passed = bool(eval(expression, {"__builtins__": {}}, variables))
        except Exception as e:
            logger.warning(f"Condition evaluation error: {e}")
            passed = False

        step = {"type": "condition", "content": str(passed), "thought": expression}
        self._steps.append(step)
        session.add_step(step)
        session.set_variable("condition_result", passed)

        outgoing = self.definition.get_outgoing_edges(node.get("id"))
        for edge in outgoing:
            edge_condition = edge.get("condition")
            if edge_condition is None:
                continue
            if (edge_condition.lower() == "true" and passed) or (edge_condition.lower() == "false" and not passed):
                return self.definition.get_node(edge.get("target"))

        # Fallback to first unconditional outgoing edge
        for edge in outgoing:
            if edge.get("condition") is None:
                return self.definition.get_node(edge.get("target"))

        return None

    def _next_node(self, current_node_id: str) -> Optional[Dict[str, Any]]:
        outgoing = self.definition.get_outgoing_edges(current_node_id)
        if not outgoing:
            return None
        return self.definition.get_node(outgoing[0].get("target"))

    # -----------------------------------------------------------------------
    # Legacy single LLM loop (fallback when no workflow graph is defined)
    # -----------------------------------------------------------------------

    async def _run_loop(
        self, session: AgentSession, trace_id: UUID, max_iters: Optional[int] = None
    ) -> Dict[str, Any]:
        max_iters = max_iters or self.definition.max_iterations
        final_output = ""

        for _ in range(max_iters):
            if self._should_interrupt:
                session.set_status("interrupted")
                await session.save()
                return {
                    "output": final_output or "Interrupted by user.",
                    "steps": self._steps,
                    "status": "interrupted",
                    "trace_id": str(trace_id),
                }

            messages = session.get_messages()
            step_start = time.time()
            try:
                llm_response = await llm_gateway.chat(
                    messages=messages,
                    model=self.definition.model,
                    temperature=self.definition.temperature,
                    max_tokens=2048,
                    db=self.db,
                )
            except Exception as e:
                step = {
                    "type": "llm_error",
                    "error": str(e),
                    "duration_ms": int((time.time() - step_start) * 1000),
                }
                self._steps.append(step)
                session.add_step(step)
                session.set_status("failed")
                await session.save()
                return {
                    "output": f"LLM call failed: {e}",
                    "steps": self._steps,
                    "status": "failed",
                    "trace_id": str(trace_id),
                }

            choice = llm_response.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            step_duration = int((time.time() - step_start) * 1000)

            if tool_calls:
                step = {"type": "llm", "thought": content, "tool_calls": [], "duration_ms": step_duration}
                session.add_message("assistant", content)
                for tc in tool_calls:
                    func = tc.get("function", {})
                    tname = func.get("name", "")
                    targs = json.loads(func.get("arguments", "{}"))
                    tresult = await self._execute_tool(tname, **targs)
                    step["tool_calls"].append({"tool": tname, "args": targs, "result": tresult})
                    session.add_message("tool", f"[{tname}]: {tresult}")
                self._steps.append(step)
                session.add_step(step)

                if self.definition.human_in_the_loop:
                    session.set_status("awaiting_input")
                    session.set_prompt(self.definition.human_prompt)
                    await session.save()
                    return {
                        "output": content,
                        "steps": self._steps,
                        "status": "awaiting_input",
                        "trace_id": str(trace_id),
                        "requires_input": True,
                        "prompt": self.definition.human_prompt,
                    }
                continue

            final_output = content
            session.set_output(final_output)
            step = {"type": "answer", "content": final_output, "duration_ms": step_duration}
            self._steps.append(step)
            session.add_step(step)
            session.add_message("assistant", final_output)
            break

        if not final_output:
            final_output = content or "Max iterations reached."
            session.set_output(final_output)

        session.set_status("completed")
        await session.save()
        return {
            "output": final_output,
            "steps": self._steps,
            "status": "completed",
            "trace_id": str(trace_id),
        }

    async def _run_loop_stream(
        self, session: AgentSession, trace_id: UUID, max_iters: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        max_iters = max_iters or self.definition.max_iterations
        final_output = ""

        for _ in range(max_iters):
            if self._should_interrupt:
                session.set_status("interrupted")
                await session.save()
                yield {"event": "interrupted", "data": {"output": final_output or "Interrupted by user.", "trace_id": str(trace_id)}}
                return

            messages = session.get_messages()
            step_start = time.time()
            try:
                llm_response = await llm_gateway.chat(
                    messages=messages,
                    model=self.definition.model,
                    temperature=self.definition.temperature,
                    max_tokens=2048,
                    db=self.db,
                )
            except Exception as e:
                step = {
                    "type": "llm_error",
                    "error": str(e),
                    "duration_ms": int((time.time() - step_start) * 1000),
                }
                self._steps.append(step)
                session.add_step(step)
                session.set_status("failed")
                await session.save()
                yield {"event": "failed", "data": {"error": str(e), "trace_id": str(trace_id)}}
                return

            choice = llm_response.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            step_duration = int((time.time() - step_start) * 1000)

            if tool_calls:
                step = {"type": "llm", "thought": content, "tool_calls": [], "duration_ms": step_duration}
                session.add_message("assistant", content)
                for tc in tool_calls:
                    func = tc.get("function", {})
                    tname = func.get("name", "")
                    targs = json.loads(func.get("arguments", "{}"))
                    tresult = await self._execute_tool(tname, **targs)
                    step["tool_calls"].append({"tool": tname, "args": targs, "result": tresult})
                    session.add_message("tool", f"[{tname}]: {tresult}")
                self._steps.append(step)
                session.add_step(step)
                yield {"event": "step", "data": step}

                if self.definition.human_in_the_loop:
                    session.set_status("awaiting_input")
                    session.set_prompt(self.definition.human_prompt)
                    await session.save()
                    yield {
                        "event": "human_input_required",
                        "data": {
                            "output": content,
                            "trace_id": str(trace_id),
                            "prompt": self.definition.human_prompt,
                        },
                    }
                    return
                continue

            final_output = content
            session.set_output(final_output)
            step = {"type": "answer", "content": final_output, "duration_ms": step_duration}
            self._steps.append(step)
            session.add_step(step)
            session.add_message("assistant", final_output)
            yield {"event": "step", "data": step}
            break

        if not final_output:
            final_output = content or "Max iterations reached."
            session.set_output(final_output)

        session.set_status("completed")
        await session.save()
        yield {"event": "completed", "data": {"output": final_output, "trace_id": str(trace_id)}}

    async def _execute_tool(self, tool_name: str, **kwargs) -> str:
        for tool in self._make_tools():
            if tool.name == tool_name:
                return await tool.execute(**kwargs)
        return f"Unknown tool: {tool_name}"


class AgentRegistry:
    """Registry of available agent definitions."""

    def __init__(self):
        self._agents: Dict[UUID, AgentDefinition] = {}

    def register(self, definition: AgentDefinition) -> None:
        self._agents[definition.agent_id] = definition

    def get(self, agent_id: UUID) -> Optional[AgentDefinition]:
        return self._agents.get(agent_id)

    def list_all(self) -> List[AgentDefinition]:
        return list(self._agents.values())

    def create_default_agents(self) -> None:
        self.register(AgentDefinition(
            agent_id=UUID("00000000-0000-0000-0000-000000000001"),
            name="General Assistant",
            description="A general purpose assistant with ontology search capability.",
            system_prompt=(
                "You are a helpful assistant for the Meatapivot enterprise knowledge platform. "
                "You help users understand their ontology, execute actions, and find information. "
                "Be concise, accurate, and always refer to specific ontology objects when relevant. "
                "Use the search_ontology tool when you need to look up ontology objects."
            ),
            max_iterations=5,
            human_in_the_loop=False,
        ))
        self.register(AgentDefinition(
            agent_id=UUID("00000000-0000-0000-0000-000000000002"),
            name="Ontology Explorer",
            description="An ontology exploration specialist using a sequential search-then-answer workflow.",
            system_prompt=(
                "You are an ontology exploration specialist. Help users navigate and understand "
                "their ontology objects. Guide them to use the search and object view features. "
                "Always be specific about which Object Types or Interfaces are relevant."
            ),
            max_iterations=5,
            workflow_mode="sequential",
            nodes=[
                {
                    "id": "search",
                    "type": "search",
                    "config": {"query_template": "{user_input}", "top_k": 5},
                },
                {
                    "id": "summarize",
                    "type": "llm",
                    "config": {
                        "system_prompt": (
                            "Summarize the search results for the user. Be concise and cite specific object keys."
                        ),
                    },
                },
                {"id": "end", "type": "end", "config": {}},
            ],
            edges=[
                {"source": "search", "target": "summarize"},
                {"source": "summarize", "target": "end"},
            ],
        ))
        self.register(AgentDefinition(
            agent_id=UUID("00000000-0000-0000-0000-000000000003"),
            name="Action Agent",
            description="An action execution specialist that pauses for human confirmation before acting.",
            system_prompt=(
                "You are an action execution specialist. Help users perform operations on "
                "ontology objects. Guide them to find the right actions and parameters. "
                "Always verify the action exists and the user understands consequences."
            ),
            max_iterations=8,
            human_in_the_loop=True,
            human_prompt="Please confirm before I execute the proposed ontology action. Reply 'yes' to proceed.",
        ))
        self.register(AgentDefinition(
            agent_id=UUID("00000000-0000-0000-0000-000000000004"),
            name="Condition Branching Demo",
            description="A demo agent that uses a condition node to branch based on user input length.",
            system_prompt="You are a workflow demo agent.",
            workflow_mode="branching",
            nodes=[
                {
                    "id": "check_length",
                    "type": "condition",
                    "config": {"condition_expression": "len(user_input) > 10"},
                },
                {"id": "short", "type": "llm", "config": {"system_prompt": "User input is short. Keep it brief."}},
                {"id": "long", "type": "llm", "config": {"system_prompt": "User input is long. Provide a detailed answer."}},
                {"id": "end", "type": "end", "config": {}},
            ],
            edges=[
                {"source": "check_length", "target": "long", "condition": "true"},
                {"source": "check_length", "target": "short", "condition": "false"},
                {"source": "short", "target": "end"},
                {"source": "long", "target": "end"},
            ],
        ))
        self.register(AgentDefinition(
            agent_id=UUID("00000000-0000-0000-0000-000000000005"),
            name="Loop Demo",
            description="A demo agent that loops until the user says stop.",
            system_prompt="You are a loop demo agent. Count iterations and stop when told.",
            workflow_mode="loop",
            nodes=[
                {"id": "ask", "type": "llm", "config": {"system_prompt": "Ask the user if they want to continue."}},
                {"id": "human", "type": "human", "config": {"prompt": "Reply 'yes' to continue or 'stop' to end."}},
                {
                    "id": "check_stop",
                    "type": "condition",
                    "config": {"condition_expression": "user_input.lower().strip() != 'stop'"},
                },
                {"id": "end", "type": "end", "config": {}},
            ],
            edges=[
                {"source": "ask", "target": "human"},
                {"source": "human", "target": "check_stop"},
                {"source": "check_stop", "target": "ask", "condition": "true"},
                {"source": "check_stop", "target": "end", "condition": "false"},
            ],
        ))


agent_registry = AgentRegistry()
