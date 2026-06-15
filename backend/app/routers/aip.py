"""AIP (AI Platform) API Router"""
import json
import logging
from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.aip_schemas import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    SSEChunk,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSource,
    AgentRunRequest,
    AgentRunResponse,
    AgentListResponse,
    AgentDefinitionSchema,
    AgentStep,
    AgentSSEEvent,
    LLMCallLogResponse,
    LLMUsageTrendResponse,
    LLMUsageBucket,
    GuardrailsLogResponse,
    AvailableModelsResponse,
    ModelInfo,
)
from app.models.ontology_models import AIPLLMCall, AIPGuardrailsLog
from app.services.database import get_db
from app.services.llm_gateway import llm_gateway
from app.services.semantic_search import SemanticSearchService
from app.services.guardrails_service import GuardrailsService
from app.services.agent_engine import AgentEngine, AgentSession, agent_registry
from app.services.prompt_template_service import PromptTemplateService
from app.services import llama_index_rag

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AIP"])


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Non-streaming chat completion with guardrails."""
    tenant_id = getattr(request.state, "tenant_id", None)
    messages = [{"role": m.role, "content": m.content} for m in data.messages]
    last_user_message = messages[-1]["content"] if messages else ""

    # Guardrails input check
    guardrails = GuardrailsService(db, tenant_id)
    input_check = guardrails.check_input(last_user_message)
    if not input_check["passed"]:
        await guardrails.log_check(
            model=data.model or settings.DEFAULT_LLM_MODEL,
            input_text=last_user_message,
            output_text="",
            input_result=input_check,
            output_result={"passed": True, "score": 0, "triggered": [], "check_type": "output"},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Input blocked by guardrails: {input_check['triggered']}",
        )

    try:
        # Apply prompt template if provided
        prompt_service = PromptTemplateService(db, tenant_id)
        if data.prompt_template_id:
            rendered = await prompt_service.render(
                data.prompt_template_id,
                data.prompt_variables or {"user_input": last_user_message},
            )
            if rendered:
                messages.insert(0, {"role": "system", "content": rendered})

        result = await llm_gateway.chat(
            messages=messages,
            model=data.model,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            db=db,
        )
        choice = result.get("choices", [{}])[0]
        message_data = choice.get("message", {})
        usage_data = result.get("usage", {})
        # Guardrails output check
        output_check = guardrails.check_output(message_data.get("content", ""))
        safe_content = output_check.get("redacted_text", message_data.get("content", ""))
        await guardrails.log_check(
            model=result.get("model", data.model or settings.DEFAULT_LLM_MODEL),
            input_text=last_user_message,
            output_text=safe_content,
            input_result=input_check,
            output_result=output_check,
        )

        # Update prompt template usage statistics
        if data.prompt_template_id:
            await prompt_service.record_usage(
                data.prompt_template_id,
                usage_data.get("prompt_tokens", 0),
            )

        return ChatResponse(
            message=ChatMessage(
                role=message_data.get("role", "assistant"),
                content=safe_content,
            ),
            model=result.get("model", data.model or settings.DEFAULT_LLM_MODEL),
            usage={
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM gateway error: {e}")


async def _sse_generator(data: ChatRequest) -> AsyncGenerator[str, None]:
    """SSE generator for streaming chat."""
    messages = [{"role": m.role, "content": m.content} for m in data.messages]
    try:
        async for chunk_json in llm_gateway.chat_stream(
            messages=messages,
            model=data.model,
            temperature=data.temperature,
        ):
            chunk = json.loads(chunk_json)
            if "error" in chunk:
                yield f"data: {json.dumps({'error': chunk['error']})}\n\n"
                break
            if chunk.get("done"):
                yield f"data: [DONE]\n\n"
                break
            sse_data = json.dumps({"delta": chunk.get("delta", ""), "finish_reason": chunk.get("finish_reason")})
            yield f"data: {sse_data}\n\n"
    except Exception as e:
        logger.error(f"SSE generator error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    data: ChatRequest,
):
    """Streaming chat completion (SSE)."""
    return StreamingResponse(
        _sse_generator(data),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# RAG
# ---------------------------------------------------------------------------

@router.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(
    request: Request,
    data: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ontology-aware RAG query."""
    tenant_id = getattr(request.state, "tenant_id", None)
    guardrails = GuardrailsService(db, tenant_id)

    # Guardrails input check
    input_check = guardrails.check_input(data.query)
    if not input_check["passed"]:
        await guardrails.log_check(
            model=settings.DEFAULT_LLM_MODEL,
            input_text=data.query,
            output_text="",
            input_result=input_check,
            output_result={"passed": True, "score": 0, "triggered": [], "check_type": "output"},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Input blocked by guardrails: {input_check['triggered']}",
        )

    # Step 1: Retrieve relevant objects via semantic search
    search_service = SemanticSearchService(db, tenant_id)
    search_result = await search_service.search(
        query=data.query,
        object_types=data.object_types,
        search_mode=data.search_mode or "hybrid",
        top_k=data.top_k or 5,
    )

    # Step 2: Build context from retrieved objects
    context_parts = []
    sources = []
    for item in search_result.results:
        context_parts.append(f"[{item.object_type}] {item.object_key}: {json.dumps(item.properties_preview, ensure_ascii=False)}")
        sources.append(RAGSource(
            object_id=item.object_id,
            object_type=item.object_type,
            object_key=item.object_key,
            score=item.score,
            explanation=item.explanation,
            properties_preview=item.properties_preview,
        ))

    context = "\n".join(context_parts) if context_parts else "No relevant ontology objects found."

    # Step 3: Ask LLM to answer based on context
    default_system = "You are a helpful assistant. Answer the user's question based ONLY on the provided ontology context. If the context does not contain enough information, say so."
    default_user = f"Context:\n{context}\n\nQuestion: {data.query}\n\nAnswer:"

    prompt_service = PromptTemplateService(db, tenant_id)
    if data.prompt_template_id:
        rendered = await prompt_service.render(
            data.prompt_template_id,
            {
                "query": data.query,
                "context": context,
                **(data.prompt_variables or {}),
            },
        )
        if rendered:
            # Template is treated as system prompt; user prompt contains context + query
            system_prompt = rendered
            user_prompt = f"Context:\n{context}\n\nQuestion: {data.query}\n\nAnswer:"
        else:
            system_prompt = default_system
            user_prompt = default_user
    else:
        system_prompt = default_system
        user_prompt = default_user

    answer = ""
    model_used = ""
    usage_data: Dict[str, int] = {}

    # Optional LlamaIndex synthesis
    if data.use_llama_index:
        try:
            llama_answer = await llama_index_rag.query_with_llama_index(
                query=data.query,
                search_results=sources,
                system_prompt=system_prompt,
            )
            if llama_answer:
                answer = llama_answer
                model_used = "llama-index"
        except Exception as e:
            logger.warning(f"LlamaIndex RAG failed, falling back to native: {e}")

    # Native LLM synthesis
    if not answer:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            result = await llm_gateway.chat(
                messages=messages,
                model=settings.DEFAULT_LLM_MODEL,
                temperature=0.3,
                max_tokens=2048,
                db=db,
            )
            answer = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            model_used = result.get("model", settings.DEFAULT_LLM_MODEL)
            usage_data = result.get("usage", {}) or {}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"RAG LLM error: {e}")
            answer = f"Failed to generate answer: {e}"
            model_used = ""

    # Guardrails output check
    if answer and not answer.startswith("Failed to generate answer"):
        try:
            output_check = guardrails.check_output(answer, ontology_context=context)
            safe_answer = output_check.get("redacted_text", answer)
            await guardrails.log_check(
                model=model_used,
                input_text=data.query,
                output_text=safe_answer,
                input_result={"passed": True, "score": 0, "triggered": [], "check_type": "input"},
                output_result=output_check,
            )
            answer = safe_answer
        except Exception as e:
            logger.warning(f"RAG output guardrails failed: {e}")

    # Update prompt template usage statistics
    if data.prompt_template_id and model_used and model_used != "llama-index":
        try:
            await prompt_service.record_usage(
                data.prompt_template_id,
                usage_data.get("prompt_tokens", 0),
            )
        except Exception as e:
            logger.warning(f"Failed to record prompt template usage: {e}")

    return RAGQueryResponse(
        answer=answer,
        sources=sources,
        duration_ms=search_result.duration_ms,
        model=model_used,
    )


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

_agents_initialized = False


def _ensure_agents_initialized():
    """Lazy initialize agent registry with default agents."""
    global _agents_initialized
    if _agents_initialized:
        return
    try:
        agent_registry.create_default_agents()
        _agents_initialized = True
        logger.info("Agent registry initialized with %d agents", len(agent_registry.list_all()))
    except Exception as e:
        logger.warning(f"Agent registry init skipped: {e}")


@router.get("/agents", response_model=AgentListResponse)
async def list_agents():
    """List available agents."""
    _ensure_agents_initialized()
    agents = agent_registry.list_all()
    return AgentListResponse(agents=[AgentDefinitionSchema(**a.to_schema_dict()) for a in agents])


def _steps_to_schema(steps: list) -> list[AgentStep]:
    return [
        AgentStep(
            type=s.get("type", "unknown"),
            thought=s.get("thought"),
            content=s.get("content"),
            tool_calls=s.get("tool_calls"),
            duration_ms=s.get("duration_ms"),
            error=s.get("error"),
        )
        for s in steps
    ]


@router.post("/agents/{id}/run", response_model=AgentRunResponse)
async def run_agent(
    id: UUID,
    data: AgentRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Run an agent with user input."""
    tenant_id = getattr(request.state, "tenant_id", None)
    _ensure_agents_initialized()

    definition = agent_registry.get(id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Agent {id} not found")

    engine = AgentEngine(db=db, tenant_id=tenant_id, definition=definition)

    session = None
    if data.session_id:
        session = AgentSession(session_id=data.session_id, agent_id=id, tenant_id=tenant_id)

    result = await engine.run(user_input=data.input, session=session, context=data.context)

    response = AgentRunResponse(
        output=result["output"],
        status=result["status"],
        trace_id=result["trace_id"],
        steps=_steps_to_schema(result.get("steps", [])),
        session_id=data.session_id or result["trace_id"],
    )
    if result.get("requires_input"):
        response.requires_input = True
        response.prompt = result.get("prompt")
    return response


@router.get("/agents/{id}/status", response_model=AgentRunResponse)
async def get_agent_status(
    id: UUID,
    request: Request,
    trace_id: str = Query(..., description="Agent run trace ID"),
):
    """Get agent run status by trace ID."""
    tenant_id = getattr(request.state, "tenant_id", None)
    _ensure_agents_initialized()
    session = AgentSession(session_id=UUID(trace_id), agent_id=id, tenant_id=tenant_id)
    found = await session.load()
    if not found:
        return AgentRunResponse(output="", status="not_found", trace_id=trace_id)
    return AgentRunResponse(
        output=session.get_output(),
        status=session.get_status(),
        trace_id=trace_id,
        steps=_steps_to_schema(session.get_steps()),
        requires_input=session.get_status() == "awaiting_input",
        prompt=session.get_prompt(),
    )


@router.post("/agents/{id}/interrupt", response_model=AgentRunResponse)
async def interrupt_agent(
    id: UUID,
    request: Request,
    trace_id: str = Query(..., description="Agent run trace ID"),
):
    """Interrupt a running agent."""
    tenant_id = getattr(request.state, "tenant_id", None)
    _ensure_agents_initialized()
    session = AgentSession(session_id=UUID(trace_id), agent_id=id, tenant_id=tenant_id)
    await session.load()
    session.set_status("interrupted")
    session.set_output("Agent interrupted by user.")
    await session.save()
    return AgentRunResponse(
        output="Agent interrupted.",
        status="interrupted",
        trace_id=trace_id,
        steps=_steps_to_schema(session.get_steps()),
    )


@router.post("/agents/{id}/resume", response_model=AgentRunResponse)
async def resume_agent(
    id: UUID,
    data: AgentRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Resume an agent waiting for human input."""
    tenant_id = getattr(request.state, "tenant_id", None)
    _ensure_agents_initialized()

    definition = agent_registry.get(id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Agent {id} not found")

    if not data.session_id:
        raise HTTPException(status_code=400, detail="session_id is required to resume")

    session = AgentSession(session_id=data.session_id, agent_id=id, tenant_id=tenant_id)
    found = await session.load()
    if not found:
        raise HTTPException(status_code=404, detail="Agent session not found")

    engine = AgentEngine(db=db, tenant_id=tenant_id, definition=definition)
    result = await engine.run(user_input=data.input, session=session, context=data.context)

    response = AgentRunResponse(
        output=result["output"],
        status=result["status"],
        trace_id=result["trace_id"],
        steps=_steps_to_schema(result.get("steps", [])),
        session_id=str(data.session_id),
    )
    if result.get("requires_input"):
        response.requires_input = True
        response.prompt = result.get("prompt")
    return response


async def _agent_sse_generator(
    engine: AgentEngine,
    session: AgentSession,
    trace_id: UUID,
    user_input: str,
    context: Optional[dict],
) -> AsyncGenerator[str, None]:
    """SSE generator that streams agent step events."""

    async def event_stream() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'event': 'start', 'trace_id': str(trace_id)})}\n\n"

        async for step in engine.run_stream(
            user_input=user_input, session=session, context=context
        ):
            payload = {
                "event": step.get("event", "step"),
                "trace_id": str(trace_id),
                "data": step.get("data", {}),
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if step.get("event") == "human_input_required":
                break
            if step.get("event") in ("completed", "failed", "interrupted"):
                break

        yield f"data: {json.dumps({'event': 'done', 'trace_id': str(trace_id)})}\n\n"

    async for line in event_stream():
        yield line


@router.post("/agents/{id}/stream")
async def stream_agent(
    id: UUID,
    data: AgentRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Run an agent and stream step events via SSE."""
    tenant_id = getattr(request.state, "tenant_id", None)
    _ensure_agents_initialized()

    definition = agent_registry.get(id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Agent {id} not found")

    engine = AgentEngine(db=db, tenant_id=tenant_id, definition=definition)
    trace_id = data.session_id or engine.new_trace_id()
    session = AgentSession(session_id=trace_id, agent_id=id, tenant_id=tenant_id)

    return StreamingResponse(
        _agent_sse_generator(
            engine=engine,
            session=session,
            trace_id=trace_id,
            user_input=data.input,
            context=data.context,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

@router.get("/llm-calls", response_model=list[LLMCallLogResponse])
async def list_llm_calls(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List LLM call logs."""
    total_result = await db.execute(select(func.count()).select_from(AIPLLMCall))
    total = total_result.scalar() or 0
    result = await db.execute(
        select(AIPLLMCall)
        .order_by(AIPLLMCall.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return [
        LLMCallLogResponse(
            id=log.id,
            model=log.model,
            prompt_tokens=log.prompt_tokens,
            completion_tokens=log.completion_tokens,
            duration_ms=log.duration_ms,
            status=log.status,
            created_at=log.created_at,
        )
        for log in items
    ]


@router.get("/llm-calls/aggregate", response_model=LLMUsageTrendResponse)
async def aggregate_llm_usage(
    request: Request,
    db: AsyncSession = Depends(get_db),
    hours: int = Query(24, ge=1, le=168),
    group_by: str = Query("hour", pattern="^(hour|day)$"),
):
    """Aggregate LLM call volume/cost into time buckets for the dashboard trend chart."""
    tenant_id = getattr(request.state, "tenant_id", UUID(int=0))

    bucket_seconds = 3600 if group_by == "hour" else 86400
    bucket_count = hours if group_by == "hour" else max(1, hours // 24)

    # Use PG date_trunc to bucket; (1.0 / bucket_seconds) keeps a numeric ratio
    # that lets us pull the bucket start with to_timestamp.
    epoch = func.extract("epoch", AIPLLMCall.created_at)
    bucket_idx = func.floor(epoch / bucket_seconds).cast(type_=AIPLLMCall.id.type)
    bucket_start = func.to_timestamp(bucket_idx * bucket_seconds)

    rows = await db.execute(
        select(
            bucket_start.label("bucket"),
            func.count().label("call_count"),
            func.coalesce(func.sum(AIPLLMCall.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AIPLLMCall.estimated_cost_cents), 0).label(
                "estimated_cost_cents"
            ),
        )
        .where(AIPLLMCall.tenant_id == tenant_id)
        .where(AIPLLMCall.created_at >= func.now() - func.make_interval(0, 0, 0, 0, 0, 0, hours))
        .group_by("bucket")
        .order_by("bucket")
    )

    seen: Dict[str, LLMUsageBucket] = {}
    for row in rows:
        # PG returns a datetime; normalize to ISO with minute precision so the
        # frontend can group_by and chart axis stay stable.
        bucket_dt = row.bucket
        if hasattr(bucket_dt, "isoformat"):
            bucket_key = bucket_dt.isoformat(timespec="minutes")
        else:
            bucket_key = str(bucket_dt)
        seen[bucket_key] = LLMUsageBucket(
            bucket=bucket_key,
            call_count=int(row.call_count or 0),
            total_tokens=int(row.total_tokens or 0),
            estimated_cost_cents=int(row.estimated_cost_cents or 0),
        )

    # Fill empty trailing buckets so the chart shows the full window
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    buckets: List[LLMUsageBucket] = []
    for offset in range(bucket_count - 1, -1, -1):
        ts = now - timedelta(seconds=bucket_seconds * offset)
        key = ts.isoformat(timespec="minutes")
        buckets.append(
            seen.get(
                key,
                LLMUsageBucket(
                    bucket=key,
                    call_count=0,
                    total_tokens=0,
                    estimated_cost_cents=0,
                ),
            )
        )

    return LLMUsageTrendResponse(
        group_by=group_by,
        hours=hours,
        buckets=buckets,
    )


@router.get("/guardrails-logs", response_model=list[GuardrailsLogResponse])
async def list_guardrails_logs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List guardrails logs."""
    total_result = await db.execute(select(func.count()).select_from(AIPGuardrailsLog))
    total = total_result.scalar() or 0
    result = await db.execute(
        select(AIPGuardrailsLog)
        .order_by(AIPGuardrailsLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return [
        GuardrailsLogResponse(
            id=log.id,
            model=log.model,
            input_preview=log.input_preview,
            output_preview=log.output_preview,
            triggered=log.triggered,
            rules_triggered=log.rules_triggered or [],
            created_at=log.created_at,
        )
        for log in items
    ]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@router.get("/models", response_model=AvailableModelsResponse)
async def list_models():
    """List available LLM models."""
    try:
        models_data = await llm_gateway.get_available_models()
        models = []
        for m in models_data:
            models.append(ModelInfo(
                id=m.get("id", ""),
                name=m.get("name", m.get("id", "")),
                provider=m.get("provider", "unknown"),
                max_tokens=m.get("max_tokens", 4096),
                supports_streaming=m.get("supports_streaming", True),
            ))
        return AvailableModelsResponse(models=models)
    except Exception as e:
        logger.warning(f"Failed to list models: {e}")
        return AvailableModelsResponse(models=[
            ModelInfo(id="gpt-4o", name="GPT-4o", provider="openai", max_tokens=4096),
            ModelInfo(id="gpt-4o-mini", name="GPT-4o Mini", provider="openai", max_tokens=4096),
            ModelInfo(id="claude-3-5-sonnet", name="Claude 3.5 Sonnet", provider="anthropic", max_tokens=4096),
        ])
