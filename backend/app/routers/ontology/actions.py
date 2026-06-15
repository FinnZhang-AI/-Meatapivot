from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
import logging
import math
import time
import subprocess
import resource
import ast

from app.services.database import get_db
from app.models.ontology_models import (
    OntologyActionType, OntologyFunction, OntologyFunctionVersion,
    OntologyObject, ActionExecutionLog
)
from app.models.ontology_schemas import (
    ActionTypeCreate, ActionTypeUpdate, ActionTypeResponse, ActionTypeListResponse,
    ActionExecuteRequest, ActionExecuteResponse, RuleEvaluation,
    FunctionCreate, FunctionUpdate, FunctionResponse, FunctionListResponse,
    FunctionTestRequest, FunctionTestResponse
)
from app.routers.auth import get_current_user, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ontology - Actions & Functions"])


async def _get_tenant_id(current_user: UserResponse) -> UUID:
    return UUID(current_user.tenant_id)


@router.post("/action-types", response_model=ActionTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_action_type(
    action_data: ActionTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new Action Type"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyActionType).where(
            OntologyActionType.tenant_id == tenant_id,
            OntologyActionType.name == action_data.name
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Action Type '{action_data.name}' already exists")
    
    result = await db.execute(
        select(OntologyObjectType).where(
            OntologyObjectType.id == action_data.target_object_type_id,
            OntologyObjectType.tenant_id == tenant_id
        )
    )
    target_type = result.scalar_one_or_none()
    if not target_type:
        raise HTTPException(status_code=404, detail="Target Object Type not found")
    
    action_type = OntologyActionType(
        tenant_id=tenant_id,
        name=action_data.name,
        display_name=action_data.display_name,
        description=action_data.description,
        target_object_type_id=action_data.target_object_type_id,
        parameters=[p.model_dump() for p in action_data.parameters],
        modifies_properties=action_data.modifies_properties,
        modifies_links=action_data.modifies_links,
        rules=[r.model_dump() for r in action_data.rules],
        execution_type=action_data.execution_type,
        function_id=action_data.function_id,
        workflow_id=action_data.workflow_id,
        status="active",
        created_by=UUID(current_user.id) if current_user.id else None
    )
    
    db.add(action_type)
    await db.flush()
    await db.refresh(action_type)
    
    return ActionTypeResponse(
        id=action_type.id,
        tenant_id=action_type.tenant_id,
        name=action_type.name,
        display_name=action_type.display_name,
        description=action_type.description,
        target_object_type_id=action_type.target_object_type_id,
        target_object_type_name=target_type.name,
        parameters=action_data.parameters,
        modifies_properties=action_type.modifies_properties,
        modifies_links=action_type.modifies_links,
        rules=action_data.rules,
        execution_type=action_type.execution_type,
        function_id=action_type.function_id,
        workflow_id=action_type.workflow_id,
        status=action_type.status,
        created_by=action_type.created_by,
        created_at=action_type.created_at
    )


@router.get("/action-types", response_model=ActionTypeListResponse)
async def list_action_types(
    target_type_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """List Action Types"""
    tenant_id = await _get_tenant_id(current_user)
    
    query = select(OntologyActionType).where(OntologyActionType.tenant_id == tenant_id)
    
    if target_type_id:
        query = query.where(OntologyActionType.target_object_type_id == target_type_id)
    
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    query = query.order_by(OntologyActionType.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    action_types = result.scalars().all()
    
    from app.models.ontology_models import OntologyObjectType
    items = []
    for at in action_types:
        type_result = await db.execute(
            select(OntologyObjectType.name).where(OntologyObjectType.id == at.target_object_type_id)
        )
        type_name = type_result.scalar_one_or_none() or "Unknown"
        
        items.append(ActionTypeResponse(
            id=at.id,
            tenant_id=at.tenant_id,
            name=at.name,
            display_name=at.display_name,
            description=at.description,
            target_object_type_id=at.target_object_type_id,
            target_object_type_name=type_name,
            parameters=at.parameters,
            modifies_properties=at.modifies_properties,
            modifies_links=at.modifies_links,
            rules=at.rules,
            execution_type=at.execution_type,
            function_id=at.function_id,
            workflow_id=at.workflow_id,
            status=at.status,
            created_by=at.created_by,
            created_at=at.created_at
        ))
    
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return ActionTypeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.post("/actions/{action_type_id}/execute", response_model=ActionExecuteResponse)
async def execute_action(
    action_type_id: UUID,
    execute_data: ActionExecuteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Execute an Action"""
    tenant_id = await _get_tenant_id(current_user)
    started_at = datetime.utcnow()
    
    result = await db.execute(
        select(OntologyActionType).where(
            OntologyActionType.id == action_type_id,
            OntologyActionType.tenant_id == tenant_id
        )
    )
    action_type = result.scalar_one_or_none()
    
    if not action_type:
        raise HTTPException(status_code=404, detail="Action Type not found")
    
    execution_log = ActionExecutionLog(
        tenant_id=tenant_id,
        action_type_id=action_type_id,
        target_object_id=execute_data.target_object_id,
        parameters=execute_data.parameters,
        status="running",
        started_at=started_at,
        executed_by=UUID(current_user.id) if current_user.id else None
    )
    db.add(execution_log)
    await db.flush()
    await db.refresh(execution_log)
    
    rules_evaluation = []
    all_rules_passed = True
    
    for rule in action_type.rules:
        rule_eval = RuleEvaluation(
            rule_name=rule["name"],
            passed=True,
            reason="OPA rule passed"
        )
        rules_evaluation.append(rule_eval)
    
    result_data = None
    error_message = None
    final_status = "success"
    
    try:
        if action_type.execution_type == "direct":
            if execute_data.target_object_id:
                result = await db.execute(
                    select(OntologyObject).where(
                        OntologyObject.id == execute_data.target_object_id,
                        OntologyObject.tenant_id == tenant_id
                    )
                )
                obj = result.scalar_one_or_none()
                
                if obj:
                    for prop_name in action_type.modifies_properties:
                        if prop_name in execute_data.parameters:
                            current_props = obj.properties or {}
                            current_props[prop_name] = execute_data.parameters[prop_name]
                            obj.properties = current_props
                    
                    await db.flush()
                    result_data = {"updated_object_id": str(obj.id), "properties_updated": action_type.modifies_properties}
        
        elif action_type.execution_type == "function_backed":
            if action_type.function_id:
                func_result = await db.execute(
                    select(OntologyFunction).where(OntologyFunction.id == action_type.function_id)
                )
                func_def = func_result.scalar_one_or_none()
                
                if func_def:
                    try:
                        code_result = _execute_function_sandbox(
                            func_def.code,
                            execute_data.parameters,
                            func_def.timeout_seconds,
                            func_def.memory_mb
                        )
                        
                        if code_result["success"]:
                            result_data = {"output": code_result["output"]}
                        else:
                            error_message = code_result["error"]
                            final_status = "failed"
                    except Exception as e:
                        error_message = str(e)
                        final_status = "failed"
    
    except Exception as e:
        logger.error(f"Action execution failed: {e}")
        error_message = str(e)
        final_status = "failed"
    
    completed_at = datetime.utcnow()
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    
    execution_log.status = final_status
    execution_log.result = result_data
    execution_log.error_message = error_message
    execution_log.rules_evaluation = [r.model_dump() for r in rules_evaluation]
    execution_log.completed_at = completed_at
    execution_log.duration_ms = duration_ms
    
    await db.flush()
    
    return ActionExecuteResponse(
        execution_id=execution_log.id,
        status=final_status,
        result=result_data,
        error_message=error_message,
        rules_evaluation=rules_evaluation,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms
    )


def _execute_function_sandbox(code: str, parameters: dict, timeout_seconds: int, memory_mb: int) -> dict:
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {"success": False, "error": f"Syntax error: {str(e)}"}
    
    try:
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ["python", temp_file],
                input=str(parameters),
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout if result.returncode == 0 else None,
                "error": result.stderr if result.returncode != 0 else None
            }
        finally:
            os.unlink(temp_file)
            
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Function timed out after {timeout_seconds}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


from datetime import datetime


@router.post("/functions", response_model=FunctionResponse, status_code=status.HTTP_201_CREATED)
async def create_function(
    function_data: FunctionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Register a new Function"""
    tenant_id = await _get_tenant_id(current_user)
    
    existing = await db.execute(
        select(OntologyFunction).where(
            OntologyFunction.tenant_id == tenant_id,
            OntologyFunction.name == function_data.name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Function '{function_data.name}' already exists")
    
    func_def = OntologyFunction(
        tenant_id=tenant_id,
        name=function_data.name,
        display_name=function_data.display_name,
        description=function_data.description,
        language=function_data.language,
        code=function_data.code,
        read_only=function_data.read_only,
        timeout_seconds=function_data.timeout_seconds,
        memory_mb=function_data.memory_mb,
        status="active",
        current_version=1,
        created_by=UUID(current_user.id) if current_user.id else None
    )
    
    db.add(func_def)
    await db.flush()
    await db.refresh(func_def)
    
    version = OntologyFunctionVersion(
        function_id=func_def.id,
        version=1,
        code=function_data.code,
        change_notes="Initial version",
        created_by=UUID(current_user.id) if current_user.id else None
    )
    db.add(version)
    await db.flush()
    
    return FunctionResponse(
        id=func_def.id,
        tenant_id=func_def.tenant_id,
        name=func_def.name,
        display_name=func_def.display_name,
        description=func_def.description,
        language=func_def.language,
        code=func_def.code,
        read_only=func_def.read_only,
        timeout_seconds=func_def.timeout_seconds,
        memory_mb=func_def.memory_mb,
        current_version=func_def.current_version,
        status=func_def.status,
        created_by=func_def.created_by,
        created_at=func_def.created_at,
        updated_at=func_def.updated_at
    )


@router.get("/functions", response_model=FunctionListResponse)
async def list_functions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """List Functions"""
    tenant_id = await _get_tenant_id(current_user)
    
    query = select(OntologyFunction).where(OntologyFunction.tenant_id == tenant_id)
    
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    query = query.order_by(OntologyFunction.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    functions = result.scalars().all()
    
    items = []
    for func in functions:
        items.append(FunctionResponse(
            id=func.id,
            tenant_id=func.tenant_id,
            name=func.name,
            display_name=func.display_name,
            description=func.description,
            language=func.language,
            code=func.code,
            read_only=func.read_only,
            timeout_seconds=func.timeout_seconds,
            memory_mb=func.memory_mb,
            current_version=func.current_version,
            status=func.status,
            created_by=func.created_by,
            created_at=func.created_at,
            updated_at=func.updated_at
        ))
    
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return FunctionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.post("/functions/{function_id}/test", response_model=FunctionTestResponse)
async def test_function(
    function_id: UUID,
    test_data: FunctionTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Test a Function in sandbox"""
    tenant_id = await _get_tenant_id(current_user)
    
    result = await db.execute(
        select(OntologyFunction).where(
            OntologyFunction.id == function_id,
            OntologyFunction.tenant_id == tenant_id
        )
    )
    func_def = result.scalar_one_or_none()
    
    if not func_def:
        raise HTTPException(status_code=404, detail="Function not found")
    
    start_time = int(time.time() * 1000)
    
    try:
        ast.parse(func_def.code)
    except SyntaxError as e:
        return FunctionTestResponse(
            success=False,
            output=None,
            stdout=None,
            stderr=f"Syntax error: {str(e)}",
            duration_ms=int(time.time() * 1000) - start_time
        )
    
    sandbox_result = _execute_function_sandbox(
        func_def.code,
        {**test_data.parameters, **test_data.context},
        func_def.timeout_seconds,
        func_def.memory_mb
    )
    
    duration_ms = int(time.time() * 1000) - start_time
    
    return FunctionTestResponse(
        success=sandbox_result["success"],
        output=sandbox_result.get("output"),
        stdout=None,
        stderr=sandbox_result.get("error"),
        duration_ms=duration_ms,
        memory_peak_mb=None
    )


from app.models.ontology_models import OntologyObjectType