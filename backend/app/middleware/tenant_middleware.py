"""Tenant isolation middleware.

P1-11/S4-4: Injects request.state.tenant_id from JWT token or X-Tenant-ID header.
Ensures all downstream handlers have a tenant context.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import Request, Response
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000000")


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts tenant_id from JWT or header and injects into request.state.
    
    Priority:
        1. Decode tenant_id from Authorization Bearer JWT payload
        2. Fallback to X-Tenant-ID header
        3. Fallback to default tenant UUID
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        tenant_id = self._extract_tenant_id(request)
        request.state.tenant_id = tenant_id
        
        # Also set a contextvar or log for tracing
        logger.debug(f"Tenant resolved: {tenant_id} for {request.method} {request.url.path}")
        
        response = await call_next(request)
        
        # Optional: add tenant header to response for debugging
        response.headers["X-Tenant-ID"] = str(tenant_id)
        return response

    def _extract_tenant_id(self, request: Request) -> UUID:
        """Extract tenant_id from request."""
        # Priority 1: JWT token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            jwt_tenant = self._decode_tenant_from_jwt(token)
            if jwt_tenant:
                return jwt_tenant
        
        # Priority 2: X-Tenant-ID header
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            try:
                return UUID(tenant_header)
            except ValueError:
                logger.warning(f"Invalid X-Tenant-ID header: {tenant_header}")
        
        # Priority 3: default
        return DEFAULT_TENANT_ID

    def _decode_tenant_from_jwt(self, token: str) -> Optional[UUID]:
        """Decode tenant_id from JWT payload without DB validation."""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False},  # Allow expired tokens for tenant extraction
            )
            tenant_id_str = payload.get("tenant_id")
            if tenant_id_str:
                return UUID(tenant_id_str)
        except JWTError:
            # Token invalid - will be caught by auth dependencies later
            pass
        except (ValueError, TypeError):
            logger.warning(f"Invalid tenant_id in JWT payload")
        return None
