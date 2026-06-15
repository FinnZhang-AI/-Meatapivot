"""Unit tests for the AIP Agent engine and router schemas.

These tests mock external dependencies (LLM gateway, Redis, SemanticSearch,
ActionExecutor) so they can run without a full infrastructure stack.
"""

import json
import pytest
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio


def _import_or_skip():
    try:
        from app.services.agent_engine import AgentEngine, AgentSession, AgentDefinition, agent_registry
        from app.models.aip_schemas import AgentRunRequest, AgentRunResponse, AgentListResponse
        return AgentEngine, AgentSession, AgentDefinition, agent_registry, AgentRunRequest, AgentRunResponse, AgentListResponse
    except Exception as e:
        pytest.skip(f"Backend dependencies not available: {e}")


async def test_agent_session_roundtrip():
    """AgentSession should serialize and deserialize state correctly."""
    AgentEngine, AgentSession, AgentDefinition, *_ = _import_or_skip()

    session_id = uuid4()
    agent_id = uuid4()
    tenant_id = uuid4()
    session = AgentSession(session_id, agent_id, tenant_id)
    session.add_message("system", "You are a test agent")
    session.add_message("user", "hello")
    session.set_status("running")
    session.set_output("world")
    session.add_step({"type": "answer", "content": "world"})
    session.set_prompt("Need confirmation")
    session.set_current_node("n1")
    session.set_variable("user_input", "hello")

    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value=session._serialize().encode())
    fake_redis.setex = AsyncMock(return_value=True)

    with patch("app.services.agent_engine.redis_client") as mock_redis:
        mock_redis.client = fake_redis
        await session.save()
        fake_redis.setex.assert_awaited_once()

        loaded_session = AgentSession(session_id, agent_id, tenant_id)
        found = await loaded_session.load()
        assert found is True
        assert loaded_session.get_status() == "running"
        assert loaded_session.get_output() == "world"
        assert loaded_session.get_messages() == [
            {"role": "system", "content": "You are a test agent"},
            {"role": "user", "content": "hello"},
        ]
        assert loaded_session.get_steps() == [{"type": "answer", "content": "world"}]
        assert loaded_session.get_prompt() == "Need confirmation"
        assert loaded_session.get_current_node() == "n1"
        assert loaded_session.get_variable("user_input") == "hello"


async def test_agent_engine_completes_without_tools():
    """Agent should complete when LLM returns a plain answer without tool calls."""
    AgentEngine, AgentSession, AgentDefinition, *_ = _import_or_skip()

    definition = AgentDefinition(
        agent_id=uuid4(),
        name="Test Agent",
        system_prompt="You are a test agent",
        max_iterations=3,
    )

    mock_db = MagicMock()
    engine = AgentEngine(db=mock_db, tenant_id=uuid4(), definition=definition)

    fake_redis = MagicMock()
    fake_redis.setex = AsyncMock(return_value=True)
    fake_redis.get = AsyncMock(return_value=None)

    with patch("app.services.agent_engine.redis_client") as mock_redis_client:
        mock_redis_client.client = fake_redis
        with patch("app.services.agent_engine.llm_gateway") as mock_llm:
            mock_llm.chat = AsyncMock(return_value={
                "choices": [{"message": {"role": "assistant", "content": "Final answer"}}],
                "model": "gpt-4o-mini",
            })
            result = await engine.run(user_input="hello")

    assert result["status"] == "completed"
    assert result["output"] == "Final answer"
    assert any(s["type"] == "answer" for s in result["steps"])


async def test_agent_engine_human_in_the_loop():
    """Agent should pause for human input after a tool call when HITL is enabled."""
    AgentEngine, AgentSession, AgentDefinition, *_ = _import_or_skip()

    definition = AgentDefinition(
        agent_id=uuid4(),
        name="HITL Agent",
        system_prompt="You are a careful agent",
        tools=[],
        max_iterations=3,
        human_in_the_loop=True,
        human_prompt="Please confirm before continuing.",
    )

    mock_db = MagicMock()
    engine = AgentEngine(db=mock_db, tenant_id=uuid4(), definition=definition)

    fake_redis = MagicMock()
    fake_redis.setex = AsyncMock(return_value=True)
    fake_redis.get = AsyncMock(return_value=None)

    with patch("app.services.agent_engine.redis_client") as mock_redis_client:
        mock_redis_client.client = fake_redis
        with patch("app.services.agent_engine.llm_gateway") as mock_llm:
            mock_llm.chat = AsyncMock(return_value={
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "I will run a tool",
                        "tool_calls": [{
                            "id": "tc_1",
                            "type": "function",
                            "function": {"name": "noop", "arguments": "{}"},
                        }],
                    },
                }],
                "model": "gpt-4o-mini",
            })
            result = await engine.run(user_input="do something")

    assert result["status"] == "awaiting_input"
    assert result["requires_input"] is True
    assert result["prompt"] == "Please confirm before continuing."
    assert any(s["type"] == "llm" for s in result["steps"])


async def test_sequential_workflow():
    """A simple search -> llm -> end workflow should execute sequentially."""
    AgentEngine, AgentSession, AgentDefinition, *_ = _import_or_skip()

    definition = AgentDefinition(
        agent_id=uuid4(),
        name="Sequential Workflow",
        system_prompt="You are a workflow agent",
        workflow_mode="sequential",
        nodes=[
            {"id": "search", "type": "search", "config": {"query_template": "{user_input}", "top_k": 3}},
            {"id": "answer", "type": "llm", "config": {"system_prompt": "Answer based on search results."}},
            {"id": "end", "type": "end", "config": {}},
        ],
        edges=[
            {"source": "search", "target": "answer"},
            {"source": "answer", "target": "end"},
        ],
    )

    mock_db = MagicMock()
    engine = AgentEngine(db=mock_db, tenant_id=uuid4(), definition=definition)

    fake_redis = MagicMock()
    fake_redis.setex = AsyncMock(return_value=True)
    fake_redis.get = AsyncMock(return_value=None)

    with patch("app.services.agent_engine.redis_client") as mock_redis_client:
        mock_redis_client.client = fake_redis
        with patch("app.services.agent_engine.llm_gateway") as mock_llm:
            mock_llm.chat = AsyncMock(return_value={
                "choices": [{"message": {"role": "assistant", "content": "Workflow answer"}}],
                "model": "gpt-4o-mini",
            })
            with patch("app.services.agent_engine.SemanticSearchService") as mock_search:
                mock_result = MagicMock()
                mock_result.results = []
                mock_search.return_value.search = AsyncMock(return_value=mock_result)
                result = await engine.run(user_input="test query")

    assert result["status"] == "completed"
    assert any(s["type"] == "search" for s in result["steps"])
    assert any(s["type"] == "answer" for s in result["steps"])


async def test_branching_workflow():
    """A condition node should route to the correct branch based on variables."""
    AgentEngine, AgentSession, AgentDefinition, *_ = _import_or_skip()

    definition = AgentDefinition(
        agent_id=uuid4(),
        name="Branching Workflow",
        system_prompt="You are a workflow agent",
        workflow_mode="branching",
        nodes=[
            {"id": "check", "type": "condition", "config": {"condition_expression": "len(user_input) > 5"}},
            {"id": "long", "type": "llm", "config": {"system_prompt": "Long input."}},
            {"id": "short", "type": "llm", "config": {"system_prompt": "Short input."}},
            {"id": "end", "type": "end", "config": {}},
        ],
        edges=[
            {"source": "check", "target": "long", "condition": "true"},
            {"source": "check", "target": "short", "condition": "false"},
            {"source": "long", "target": "end"},
            {"source": "short", "target": "end"},
        ],
    )

    mock_db = MagicMock()
    engine = AgentEngine(db=mock_db, tenant_id=uuid4(), definition=definition)

    fake_redis = MagicMock()
    fake_redis.setex = AsyncMock(return_value=True)
    fake_redis.get = AsyncMock(return_value=None)

    with patch("app.services.agent_engine.redis_client") as mock_redis_client:
        mock_redis_client.client = fake_redis
        with patch("app.services.agent_engine.llm_gateway") as mock_llm:
            mock_llm.chat = AsyncMock(return_value={
                "choices": [{"message": {"role": "assistant", "content": "Answer"}}],
                "model": "gpt-4o-mini",
            })
            result = await engine.run(user_input="this is a long query")

    assert result["status"] == "completed"
    condition_step = next((s for s in result["steps"] if s["type"] == "condition"), None)
    assert condition_step is not None
    assert condition_step["content"] == "True"


async def test_loop_workflow_pauses_at_human_node():
    """A loop workflow should pause at the human node on the first iteration."""
    AgentEngine, AgentSession, AgentDefinition, *_ = _import_or_skip()

    definition = AgentDefinition(
        agent_id=uuid4(),
        name="Loop Workflow",
        system_prompt="You are a loop agent",
        workflow_mode="loop",
        nodes=[
            {"id": "ask", "type": "llm", "config": {"system_prompt": "Ask to continue."}},
            {"id": "human", "type": "human", "config": {"prompt": "Continue?"}},
            {"id": "check", "type": "condition", "config": {"condition_expression": "user_input.lower().strip() != 'stop'"}},
            {"id": "end", "type": "end", "config": {}},
        ],
        edges=[
            {"source": "ask", "target": "human"},
            {"source": "human", "target": "check"},
            {"source": "check", "target": "ask", "condition": "true"},
            {"source": "check", "target": "end", "condition": "false"},
        ],
    )

    mock_db = MagicMock()
    engine = AgentEngine(db=mock_db, tenant_id=uuid4(), definition=definition)

    fake_redis = MagicMock()
    fake_redis.setex = AsyncMock(return_value=True)
    fake_redis.get = AsyncMock(return_value=None)

    with patch("app.services.agent_engine.redis_client") as mock_redis_client:
        mock_redis_client.client = fake_redis
        with patch("app.services.agent_engine.llm_gateway") as mock_llm:
            mock_llm.chat = AsyncMock(return_value={
                "choices": [{"message": {"role": "assistant", "content": "Shall I continue?"}}],
                "model": "gpt-4o-mini",
            })
            result = await engine.run(user_input="start")

    assert result["status"] == "awaiting_input"
    assert result["requires_input"] is True


async def test_agent_registry_default_agents():
    """Default agents should be registered with expected IDs and workflow support."""
    AgentEngine, AgentSession, AgentDefinition, agent_registry, *_ = _import_or_skip()

    agent_registry._agents.clear()
    agent_registry.create_default_agents()
    agents = agent_registry.list_all()

    assert len(agents) == 5
    names = {a.name for a in agents}
    assert names == {"General Assistant", "Ontology Explorer", "Action Agent", "Condition Branching Demo", "Loop Demo"}

    general = agent_registry.get(UUID("00000000-0000-0000-0000-000000000001"))
    assert general is not None
    assert general.workflow_mode == "sequential"
    assert not general.has_workflow

    explorer = agent_registry.get(UUID("00000000-0000-0000-0000-000000000002"))
    assert explorer is not None
    assert explorer.has_workflow
    assert len(explorer.nodes) == 3
