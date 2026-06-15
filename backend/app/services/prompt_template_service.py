"""Prompt Template Service - load templates and track usage statistics."""
import logging
import re
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ontology_models import AIPPromptTemplate

logger = logging.getLogger(__name__)


def _extract_variables(template_text: str) -> list[str]:
    """Extract Jinja2-style {{ variable }} placeholders from template."""
    return sorted(set(re.findall(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}", template_text)))


def _render_template(template_text: str, variables: Dict[str, Any]) -> str:
    """Simple Jinja2-style variable substitution."""
    result = template_text
    for key, value in variables.items():
        result = result.replace(f"{{{{ {key} }}}}", str(value)).replace(f"{{{{{key}}}}}", str(value))
    return result


class PromptTemplateService:
    """Service for loading and rendering prompt templates with usage tracking."""

    def __init__(self, db: AsyncSession, tenant_id: Optional[UUID]):
        self.db = db
        self.tenant_id = tenant_id

    async def load_template(self, template_id: UUID) -> Optional[AIPPromptTemplate]:
        """Load a prompt template by ID and tenant."""
        if not self.tenant_id:
            return None
        result = await self.db.execute(
            select(AIPPromptTemplate).where(
                AIPPromptTemplate.id == template_id,
                AIPPromptTemplate.tenant_id == self.tenant_id,
                AIPPromptTemplate.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def render(
        self,
        template_id: UUID,
        variables: Dict[str, Any],
    ) -> Optional[str]:
        """Render a prompt template with variables."""
        template = await self.load_template(template_id)
        if not template:
            return None
        return _render_template(template.template_text, variables)

    async def record_usage(self, template_id: UUID, prompt_tokens: int) -> None:
        """Update template usage statistics."""
        template = await self.load_template(template_id)
        if not template:
            return
        try:
            new_count = template.usage_count + 1
            # Incremental moving average
            template.avg_prompt_tokens = int(
                (template.avg_prompt_tokens * template.usage_count + prompt_tokens) / new_count
            )
            template.usage_count = new_count
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Failed to update prompt template usage: {e}")

    def get_missing_variables(self, template: AIPPromptTemplate, variables: Dict[str, Any]) -> list[str]:
        """Return list of template variables not provided in variables dict."""
        provided = set(variables.keys())
        required = set(template.variables or [])
        return sorted(required - provided)
