"""Agent Engine - Lightweight agent orchestration for the AIP layer.

Design: Custom async workflow engine integrated with existing services.
- Uses LLMGateway for LLM calls
- Uses ActionExecutor for ontology actions  
- Uses SemanticSearchService for knowledge retrieval
- Uses Redis for session state persistence

Workflow modes: sequential, branching, loop.
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.llm_gateway import llm_gateway
from app.services.redis_client import redis_client

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
    ):
        self.agent_id = agent_id
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model = model or settings.DEFAULT_LLM_MODEL
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.workflow_mode = workflow_mode


class AgentSession:
    """Redis-backed session state."""

    PREFIX = "agent_session"
    TTL = 3600

    def __init__(self, session_id: UUID, agent_id: UUID, tenant_id: UUID):
        self.session_id = session_id
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self._messages: List[Dict[str, str]] = []
        self._status = "pending"
        self._last_output = ""

    @property
    def key(self) -> str:
        return f"{self.PREFIX}:{self.tenant_id}:{self.session_id}"

    async def save(self) -> None:
        data = json.dumps({
            "session_id": str(self.session_id),
            "agent_id": str(self.agent_id),
            "messages": json.dumps(self._messages),
            "status": self._status,
            "last_output": self._last_output,
        })
        try:
            if redis_client.client:
                await redis_client.client.setex(self.key, self.TTL, data)
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


class AgentEngine:
    """Core agent orchestration engine."""

    def __init__(self, db: AsyncSession, tenant_id: UUID, definition: AgentDefinition):
        self.db = db
        self.tenant_id = tenant_id
        self.definition = definition
        self._should_interrupt = False
        self._steps: List[Dict[str, Any]] = []

    def interrupt(self) -> None:
        self._should_interrupt = True

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
        await session.save()

        try:
            result = await self._run_loop(session, trace_id)
            session.set_status("completed")
            await session.save()
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

    async def _run_loop(
        self, session: AgentSession, trace_id: UUID, max_iters: Optional[int] = None
    ) -> Dict[str, Any]:
        max_iters = max_iters or self.definition.max_iterations
        final_output = ""

        for _ in range(max_iters):
            if self._should_interrupt:
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
                self._steps.append({
                    "type": "llm_error",
                    "error": str(e),
                    "duration_ms": int((time.time() - step_start) * 1000),
                })
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
                continue

            final_output = content
            session.set_output(final_output)
            self._steps.append({"type": "answer", "content": final_output, "duration_ms": step_duration})
            session.add_message("assistant", final_output)
            break

        if not final_output:
            final_output = content or "Max iterations reached."
            session.set_output(final_output)

        return {
            "output": final_output,
            "steps": self._steps,
            "status": "completed",
            "trace_id": str(trace_id),
        }

    async def _execute_tool(self, tool_name: str, **kwargs) -> str:
        for tool in self.definition.tools:
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
            system_prompt=(
                "You are a helpful assistant for the Meatapivot enterprise knowledge platform. "
                "You help users understand their ontology, execute actions, and find information. "
                "Be concise, accurate, and always refer to specific ontology objects when relevant."
            ),
            max_iterations=5,
        ))
        self.register(AgentDefinition(
            agent_id=UUID("00000000-0000-0000-0000-000000000002"),
            name="Ontology Explorer",
            system_prompt=(
                "You are an ontology exploration specialist. Help users navigate and understand "
                "their ontology objects. Guide them to use the search and object view features. "
                "Always be specific about which Object Types or Interfaces are relevant."
            ),
            max_iterations=5,
        ))
        self.register(AgentDefinition(
            agent_id=UUID("00000000-0000-0000-0000-000000000003"),
            name="Action Agent",
            system_prompt=(
                "You are an action execution specialist. Help users perform operations on "
                "ontology objects. Guide them to find the right actions and parameters. "
                "Always verify the action exists and the user understands consequences."
            ),
            max_iterations=8,
        ))


agent_registry = AgentRegistry()
