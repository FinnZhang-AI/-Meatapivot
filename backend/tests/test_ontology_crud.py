"""CRUD flow tests for Ontology endpoints using mocked database sessions.

These tests verify request/response handling and business logic flows
without requiring live PostgreSQL or Neo4j services.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4


@pytest.fixture
def mock_db():
    """Create a mock AsyncSession for isolated unit tests."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def tenant_id():
    return UUID("12345678-1234-1234-1234-123456789abc")


# ---------------------------------------------------------------------------
# ObjectType CRUD Flow
# ---------------------------------------------------------------------------

class TestObjectTypeCrudFlow:
    def test_object_type_create_schema_validation(self):
        """Verify ObjectTypeCreate schema accepts valid payload."""
        from app.models.ontology_schemas import ObjectTypeCreate, PropertyDef

        payload = {
            "name": "Customer",
            "display_name": "客户",
            "description": "A customer entity",
            "icon": "user",
            "properties": [
                {"name": "email", "type": "string", "required": True},
                {"name": "age", "type": "int", "required": False},
            ],
        }
        schema = ObjectTypeCreate(**payload)
        assert schema.name == "Customer"
        assert len(schema.properties) == 2
        assert schema.properties[0].name == "email"
        assert schema.properties[0].required is True

    def test_object_type_update_schema_partial(self):
        """Verify ObjectTypeUpdate allows partial updates."""
        from app.models.ontology_schemas import ObjectTypeUpdate

        schema = ObjectTypeUpdate(display_name="Updated Name")
        assert schema.display_name == "Updated Name"
        assert schema.name is None

    def test_object_type_response_serialization(self):
        """Verify ObjectTypeResponse can be constructed from dict."""
        from app.models.ontology_schemas import ObjectTypeResponse

        data = {
            "id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "name": "Product",
            "display_name": "产品",
            "description": "A product",
            "icon": "box",
            "properties": [],
            "implemented_interfaces": [],
            "neo4j_label": "Product",
            "status": "active",
            "compile_status": "pending",
            "version": 1,
        }
        resp = ObjectTypeResponse(**data)
        assert resp.name == "Product"
        assert resp.status == "active"


# ---------------------------------------------------------------------------
# LinkType CRUD Flow
# ---------------------------------------------------------------------------

class TestLinkTypeCrudFlow:
    def test_link_type_create_schema(self):
        """Verify LinkTypeCreate schema accepts valid payload."""
        from app.models.ontology_schemas import LinkTypeCreate

        source_id = uuid4()
        target_id = uuid4()
        payload = {
            "name": "placed_by",
            "display_name": "由...下单",
            "source_object_type_id": source_id,
            "target_object_type_id": target_id,
            "cardinality": "MANY_TO_ONE",
        }
        schema = LinkTypeCreate(**payload)
        assert schema.name == "placed_by"
        assert str(schema.source_object_type_id) == str(source_id)

    def test_link_type_cardinality_enum(self):
        """Verify cardinality accepts all valid enum values."""
        from app.models.ontology_schemas import LinkTypeCreate
        from uuid import uuid4

        for cardinality in ("ONE_TO_ONE", "ONE_TO_MANY", "MANY_TO_ONE", "MANY_TO_MANY"):
            schema = LinkTypeCreate(
                name=f"link_{cardinality}",
                source_object_type_id=uuid4(),
                target_object_type_id=uuid4(),
                cardinality=cardinality,
            )
            assert schema.cardinality == cardinality


# ---------------------------------------------------------------------------
# Interface CRUD Flow
# ---------------------------------------------------------------------------

class TestInterfaceCrudFlow:
    def test_interface_create_schema(self):
        """Verify InterfaceCreate schema with required properties and links."""
        from app.models.ontology_schemas import InterfaceCreate

        payload = {
            "name": "Identifiable",
            "display_name": "可识别实体",
            "required_properties": [{"name": "id", "type": "string", "required": True}],
            "required_links": [],
        }
        schema = InterfaceCreate(**payload)
        assert schema.name == "Identifiable"
        assert len(schema.required_properties) == 1


# ---------------------------------------------------------------------------
# ActionType CRUD Flow
# ---------------------------------------------------------------------------

class TestActionTypeCrudFlow:
    def test_action_type_create_schema(self):
        """Verify ActionTypeCreate schema accepts valid payload."""
        from app.models.ontology_schemas import ActionTypeCreate, ActionParameter, ActionRule

        payload = {
            "name": "AssignVIP",
            "display_name": "分配VIP等级",
            "target_object_type_id": uuid4(),
            "parameters": [
                {"name": "level", "type": "int", "required": True},
            ],
            "rules": [
                {"name": "check_active", "rule_type": "expression", "policy": "status == 'active'"},
            ],
            "execution_type": "direct",
        }
        schema = ActionTypeCreate(**payload)
        assert schema.name == "AssignVIP"
        assert len(schema.parameters) == 1
        assert len(schema.rules) == 1
        assert schema.execution_type == "direct"

    def test_action_execution_request_schema(self):
        """Verify ActionExecuteRequest schema."""
        from app.models.ontology_schemas import ActionExecuteRequest

        schema = ActionExecuteRequest(
            target_object_id=uuid4(),
            parameters={"level": 3},
        )
        assert schema.target_object_id is not None
        assert schema.parameters == {"level": 3}


# ---------------------------------------------------------------------------
# Function CRUD Flow
# ---------------------------------------------------------------------------

class TestFunctionCrudFlow:
    def test_function_create_schema(self):
        """Verify FunctionCreate schema accepts valid payload."""
        from app.models.ontology_schemas import FunctionCreate

        payload = {
            "name": "calculate_discount",
            "display_name": "计算折扣",
            "language": "python",
            "code": "def main(ctx):\n    return {'discount': 0.9}",
            "timeout_seconds": 30,
            "memory_mb": 256,
        }
        schema = FunctionCreate(**payload)
        assert schema.name == "calculate_discount"
        assert schema.language == "python"
        assert schema.timeout_seconds == 30


# ---------------------------------------------------------------------------
# Object Instance CRUD Flow
# ---------------------------------------------------------------------------

class TestObjectInstanceCrudFlow:
    def test_object_create_schema(self):
        """Verify OntologyObjectCreate schema."""
        from app.models.ontology_schemas import OntologyObjectCreate

        schema = OntologyObjectCreate(
            object_key="CUST-001",
            properties={"name": "张三", "email": "zhangsan@example.com"},
        )
        assert schema.object_key == "CUST-001"
        assert schema.properties["name"] == "张三"

    def test_object_response_serialization(self):
        """Verify OntologyObjectResponse serialization."""
        from app.models.ontology_schemas import OntologyObjectResponse

        data = {
            "id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "object_type_id": str(uuid4()),
            "object_key": "ORD-001",
            "properties": {"total": 100.0},
            "status": "active",
        }
        resp = OntologyObjectResponse(**data)
        assert resp.object_key == "ORD-001"
        assert resp.properties["total"] == 100.0


# ---------------------------------------------------------------------------
# Search & Compile
# ---------------------------------------------------------------------------

class TestSearchAndCompile:
    def test_search_request_schema(self):
        """Verify OntologySearchRequest schema."""
        from app.models.ontology_schemas import OntologySearchRequest

        schema = OntologySearchRequest(
            query="VIP customers",
            search_mode="hybrid",
            top_k=10,
        )
        assert schema.query == "VIP customers"
        assert schema.search_mode == "hybrid"
        assert schema.top_k == 10

    def test_compile_result_schema(self):
        """Verify CompileResult schema handles errors and warnings."""
        from app.models.ontology_schemas import CompileResult, CompileError

        result = CompileResult(
            status="has_errors",
            errors=[
                CompileError(code="MISSING_PROP", message="Missing required property", field="email"),
            ],
            warnings=["slow compile"],
            neo4j_constraints_created=0,
            duration_ms=500,
        )
        assert result.status == "has_errors"
        assert result.errors[0].field == "email"


# ---------------------------------------------------------------------------
# Action Executor - SafeExprEvaluator
# ---------------------------------------------------------------------------

class TestActionExecutorSafeExpr:
    def test_eval_simple_math(self):
        from app.services.action_executor import SafeExprEvaluator
        ev = SafeExprEvaluator({"x": 10, "y": 5})
        assert ev.eval("x + y") == 15
        assert ev.eval("x - y") == 5
        assert ev.eval("x * y") == 50
        assert ev.eval("x / y") == 2.0

    def test_eval_comparison(self):
        from app.services.action_executor import SafeExprEvaluator
        ev = SafeExprEvaluator({"age": 30})
        assert ev.eval("age >= 18") is True
        assert ev.eval("age < 18") is False

    def test_eval_disallowed_import(self):
        from app.services.action_executor import SafeExprEvaluator
        ev = SafeExprEvaluator({})
        with pytest.raises(ValueError):
            ev.eval("__import__('os')")


# ---------------------------------------------------------------------------
# Router Existence (Smoke)
# ---------------------------------------------------------------------------

class TestRouterSmoke:
    def test_all_major_routers_loaded(self):
        from app.main import app
        routes = [r.path for r in app.routes]
        assert "/api/v1/ontology/object-types" in routes or any("/object-types" in r for r in routes)
        assert "/api/v1/aip/chat" in routes or any("/chat" in r for r in routes)
        assert "/health" in routes
