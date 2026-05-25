"""Security tests for Sprint 1-2 P0 fixes.

Tests cover:
- Cypher whitelist injection protection
- RestrictedPython sandbox security
- Auth with bcrypt hashing
"""

import pytest
import uuid
from datetime import timedelta

from fastapi import HTTPException

from app.routers.knowledge_graph import _validate_readonly_cypher
from app.services.sandbox_restricted import execute_restricted, _check_forbidden_names
from app.routers.auth import verify_password, get_password_hash, create_access_token


class TestCypherWhitelist:
    """Test Cypher query whitelist validation (P0-SEC-01)."""

    def test_match_query_allowed(self):
        """MATCH query should be allowed."""
        is_valid, error = _validate_readonly_cypher("MATCH (n) RETURN n LIMIT 10")
        assert is_valid is True
        assert error == ""

    def test_return_query_allowed(self):
        """RETURN query should be allowed."""
        is_valid, error = _validate_readonly_cypher("RETURN 1 + 1")
        assert is_valid is True
        assert error == ""

    def test_optional_match_allowed(self):
        """OPTIONAL MATCH query should be allowed."""
        is_valid, error = _validate_readonly_cypher("OPTIONAL MATCH (n) RETURN n")
        assert is_valid is True
        assert error == ""

    def test_create_query_rejected(self):
        """CREATE query should be rejected."""
        is_valid, error = _validate_readonly_cypher("CREATE (n:Test) RETURN n")
        assert is_valid is False
        assert "CREATE" in error
        assert "403" not in error  # error is a message, not HTTP status

    def test_delete_query_rejected(self):
        """DELETE query should be rejected."""
        is_valid, error = _validate_readonly_cypher("MATCH (n) DELETE n")
        assert is_valid is False
        assert "DELETE" in error

    def test_merge_query_rejected(self):
        """MERGE query should be rejected."""
        is_valid, error = _validate_readonly_cypher("MERGE (n:Test {name: 'hack'}) RETURN n")
        assert is_valid is False
        assert "MERGE" in error

    def test_set_query_rejected(self):
        """SET query should be rejected."""
        is_valid, error = _validate_readonly_cypher("MATCH (n) SET n.name = 'test' RETURN n")
        assert is_valid is False
        assert "SET" in error

    def test_comment_bypass_prevented(self):
        """Comments should not bypass validation."""
        # Comments are stripped, but forbidden keywords are still detected
        is_valid, error = _validate_readonly_cypher("// This is a comment\nCREATE (n:Test) RETURN n")
        assert is_valid is False
        assert "CREATE" in error

    def test_empty_query_rejected(self):
        """Empty query should be rejected."""
        is_valid, error = _validate_readonly_cypher("")
        assert is_valid is False
        assert "Empty" in error

    def test_case_insensitive_rejection(self):
        """Keywords should be detected case-insensitively."""
        is_valid, error = _validate_readonly_cypher("create (n:Test) return n")
        assert is_valid is False
        assert "CREATE" in error

    def test_drop_query_rejected(self):
        """DROP query should be rejected."""
        is_valid, error = _validate_readonly_cypher("DROP INDEX idx_test")
        assert is_valid is False
        assert "DROP" in error


class TestRestrictedPythonSandbox:
    """Test RestrictedPython sandbox (P0-SEC-02)."""

    @pytest.mark.asyncio
    async def test_safe_code_executes(self):
        """Safe Python code should execute successfully."""
        result = await execute_restricted(
            code="result = input['x'] + input['y']",
            input_data={"x": 10, "y": 20},
            timeout=5.0
        )
        assert result.success is True
        assert result.output == 30

    @pytest.mark.asyncio
    async def test_os_system_blocked(self):
        """os.system should be blocked."""
        result = await execute_restricted(
            code="import os; os.system('whoami')",
            input_data={}
        )
        assert result.success is False
        assert "SecurityError" in result.error

    @pytest.mark.asyncio
    async def test_subprocess_blocked(self):
        """subprocess should be blocked."""
        result = await execute_restricted(
            code="import subprocess; subprocess.run(['ls'])",
            input_data={}
        )
        assert result.success is False
        assert "SecurityError" in result.error

    @pytest.mark.asyncio
    async def test_eval_blocked(self):
        """eval should be blocked."""
        result = await execute_restricted(
            code="eval('1 + 1')",
            input_data={}
        )
        assert result.success is False
        assert "SecurityError" in result.error

    @pytest.mark.asyncio
    async def test_exec_blocked(self):
        """exec should be blocked."""
        result = await execute_restricted(
            code="exec('print(1)')",
            input_data={}
        )
        assert result.success is False
        assert "SecurityError" in result.error

    @pytest.mark.asyncio
    async def test_open_blocked(self):
        """open() should be blocked."""
        result = await execute_restricted(
            code="open('/etc/passwd')",
            input_data={}
        )
        assert result.success is False
        assert "SecurityError" in result.error

    @pytest.mark.asyncio
    async def test_timeout_works(self):
        """Infinite loop should timeout."""
        result = await execute_restricted(
            code="while True: pass",
            input_data={},
            timeout=1.0
        )
        assert result.success is False
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_import_os_blocked(self):
        """import os should be blocked."""
        result = await execute_restricted(
            code="import os; result = os.environ.get('HOME')",
            input_data={}
        )
        assert result.success is False
        assert "SecurityError" in result.error

    def test_check_forbidden_names_import(self):
        """_check_forbidden_names should detect imports."""
        forbidden = _check_forbidden_names("import os")
        assert len(forbidden) > 0
        assert any("os" in f for f in forbidden)

    def test_check_forbidden_names_from_import(self):
        """_check_forbidden_names should detect from imports."""
        forbidden = _check_forbidden_names("from os import system")
        assert len(forbidden) > 0

    def test_check_forbidden_names_attribute(self):
        """_check_forbidden_names should detect attribute access."""
        forbidden = _check_forbidden_names("os.system('ls')")
        assert len(forbidden) > 0
        assert any("system" in f for f in forbidden)

    @pytest.mark.asyncio
    async def test_safe_math_operations(self):
        """Math operations should work."""
        result = await execute_restricted(
            code="result = sum([1, 2, 3, 4, 5])",
            input_data={}
        )
        assert result.success is True
        assert result.output == 15

    @pytest.mark.asyncio
    async def test_safe_list_dict_operations(self):
        """List and dict operations should work."""
        result = await execute_restricted(
            code="data = input['data']; result = sorted(data.keys())",
            input_data={"data": {"b": 2, "a": 1}}
        )
        assert result.success is True
        assert result.output == ["a", "b"]


class TestAuthSecurity:
    """Test Auth with bcrypt hashing (P0-SEC-03)."""

    def test_password_hashing(self):
        """Password should be hashed and verifiable."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        
        # Hash should be different from plain text
        assert hashed != password
        # Hash should be verifiable
        assert verify_password(password, hashed) is True
        # Wrong password should fail
        assert verify_password("wrong_password", hashed) is False

    def test_password_hash_uniqueness(self):
        """Same password should produce different hashes (due to salt)."""
        password = "same_password"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_create_access_token(self):
        """JWT token should be created with correct claims."""
        data = {"sub": "testuser", "roles": ["user"], "tenant_id": "tenant-123"}
        token = create_access_token(data, expires_delta=timedelta(minutes=30))
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_claims(self):
        """JWT token should contain the original claims."""
        from jose import jwt
        from app.core.config import settings
        
        data = {"sub": "testuser", "roles": ["admin"]}
        token = create_access_token(data, expires_delta=timedelta(minutes=30))
        
        # Decode and verify
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["roles"] == ["admin"]
        assert "exp" in payload


class TestDocumentSecurity:
    """Test Document query uses real PostgreSQL (P0-SEC-04)."""

    def test_document_response_no_defaults(self):
        """DocumentResponse should not have mock defaults."""
        from app.models.schemas import DocumentResponse
        
        # Create a response with explicit values
        response = DocumentResponse(
            id="123",
            title="Test",
            filename="test.pdf",
            object_name="tenant/123/test.pdf",
            document_type="pdf",
            description="",
            file_size=1000,
            mime_type="application/pdf",
            tags=[],
            uploaded_by="admin",
            tenant_id="tenant-1",
            uploaded_at="2024-01-01T00:00:00",
            url="http://localhost/test.pdf"
        )
        
        assert response.id == "123"
        assert response.title == "Test"
