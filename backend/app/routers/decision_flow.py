from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional, Dict, Any
import logging
import uuid
from datetime import datetime
import json
import asyncio

from app.core.config import settings
from app.models.schemas import DecisionFlowCreate, DecisionFlowResponse, DecisionFlowStep, FlowExecutionRequest, FlowExecutionResponse
from app.services.neo4j_client import neo4j_client
from app.services.message_queue import mq_service
from app.services.redis_client import redis_client
from app.routers.auth import get_current_user, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decision-flows", tags=["Decision Flows"])





async def execute_flow_step(step: DecisionFlowStep, context: Dict[str, Any], tenant_id: str) -> Any:
    """Execute a single step in the decision flow"""
    logger.info(f"Executing step: {step.name} ({step.step_type})")
    
    try:
        if step.step_type == "query":
            # Execute knowledge graph query
            query_config = step.config.get("query", {})
            result = await neo4j_client.execute_query(
                query_config.get("cypher", ""),
                query_config.get("parameters", {})
            )
            context[step.output_variable or f"step_{step.id}"] = result
            return result
        
        elif step.step_type == "transform":
            # Apply data transformation
            transform_code = step.config.get("code", "")
            input_data = context.get(step.input_variable, {})
            
            # Simple transformation example (in production, use sandboxed execution)
            if transform_code == "extract_ids":
                result = [item.get("id") for item in input_data] if isinstance(input_data, list) else []
            else:
                result = input_data
            
            context[step.output_variable or f"step_{step.id}"] = result
            return result
        
        elif step.step_type == "condition":
            # Evaluate condition
            condition_config = step.config.get("condition", {})
            field = condition_config.get("field", "")
            operator = condition_config.get("operator", "eq")
            value = condition_config.get("value")
            
            input_data = context.get(step.input_variable, {})
            
            # Simple condition evaluation
            actual_value = input_data.get(field) if isinstance(input_data, dict) else None
            
            if operator == "eq":
                result = actual_value == value
            elif operator == "gt":
                result = actual_value > value if actual_value else False
            elif operator == "lt":
                result = actual_value < value if actual_value else False
            elif operator == "contains":
                result = value in str(actual_value) if actual_value else False
            else:
                result = False
            
            context[step.output_variable or f"step_{step.id}"] = result
            return result
        
        elif step.step_type == "notification":
            # Send notification (via RabbitMQ in production)
            notification_config = step.config.get("notification", {})
            message = {
                "type": "flow_notification",
                "flow_id": context.get("flow_id"),
                "step_id": step.id,
                "message": notification_config.get("message", "Flow step completed"),
                "recipients": notification_config.get("recipients", [])
            }
            
            await mq_service.publish_message(
                queue_name="notifications",
                message=message
            )
            
            context[step.output_variable or f"step_{step.id}"] = {"status": "sent", "message": message}
            return message
        
        elif step.step_type == "api_call":
            # External API call (implement with proper security)
            api_config = step.config.get("api", {})
            # In production, implement secure HTTP client with authentication
            result = {"status": "mock_success", "data": {}}
            context[step.output_variable or f"step_{step.id}"] = result
            return result
        
        else:
            logger.warning(f"Unknown step type: {step.step_type}")
            return None
            
    except Exception as e:
        logger.error(f"Step execution failed: {e}")
        raise


async def execute_decision_flow(
    flow_id: str,
    flow_data: Dict[str, Any],
    initial_context: Dict[str, Any],
    tenant_id: str
):
    """Execute a complete decision flow"""
    execution_id = str(uuid.uuid4())
    
    await redis_client.set_flow_execution(
        tenant_id,
        execution_id,
        {
            "flow_id": flow_id,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "steps_completed": [],
            "steps_failed": [],
            "context": initial_context
        }
    )
    
    try:
        steps = flow_data.get("steps", [])
        context = {**initial_context, "flow_id": flow_id, "execution_id": execution_id}
        
        for step_data in steps:
            step = DecisionFlowStep(**step_data)
            
            try:
                result = await execute_flow_step(step, context, tenant_id)
                execution_data = await redis_client.get_flow_execution(tenant_id, execution_id) or {}
                steps_completed = execution_data.get("steps_completed", [])
                steps_completed.append({
                    "step_id": step.id,
                    "step_name": step.name,
                    "completed_at": datetime.utcnow().isoformat(),
                    "result": str(result)[:500]  # Truncate for storage
                })
                await redis_client.update_flow_execution(tenant_id, execution_id, {"steps_completed": steps_completed})
                
                # Check for conditional branching
                if step.step_type == "condition":
                    condition_result = context.get(step.output_variable or f"step_{step.id}", False)
                    if not condition_result and step.on_false_goto:
                        # Skip to specified step
                        next_step_id = step.on_false_goto
                        # Find and continue from that step
                        continue
                
            except Exception as e:
                logger.error(f"Step {step.name} failed: {e}")
                execution_data = await redis_client.get_flow_execution(tenant_id, execution_id) or {}
                steps_failed = execution_data.get("steps_failed", [])
                steps_failed.append({
                    "step_id": step.id,
                    "step_name": step.name,
                    "error": str(e),
                    "failed_at": datetime.utcnow().isoformat()
                })
                await redis_client.update_flow_execution(tenant_id, execution_id, {"steps_failed": steps_failed})
                
                if not step.continue_on_error:
                    raise
        
        await redis_client.update_flow_execution(tenant_id, execution_id, {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "final_context": context
        })
        
        logger.info(f"Flow execution completed: {execution_id}")
        
    except Exception as e:
        await redis_client.update_flow_execution(tenant_id, execution_id, {
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.utcnow().isoformat()
        })
        logger.error(f"Flow execution failed: {execution_id} - {e}")


@router.post("", response_model=DecisionFlowResponse, status_code=status.HTTP_201_CREATED)
async def create_decision_flow(
    flow_data: DecisionFlowCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new decision flow"""
    flow_id = str(uuid.uuid4())
    
    try:
        # Store flow definition in Neo4j
        query = """
        CREATE (f:DecisionFlow {
            id: $id,
            name: $name,
            description: $description,
            version: $version,
            steps: $steps,
            created_at: $created_at,
            created_by: $created_by,
            tenant_id: $tenant_id,
            is_active: true
        })
        RETURN f
        """
        
        steps_json = [step.model_dump() for step in flow_data.steps]
        
        result = await neo4j_client.execute_query(
            query,
            {
                "id": flow_id,
                "name": flow_data.name,
                "description": flow_data.description or "",
                "version": flow_data.version or "1.0.0",
                "steps": steps_json,
                "created_at": datetime.utcnow().isoformat(),
                "created_by": current_user.username,
                "tenant_id": current_user.tenant_id
            }
        )
        
        logger.info(f"Decision flow created: {flow_id} ({flow_data.name})")
        
        return DecisionFlowResponse(
            id=flow_id,
            name=flow_data.name,
            description=flow_data.description,
            version=flow_data.version or "1.0.0",
            steps=flow_data.steps,
            created_at=datetime.utcnow().isoformat(),
            created_by=current_user.username,
            is_active=True
        )
    except Exception as e:
        logger.error(f"Failed to create decision flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{flow_id}", response_model=DecisionFlowResponse)
async def get_decision_flow(
    flow_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a decision flow by ID"""
    try:
        query = """
        MATCH (f:DecisionFlow {id: $id, tenant_id: $tenant_id})
        RETURN f
        """
        
        result = await neo4j_client.execute_query(query, {"id": flow_id, "tenant_id": current_user.tenant_id})
        
        if not result or len(result) == 0:
            raise HTTPException(status_code=404, detail="Decision flow not found")
        
        flow_data = result[0]["f"]
        steps = [DecisionFlowStep(**step) for step in flow_data.get("steps", [])]
        
        return DecisionFlowResponse(
            id=flow_data["id"],
            name=flow_data["name"],
            description=flow_data.get("description"),
            version=flow_data.get("version", "1.0.0"),
            steps=steps,
            created_at=flow_data.get("created_at"),
            created_by=flow_data.get("created_by"),
            is_active=flow_data.get("is_active", True)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get decision flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{flow_id}/execute", response_model=FlowExecutionResponse)
async def execute_decision_flow_endpoint(
    flow_id: str,
    execution_request: FlowExecutionRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user)
):
    """Execute a decision flow"""
    try:
        # Get flow definition
        query = """
        MATCH (f:DecisionFlow {id: $id, tenant_id: $tenant_id})
        RETURN f
        """
        
        result = await neo4j_client.execute_query(query, {"id": flow_id, "tenant_id": current_user.tenant_id})
        
        if not result or len(result) == 0:
            raise HTTPException(status_code=404, detail="Decision flow not found")
        
        flow_data = result[0]["f"]
        
        # Start async execution
        execution_id = str(uuid.uuid4())
        background_tasks.add_task(
            execute_decision_flow,
            flow_id,
            flow_data,
            execution_request.initial_context or {},
            current_user.tenant_id
        )
        
        logger.info(f"Flow execution started: {execution_id}")
        
        return FlowExecutionResponse(
            execution_id=execution_id,
            flow_id=flow_id,
            status="queued",
            started_at=datetime.utcnow().isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start flow execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions/{execution_id}", response_model=Dict[str, Any])
async def get_execution_status(
    execution_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get the status of a flow execution"""
    execution = await redis_client.get_flow_execution(current_user.tenant_id, execution_id)
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return execution


@router.get("", response_model=List[DecisionFlowResponse])
async def list_decision_flows(
    skip: int = 0,
    limit: int = 20,
    current_user: UserResponse = Depends(get_current_user)
):
    """List all decision flows for the current tenant"""
    try:
        query = """
        MATCH (f:DecisionFlow {tenant_id: $tenant_id})
        RETURN f
        ORDER BY f.created_at DESC
        SKIP $skip LIMIT $limit
        """
        
        result = await neo4j_client.execute_query(
            query,
            {"tenant_id": current_user.tenant_id, "skip": skip, "limit": limit}
        )
        
        flows = []
        for record in result:
            f = record["f"]
            steps = [DecisionFlowStep(**step) for step in f.get("steps", [])]
            flows.append(DecisionFlowResponse(
                id=f["id"],
                name=f["name"],
                description=f.get("description"),
                version=f.get("version", "1.0.0"),
                steps=steps,
                created_at=f.get("created_at"),
                created_by=f.get("created_by"),
                is_active=f.get("is_active", True)
            ))
        
        return flows
    except Exception as e:
        logger.error(f"Failed to list decision flows: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{flow_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_decision_flow(
    flow_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Deactivate a decision flow"""
    try:
        query = """
        MATCH (f:DecisionFlow {id: $id, tenant_id: $tenant_id})
        SET f.is_active = false,
            f.deactivated_at = $deactivated_at,
            f.deactivated_by = $deactivated_by
        """
        
        await neo4j_client.execute_query(
            query,
            {
                "id": flow_id,
                "tenant_id": current_user.tenant_id,
                "deactivated_at": datetime.utcnow().isoformat(),
                "deactivated_by": current_user.username
            }
        )
        
        logger.info(f"Decision flow deactivated: {flow_id}")
    except Exception as e:
        logger.error(f"Failed to deactivate decision flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_decision_flow(
    flow_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a decision flow"""
    try:
        query = """
        MATCH (f:DecisionFlow {id: $id, tenant_id: $tenant_id})
        DETACH DELETE f
        """
        
        await neo4j_client.execute_query(query, {"id": flow_id, "tenant_id": current_user.tenant_id})
        logger.info(f"Decision flow deleted: {flow_id}")
    except Exception as e:
        logger.error(f"Failed to delete decision flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))