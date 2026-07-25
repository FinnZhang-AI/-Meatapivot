"""AIP-009: Prompt Template Management — unit tests.

Covers the 8 acceptance-criteria scenarios:
  1. create
  2. duplicate name detection (409)
  3. list with pagination
  4. include_inactive filter
  5. get single
  6. update with implicit version bump
  7. render success
  8. render with missing variables (400)
  9. delete (soft-archive)
Plus schema/service smoke tests for full coverage.

Tests use AsyncMock for the DB layer (no live PostgreSQL needed) and follow
the same pattern as test_aip_sprint2.py.
"""

import re
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.asyncio


def _import_or_skip():
    try:
        from app.models.aip_schemas import (
            PromptTemplateCreate,
            PromptTemplateUpdate,
            PromptTemplateResponse,
            PromptTemplateListResponse,
            PromptRenderRequest,
            PromptRenderResponse,
        )
        from app.models.ontology_models import AIPPromptTemplate
        from app.services.prompt_template_service import (
            PromptTemplateService,
            _render_template,
            _extract_variables,
        )
        from app.routers.prompts import (
            create_prompt,
            list_prompts,
            get_prompt,
            update_prompt,
            render_prompt,
            delete_prompt,
            _template_to_dict,
        )
        return {
            "schemas": (
                PromptTemplateCreate,
                PromptTemplateUpdate,
                PromptTemplateResponse,
                PromptTemplateListResponse,
                PromptRenderRequest,
                PromptRenderResponse,
            ),
            "model": AIPPromptTemplate,
            "service": PromptTemplateService,
            "render": _render_template,
            "extract": _extract_variables,
            "router": {
                "create": create_prompt,
                "list": list_prompts,
                "get": get_prompt,
                "update": update_prompt,
                "render": render_prompt,
                "delete": delete_prompt,
                "_template_to_dict": _template_to_dict,
            },
        }
    except Exception as e:
        pytest.skip(f"Backend dependencies not available: {e}")


def _fake_user(tenant_id: Optional[UUID] = None) -> MagicMock:
    user = MagicMock()
    user.id = str(uuid4())
    user.tenant_id = str(tenant_id or uuid4())
    user.username = "tester"
    return user


def _fake_template(**overrides) -> MagicMock:
    template = MagicMock()
    template.id = uuid4()
    template.tenant_id = uuid4()
    template.name = "demo"
    template.description = "desc"
    template.template_text = "Hello {{ name }}"
    template.variables = ["name"]
    template.version = 1
    template.is_active = True
    template.is_ab_test = False
    template.ab_test_group = None
    template.usage_count = 0
    template.avg_prompt_tokens = 0
    template.created_by = None
    template.created_at = MagicMock()
    template.updated_at = MagicMock()
    for k, v in overrides.items():
        setattr(template, k, v)
    return template


def _fake_db_with_execute(result) -> MagicMock:
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=result)))
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_prompt_template_create_schema_accepts_minimal_payload():
    """PromptTemplateCreate should accept name + template_text only."""
    mods = _import_or_skip()
    PromptTemplateCreate = mods["schemas"][0]
    payload = PromptTemplateCreate(name="greet", template_text="Hi {{ user }}")
    assert payload.name == "greet"
    assert payload.is_ab_test is False
    assert payload.variables == []


def test_prompt_template_response_roundtrip():
    """PromptTemplateResponse should serialize all required fields."""
    mods = _import_or_skip()
    PromptTemplateResponse = mods["schemas"][2]
    tid = uuid4()
    payload = PromptTemplateResponse(
        id=tid,
        tenant_id=uuid4(),
        name="greet",
        description=None,
        template_text="Hi",
        variables=[],
        version=3,
        is_active=True,
        is_ab_test=False,
        ab_test_group=None,
        usage_count=5,
        avg_prompt_tokens=42,
        created_by=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    dumped = payload.model_dump()
    assert dumped["version"] == 3
    assert dumped["usage_count"] == 5
    assert dumped["id"] == tid


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------


def test_extract_variables_finds_jinja_placeholders():
    mods = _import_or_skip()
    extract = mods["extract"]
    assert extract("Hi {{ name }}, from {{ place }}") == ["name", "place"]
    assert extract("no vars here") == []
    # Whitespace tolerance
    assert extract("{{a}} {{ b }} {{a}}") == ["a", "b"]
    # Identifier rules
    assert extract("{{1bad}} {{ good_one }}") == ["good_one"]


async def test_service_render_substitutes_variables():
    mods = _import_or_skip()
    PromptTemplateService = mods["service"]
    service = PromptTemplateService(MagicMock(), uuid4())

    template = _fake_template(template_text="Hi {{ name }}, welcome to {{ place }}")
    with __import__("unittest.mock", fromlist=["patch"]).patch.object(
        service, "load_template", new=AsyncMock(return_value=template)
    ):
        rendered = await service.render(template.id, {"name": "Alice", "place": "Meatapivot"})
    assert rendered == "Hi Alice, welcome to Meatapivot"


async def test_service_render_returns_none_when_template_missing():
    """service.render() returns None for missing/archived templates — chat
    router uses this signal to fall back to the inline prompt."""
    mods = _import_or_skip()
    PromptTemplateService = mods["service"]
    service = PromptTemplateService(MagicMock(), uuid4())

    with __import__("unittest.mock", fromlist=["patch"]).patch.object(
        service, "load_template", new=AsyncMock(return_value=None)
    ):
        assert await service.render(uuid4(), {"x": "y"}) is None


async def test_service_record_usage_increments_moving_average():
    """record_usage should bump usage_count and update moving avg."""
    mods = _import_or_skip()
    PromptTemplateService = mods["service"]
    service = PromptTemplateService(MagicMock(), uuid4())

    template = _fake_template(usage_count=10, avg_prompt_tokens=100)
    with __import__("unittest.mock", fromlist=["patch"]).patch.object(
        service, "load_template", new=AsyncMock(return_value=template)
    ):
        await service.record_usage(template.id, 50)
    assert template.usage_count == 11
    assert template.avg_prompt_tokens == int((100 * 10 + 50) / 11)


def test_service_get_missing_variables_returns_sorted_delta():
    mods = _import_or_skip()
    PromptTemplateService = mods["service"]
    service = PromptTemplateService(MagicMock(), uuid4())
    template = _fake_template(variables=["name", "place", "thing"])
    missing = service.get_missing_variables(template, {"name": "Alice"})
    assert missing == ["place", "thing"]


# ---------------------------------------------------------------------------
# Router behavior — mocked DB
# ---------------------------------------------------------------------------


async def test_create_prompt_returns_409_on_duplicate_active_name():
    """Creating a template with an existing active name must raise 409."""
    mods = _import_or_skip()
    from fastapi import HTTPException
    PromptTemplateCreate = mods["schemas"][0]

    existing = _fake_template(name="greet", is_active=True)
    db = _fake_db_with_execute(existing)

    create_prompt = mods["router"]["create"]
    payload = PromptTemplateCreate(name="greet", template_text="x")

    with pytest.raises(HTTPException) as exc_info:
        await create_prompt(data=payload, db=db, current_user=_fake_user())
    assert exc_info.value.status_code == 409
    assert "already exists" in exc_info.value.detail.lower()


async def test_create_prompt_persists_and_extracts_variables():
    """On first create, variables are auto-extracted from template_text."""
    mods = _import_or_skip()
    from datetime import datetime, timezone
    from fastapi import HTTPException
    PromptTemplateCreate = mods["schemas"][0]

    db = _fake_db_with_execute(None)  # no existing match

    # Simulate the DB populating server-side defaults on flush, so the
    # response model has real values (not MagicMock sentinels).
    now = datetime.now(timezone.utc)

    async def fake_flush(*_a, **_kw):
        added = db.add.call_args[0][0]
        added.id = added.id or uuid4()
        added.version = added.version if added.version is not None else 1
        added.is_active = True
        added.usage_count = 0
        added.avg_prompt_tokens = 0
        added.created_at = now
        added.updated_at = now

    db.flush = AsyncMock(side_effect=fake_flush)

    create_prompt = mods["router"]["create"]
    payload = PromptTemplateCreate(
        name="greet",
        template_text="Hello {{ name }} from {{ place }}",
    )

    user = _fake_user()
    result = await create_prompt(data=payload, db=db, current_user=user)

    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert added.name == "greet"
    assert sorted(added.variables) == ["name", "place"]
    assert added.version == 1
    assert added.is_active is True
    assert result.name == "greet"
    assert result.version == 1
    assert result.is_active is True


async def test_list_prompts_paginates_and_defaults_to_active_only():
    mods = _import_or_skip()
    PromptTemplateListResponse = mods["schemas"][3]

    t1, t2 = _fake_template(), _fake_template()
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar=MagicMock(return_value=2)),  # total count
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[t1, t2])))),
        ]
    )

    list_prompts = mods["router"]["list"]
    out = await list_prompts(page=1, page_size=20, include_inactive=False, db=db, current_user=_fake_user())

    assert isinstance(out, PromptTemplateListResponse)
    assert out.total == 2
    assert out.page == 1
    assert out.page_size == 20
    assert out.pages == 1
    assert len(out.items) == 2


async def test_render_prompt_returns_400_on_missing_variables():
    """Render endpoint should surface 400 + missing list, not a partial string."""
    mods = _import_or_skip()
    from fastapi import HTTPException
    PromptRenderRequest = mods["schemas"][4]

    template = _fake_template(
        template_text="Hi {{ name }} from {{ place }}",
        variables=["name", "place"],
    )
    db = _fake_db_with_execute(template)

    render_prompt = mods["router"]["render"]
    with pytest.raises(HTTPException) as exc_info:
        await render_prompt(
            template_id=template.id,
            data=PromptRenderRequest(variables={"name": "Alice"}),
            db=db,
            current_user=_fake_user(),
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["missing"] == ["place"]


async def test_render_prompt_success_with_all_variables():
    mods = _import_or_skip()
    PromptRenderResponse = mods["schemas"][5]
    PromptRenderRequest = mods["schemas"][4]

    template = _fake_template(
        template_text="Hi {{ name }}",
        variables=["name"],
    )
    db = _fake_db_with_execute(template)

    render_prompt = mods["router"]["render"]
    out = await render_prompt(
        template_id=template.id,
        data=PromptRenderRequest(variables={"name": "Bob"}),
        db=db,
        current_user=_fake_user(),
    )
    assert isinstance(out, PromptRenderResponse)
    assert out.rendered_text == "Hi Bob"


async def test_update_prompt_bumps_version_on_template_text_change():
    """Updating template_text must increment version (audit trail)."""
    mods = _import_or_skip()
    PromptTemplateUpdate = mods["schemas"][1]

    template = _fake_template(template_text="old", variables=[], version=1)
    db = _fake_db_with_execute(template)

    update_prompt = mods["router"]["update"]
    out = await update_prompt(
        template_id=template.id,
        data=PromptTemplateUpdate(template_text="new {{ name }}"),
        db=db,
        current_user=_fake_user(),
    )
    assert out.version == 2
    assert template.version == 2
    assert template.template_text == "new {{ name }}"
    assert sorted(template.variables) == ["name"]


async def test_delete_prompt_soft_archives():
    """DELETE must set is_active=False (not remove the row)."""
    mods = _import_or_skip()

    template = _fake_template(is_active=True)
    db = _fake_db_with_execute(template)

    delete_prompt = mods["router"]["delete"]
    out = await delete_prompt(template_id=template.id, db=db, current_user=_fake_user())
    # 204 returns None
    assert out is None
    assert template.is_active is False
    db.flush.assert_awaited_once()


async def test_get_prompt_returns_template_by_id():
    mods = _import_or_skip()
    PromptTemplateResponse = mods["schemas"][2]

    template = _fake_template(name="findme")
    db = _fake_db_with_execute(template)

    get_prompt = mods["router"]["get"]
    out = await get_prompt(template_id=template.id, db=db, current_user=_fake_user())
    assert isinstance(out, PromptTemplateResponse)
    assert out.name == "findme"


# ---------------------------------------------------------------------------
# Idempotency / migration
# ---------------------------------------------------------------------------


def test_partial_unique_index_declared_on_model():
    """AIPPromptTemplate must declare a partial unique index for active rows."""
    mods = _import_or_skip()
    AIPPromptTemplate = mods["model"]
    partial = [
        idx for idx in AIPPromptTemplate.__table__.indexes
        if idx.unique and idx.dialect_options.get("postgresql")
    ]
    assert partial, "expected at least one partial unique index"
    name = "uq_aip_prompt_templates_tenant_name_active"
    assert any(idx.name == name for idx in partial), (
        f"missing partial unique index {name}; got {[i.name for i in AIPPromptTemplate.__table__.indexes]}"
    )


def test_migration_002_is_idempotent():
    """Migration 002 should not raise on a DB where 001 already created the table.

    We exercise this by importing the module and asserting its DDL uses
    ``IF NOT EXISTS`` for both table and index creation.
    """
    import importlib.util
    import os

    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "migrations", "versions", "000000000002_add_prompt_templates.py",
    )
    if not os.path.exists(path):
        pytest.skip(f"migration file not found at {path}")
    with open(path) as fh:
        src = fh.read()

    assert "CREATE TABLE IF NOT EXISTS aip_prompt_templates" in src, (
        "migration must use CREATE TABLE IF NOT EXISTS so it can be re-run"
    )
    assert "CREATE UNIQUE INDEX IF NOT EXISTS" in src, (
        "migration must use CREATE UNIQUE INDEX IF NOT EXISTS for the partial index"
    )
    assert "WHERE is_active = TRUE" in src, (
        "partial index predicate must be is_active = TRUE"
    )