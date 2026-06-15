"""OIDC authentication router (Keycloak SSO).

S5-4: SSO login flow with python-keycloak.
Coexists with local JWT auth (auth.py).
"""

from fastapi import APIRouter, HTTPException, status, Request, Depends
from fastapi.responses import RedirectResponse
from typing import Optional

from app.services.keycloak_client import keycloak_client
from app.core.config import settings

router = APIRouter(tags=["OIDC"])


@router.get("/login")
async def oidc_login(redirect_uri: Optional[str] = None):
    """Redirect to Keycloak login page."""
    if not keycloak_client.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC/Keycloak is not configured"
        )
    
    callback = redirect_uri or f"http://localhost:{settings.PORT}/api/v1/oidc/callback"
    auth_url = keycloak_client.get_auth_url(redirect_uri=callback)
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def oidc_callback(code: str, redirect_uri: Optional[str] = None):
    """Handle Keycloak callback after login.
    
    Exchanges authorization code for tokens.
    """
    if not keycloak_client.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC/Keycloak is not configured"
        )
    
    callback = redirect_uri or f"http://localhost:{settings.PORT}/api/v1/oidc/callback"
    
    try:
        token = await keycloak_client.exchange_code(code, redirect_uri=callback)
        return {
            "access_token": token.get("access_token"),
            "refresh_token": token.get("refresh_token"),
            "token_type": token.get("token_type", "Bearer"),
            "expires_in": token.get("expires_in"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OIDC token exchange failed: {str(e)}"
        )


@router.get("/userinfo")
async def oidc_userinfo(access_token: str):
    """Get user info from Keycloak access token."""
    if not keycloak_client.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC/Keycloak is not configured"
        )
    
    try:
        userinfo = await keycloak_client.get_userinfo(access_token)
        return userinfo
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )


@router.post("/logout")
async def oidc_logout(refresh_token: str):
    """Logout from Keycloak and invalidate tokens."""
    if not keycloak_client.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC/Keycloak is not configured"
        )
    
    try:
        await keycloak_client.logout(refresh_token)
        return {"detail": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Logout failed: {str(e)}"
        )


@router.get("/config")
async def oidc_config():
    """Return OIDC configuration status (without secrets)."""
    return {
        "enabled": keycloak_client.enabled,
        "server_url": settings.KEYCLOAK_SERVER_URL if keycloak_client.enabled else None,
        "realm": settings.KEYCLOAK_REALM if keycloak_client.enabled else None,
        "client_id": settings.KEYCLOAK_CLIENT_ID if keycloak_client.enabled else None,
    }
