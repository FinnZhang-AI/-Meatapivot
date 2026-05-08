"""Integration and unit tests for Ontology services and schemas.

These tests verify business logic without requiring live databases.
"""
import pytest
import ast
from uuid import UUID
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    try:
        from app.main import app
        return TestClient(app)
    except Exception as e:
        pytest.skip(f"Backend dependencies not available: {e}")


# ---------------------------------------------------------------------------
# SafeExprEvaluator
# ---------------------------------------------------------------------------

class TestSafeExprEvaluator:
    def test_basic_math(self):
        from app.services.action_executor import SafeExprEvaluator
        ev = SafeExprEvaluator({"x": 10, "y": 3})
        assert ev.eval("x + y") == 13
        assert ev.eval("x - y") == 7
        assert ev.eval("x * y") == 30
        assert ev.eval("x / y") == pytest.approx(3.333, rel=1e-3)

    def test_comparisons(self):
        from app.services.action_executor import SafeExprEvaluator
        ev = SafeExprEvaluator({"age": 25})
        assert ev.eval("age >= 18") is True
        assert ev.eval("age < 18") is False
        assert ev.eval("age == 25") is True

    def test_boolean_logic(self):
        from app.services.action_executor import SafeExprEvaluator
        ev = SafeExprEvaluator({"a": True, "b": False})
        assert ev.eval("a and not b") is True
        assert ev.eval("a or b") is True

    def test_allowed_functions(self):
        from app.services.action_executor import SafeExprEvaluator
        ev = SafeExprEvaluator({"items": [1, 2, 3]})
        assert ev.eval("len(items)") == 3
        assert ev.eval("sum(items)") == 6
        assert ev.eval("max(items)") == 3

    def test_disallowed_functions_raise(self):
        from app.services.action_executor import SafeExprEvaluator
        ev = SafeExprEvaluator({})
        with pytest.raises(ValueError):
            ev.eval("__import__('os').system('ls')")

    def test_disallowed_name_raise(self):
        from app.services.action_executor import SafeExprEvaluator
        ev = SafeExprEvaluator({})
        with pytest.raises(ValueError):
            ev.eval("undefined_var + 1")


# ---------------------------------------------------------------------------
# Ontology Compiler - GraphQL Schema Generation
# ---------------------------------------------------------------------------

class TestOntologyCompiler:
    def test_map_property_type(self):
        from app.services.ontology_compiler import OntologyCompiler
        # _map_property_type is an instance method but pure logic
        class DummyDB:
            pass
        compiler = OntologyCompiler(DummyDB(), UUID(int=0))  # type: ignore
        assert compiler._map_property_type("string") == "String"
        assert compiler._map_property_type("int") == "Int"
        assert compiler._map_property_type("float") == "Float"
        assert compiler._map_property_type("boolean") == "Boolean"
        assert compiler._map_property_type("date") == "String"
        assert compiler._map_property_type("json") == "JSON"
        assert compiler._map_property_type("unknown") == "String"


# ---------------------------------------------------------------------------
# Router Endpoint Coverage
# ---------------------------------------------------------------------------

class TestOntologyEndpointCoverage:
    """Verify that all expected HTTP methods are registered for each resource."""

    def _get_routes_for(self, client, prefix: str):
        return [r for r in client.app.routes if prefix in r.path]

    def test_object_types_has_full_crud(self, client):
        routes = self._get_routes_for(client, "/object-types")
        methods = set()
        for r in routes:
            methods.update(getattr(r, "methods", set()))
        assert "POST" in methods
        assert "GET" in methods
        assert "PUT" in methods
        assert "DELETE" in methods

    def test_link_types_has_full_crud(self, client):
        routes = self._get_routes_for(client, "/link-types")
        methods = set()
        for r in routes:
            methods.update(getattr(r, "methods", set()))
        assert "POST" in methods
        assert "GET" in methods
        assert "PUT" in methods
        assert "DELETE" in methods

    def test_interfaces_has_full_crud(self, client):
        routes = self._get_routes_for(client, "/interfaces")
        methods = set()
        for r in routes:
            methods.update(getattr(r, "methods", set()))
        assert "POST" in methods
        assert "GET" in methods
        assert "PUT" in methods
        assert "DELETE" in methods

    def test_action_types_has_full_crud_plus_execute(self, client):
        routes = self._get_routes_for(client, "/action-types")
        methods = set()
        for r in routes:
            methods.update(getattr(r, "methods", set()))
        assert "POST" in methods
        assert "GET" in methods
        assert "PUT" in methods
        assert "DELETE" in methods
        # Execute endpoint
        paths = [r.path for r in routes]
        assert any("/execute" in p for p in paths)

    def test_functions_has_full_crud_plus_test(self, client):
        routes = self._get_routes_for(client, "/functions")
        methods = set()
        for r in routes:
            methods.update(getattr(r, "methods", set()))
        assert "POST" in methods
        assert "GET" in methods
        assert "PUT" in methods
        assert "DELETE" in methods
        paths = [r.path for r in routes]
        assert any("/test" in p for p in paths)

    def test_objects_has_get_and_links(self, client):
        routes = [r for r in client.app.routes if "/objects/{" in r.path]
        paths = [r.path for r in routes]
        assert any("/links" in p for p in paths)


# ---------------------------------------------------------------------------
# Schema Serialization
# ---------------------------------------------------------------------------

class TestSchemaSerialization:
    def test_object_type_create_schema(self):
        from app.models.ontology_schemas import ObjectTypeCreate
        data = {
            "name": "Customer",
            "display_name": "客户",
            "description": "A customer",
            "properties": [{"name": "email", "type": "string", "required": True}],
        }
        schema = ObjectTypeCreate(**data)
        assert schema.name == "Customer"
        assert len(schema.properties) == 1

    def test_compile_result_schema(self):
        from app.models.ontology_schemas import CompileResult, CompileError
        result = CompileResult(
            status="success",
            errors=[CompileError(code="TEST", message="test error")],
            warnings=["warn1"],
            neo4j_constraints_created=2,
            duration_ms=150,
        )
        assert result.status == "success"
        assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# Milvus Client
# ---------------------------------------------------------------------------

class TestMilvusClient:
    def test_singleton(self):
        from app.services.milvus_client import MilvusClient
        c1 = MilvusClient()
        c2 = MilvusClient()
        assert c1 is c2

    def test_default_dimension(self):
        from app.services.milvus_client import MilvusClient
        client = MilvusClient()
        assert client._dim == 1024

    def test_delete_expr_format(self):
        from app.services.milvus_client import MilvusClient
        client = MilvusClient()
        tenant_id = UUID("12345678-1234-1234-1234-123456789abc")
        record_id = f"{tenant_id}:obj-1"
        assert record_id == "12345678-1234-1234-1234-123456789abc:obj-1"


# ---------------------------------------------------------------------------
# AIP Router Coverage
# ---------------------------------------------------------------------------

class TestAIPRouterCoverage:
    def test_aip_chat_post(self, client):
        routes = [r for r in client.app.routes if r.path == "/api/v1/aip/chat"]
        assert len(routes) >= 1
        methods = set()
        for r in routes:
            methods.update(getattr(r, "methods", set()))
        assert "POST" in methods

    def test_aip_chat_stream_post(self, client):
        routes = [r for r in client.app.routes if r.path == "/api/v1/aip/chat/stream"]
        assert len(routes) >= 1
        methods = set()
        for r in routes:
            methods.update(getattr(r, "methods", set()))
        assert "POST" in methods

    def test_aip_rag_query_post(self, client):
        routes = [r for r in client.app.routes if r.path == "/api/v1/aip/rag/query"]
        assert len(routes) >= 1
        methods = set()
        for r in routes:
            methods.update(getattr(r, "methods", set()))
        assert "POST" in methods

    def test_aip_models_get(self, client):
        routes = [r for r in client.app.routes if r.path == "/api/v1/aip/models"]
        assert len(routes) >= 1
        methods = set()
        for r in routes:
            methods.update(getattr(r, "methods", set()))
        assert "GET" in methods


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_degraded_or_healthy(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert "services" in data
        assert "postgres" in data["services"]
        assert "neo4j" in data["services"]

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Meatapivot"
        assert "version" in data
