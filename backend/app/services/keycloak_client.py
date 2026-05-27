"""Keycloak OIDC integration for Meatapivot.

S5-4: SSO login flow with python-keycloak.
Falls back to local JWT auth if Keycloak is unavailable.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from keycloak import KeycloakOpenID
from app.core.config import settings

logger = logging.getLogger(__name__)


class KeycloakClient:
    """Keycloak OIDC client wrapper."""
    
    def __init__(self):
        self._client: Optional[KeycloakOpenID] = None
        self.enabled = bool(
            settings.KEYCLOAK_SERVER_URL and
            settings.KEYCLOAK_REALM and
            settings.KEYCLOAK_CLIENT_ID
        )
        
        if self.enabled:
            try:
                self._client = KeycloakOpenID(
                    server_url=settings.KEYCLOAK_SERVER_URL,
                    realm_name=settings.KEYCLOAK_REALM,
                    client_id=settings.KEYCLOAK_CLIENT_ID,
                    client_secret_key=getattr(settings, 'KEYCLOAK_CLIENT_SECRET', None),
                    verify=True,
                )
                logger.info("Keycloak client initialized")
            except Exception as e:
                logger.warning(f"Keycloak init failed: {e}")
                self.enabled = False
    
    def get_auth_url(self, redirect_uri: str) -> str:
        """Get Keycloak authorization URL."""
        if not self._client:
            raise RuntimeError("Keycloak not enabled")
        return self._client.auth_url(redirect_uri=redirect_uri)
    
    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        if not self._client:
            raise RuntimeError("Keycloak not enabled")
        
        token = self._client.token(
            grant_type="authorization_code",
            code=code,
            redirect_uri=redirect_uri,
        )
        return token
    
    async def introspect_token(self, token: str) -> Dict[str, Any]:
        """Introspect an access token."""
        if not self._client:
            raise RuntimeError("Keycloak not enabled")
        
        return self._client.introspect(token)
    
    async def get_userinfo(self, token: str) -> Dict[str, Any]:
        """Get user info from token."""
        if not self._client:
            raise RuntimeError("Keycloak not enabled")
        
        return self._client.userinfo(token)
    
    async def logout(self, refresh_token: str) -> None:
        """Logout user and invalidate tokens."""
        if not self._client:
            raise RuntimeError("Keycloak not enabled")
        
        self._client.logout(refresh_token)


# Global instance
keycloak_client = KeycloakClient()
