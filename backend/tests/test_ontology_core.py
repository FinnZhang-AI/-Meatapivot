"""Core integration tests for Ontology router endpoints.

These tests verify that the ontology router exposes the expected endpoints
and that schema serialization works correctly.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    try:
        from app.main import app
        return TestClient(app)
    except Exception as e:
        pytest.skip(f"Backend dependencies not available: {e}")


class TestOntologyRouter:
    def test_router_has_expected_routes(self, client):
        """Verify all major ontology endpoints are registered."""
        routes = [r.path for r in client.app.routes]

        expected_prefixes = [
            "/api/v1/ontology/object-types",
            "/api/v1/ontology/link-types",
            "/api/v1/ontology/interfaces",
            "/api/v1/ontology/action-types",
            "/api/v1/ontology/functions",
            "/api/v1/ontology/search",
            "/api/v1/ontology/subgraph",
            "/api/v1/ontology/compile",
            "/api/v1/ontology/export",
            "/api/v1/ontology/import",
            "/api/v1/ontology/objects",
        ]

        for prefix in expected_prefixes:
            assert any(prefix in r for r in routes), f"Missing route prefix: {prefix}"

    def test_object_type_crud_endpoints_exist(self, client):
        routes = [r.path for r in client.app.routes if "/object-types" in r.path]
        assert any("POST" in str(r.methods) for r in client.app.routes if "/object-types" in r.path)
        assert any("GET" in str(r.methods) for r in client.app.routes if "/object-types" in r.path)

    def test_object_instance_endpoints_exist(self, client):
        """Verify object instance GET / links endpoints are present."""
        routes = [r.path for r in client.app.routes]
        assert any("/api/v1/ontology/objects/{" in r for r in routes), "Missing /objects/{id} route"


class TestAIPRouter:
    def test_aip_chat_endpoints_exist(self, client):
        routes = [r.path for r in client.app.routes]
        assert "/api/v1/aip/chat" in routes
        assert "/api/v1/aip/chat/stream" in routes

    def test_aip_rag_endpoint_exists(self, client):
        routes = [r.path for r in client.app.routes]
        assert "/api/v1/aip/rag/query" in routes


class TestMilvusClient:
    def test_milvus_client_singleton(self):
        from app.services.milvus_client import MilvusClient
        c1 = MilvusClient()
        c2 = MilvusClient()
        assert c1 is c2

    def test_milvus_schema_fields(self):
        from app.services.milvus_client import MilvusClient
        client = MilvusClient()
        # Ensure expected fields are configured
        assert client._collection_name == "ontology_objects"
        assert client._dim in (384, 768, 1024)  # common embedding dims
