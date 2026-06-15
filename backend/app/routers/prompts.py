"""Prompt Template Management API Router"""
import logging
import math
import re
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aip_schemas import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
    PromptTemplateListResponse,
    PromptRenderRequest,
    PromptRenderResponse,
)
from app.models.ontology_models import AIPPromptTemplate
from app.routers.auth import get_current_user, UserResponse
from app.services.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AIP - Prompts"])


def _extract_variables(template_text: str) -> list[str]:
    """Extract Jinja2-style {{ variable }} placeholders from template."""
    return sorted(set(re.findall(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}", template_text)))


async def _get_tenant_id(current_user: UserResponse) -> UUID:
    return UUID(current_user.tenant_id)


@router.post("", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    data: PromptTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Create a new prompt template."""
    tenant_id = await _get_tenant_id(current_user)

    existing = await db.execute(
        select(AIPPromptTemplate).where(
            AIPPromptTemplate.tenant_id == tenant_id,
            AIPPromptTemplate.name == data.name,
            AIPPromptTemplate.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Active prompt template '{data.name}' already exists",
        )

    variables = data.variables or _extract_variables(data.template_text)

    template = AIPPromptTemplate(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        template_text=data.template_text,
        variables=variables,
        is_ab_test=data.is_ab_test,
        ab_test_group=data.ab_test_group,
        created_by=UUID(current_user.id) if current_user.id else None,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return PromptTemplateResponse(**_template_to_dict(template))


@router.get("", response_model=PromptTemplateListResponse)
async def list_prompts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """List prompt templates with pagination."""
    tenant_id = await _get_tenant_id(current_user)

    query = select(AIPPromptTemplate).where(AIPPromptTemplate.tenant_id == tenant_id)
    if not include_inactive:
        query = query.where(AIPPromptTemplate.is_active == True)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(AIPPromptTemplate.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    pages = math.ceil(total / page_size) if total > 0 else 1
    return PromptTemplateListResponse(
        items=[PromptTemplateResponse(**_template_to_dict(t)) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{template_id}", response_model=PromptTemplateResponse)
async def get_prompt(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a single prompt template."""
    tenant_id = await _get_tenant_id(current_user)
    template = await _get_template(db, tenant_id, template_id)
    return PromptTemplateResponse(**_template_to_dict(template))


@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt(
    template_id: UUID,
    data: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Update a prompt template. Creates a new version implicitly."""
    tenant_id = await _get_tenant_id(current_user)
    template = await _get_template(db, tenant_id, template_id)

    if data.description is not None:
        template.description = data.description
    if data.template_text is not None:
        template.template_text = data.template_text
        template.variables = data.variables or _extract_variables(data.template_text)
        template.version += 1
    if data.variables is not None and data.template_text is None:
        template.variables = data.variables
    if data.is_active is not None:
        template.is_active = data.is_active
    if data.is_ab_test is not None:
        template.is_ab_test = data.is_ab_test
    if data.ab_test_group is not None:
        template.ab_test_group = data.ab_test_group

    await db.flush()
    await db.refresh(template)
    return PromptTemplateResponse(**_template_to_dict(template))


@router.post("/{template_id}/render", response_model=PromptRenderResponse)
async def render_prompt(
    template_id: UUID,
    data: PromptRenderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Render a prompt template with provided variables."""
    tenant_id = await _get_tenant_id(current_user)
    template = await _get_template(db, tenant_id, template_id)

    try:
        rendered = _render_template(template.template_text, data.variables)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing variable: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Template render error: {e}")

    return PromptRenderResponse(rendered_text=rendered)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Soft-delete a prompt template (archive)."""
    tenant_id = await _get_tenant_id(current_user)
    template = await _get_template(db, tenant_id, template_id)
    template.is_active = False
    await db.flush()


async def _get_template(db: AsyncSession, tenant_id: UUID, template_id: UUID) -> AIPPromptTemplate:
    result = await db.execute(
        select(AIPPromptTemplate).where(
            AIPPromptTemplate.id == template_id,
            AIPPromptTemplate.tenant_id == tenant_id,
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    return template


def _template_to_dict(template: AIPPromptTemplate) -> dict:
    return {
        "id": template.id,
        "tenant_id": template.tenant_id,
        "name": template.name,
        "description": template.description,
        "template_text": template.template_text,
        "variables": template.variables or [],
        "version": template.version,
        "is_active": template.is_active,
        "is_ab_test": template.is_ab_test,
        "ab_test_group": template.ab_test_group,
        "usage_count": template.usage_count,
        "avg_prompt_tokens": template.avg_prompt_tokens,
        "created_by": template.created_by,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def _render_template(template_text: str, variables: dict) -> str:
    """Simple Jinja2-style variable substitution."""
    result = template_text
    for key, value in variables.items():
        result = result.replace(f"{{{{ {key} }}}}", str(value)).replace(f"{{{{{key}}}}}", str(value))
    return result
