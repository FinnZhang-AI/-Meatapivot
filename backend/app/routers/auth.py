"""Updated authentication with real PostgreSQL user storage.

Replaces mock auth with:
- bcrypt password hashing
- PostgreSQL user CRUD
- JWT token generation/validation
- Password verification
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.schemas import Token, TokenData, UserCreate, UserResponse
from app.models.database_models import User
from app.services.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate bcrypt hash for a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Fetch user from database by username."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password."""
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Get current user from JWT token (with database validation)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Fetch user from database
    user = await get_user_by_username(db, username)
    if user is None:
        raise credentials_exception
    
    # Use actual tenant_id from database, not JWT payload
    tenant_id = str(user.tenant_id) if user.tenant_id else "tenant-default"
    
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        tenant_id=tenant_id,
        roles=payload.get("roles", [user.role]),
        created_at=user.created_at,
        is_active=user.is_active,
    )


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user with bcrypt password hashing."""
    # Check if username already exists
    existing = await get_user_by_username(db, user_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_data.username}' already exists"
        )
    
    # Create new user with hashed password
    # Use provided tenant_id or default tenant
    from uuid import UUID
    DEFAULT_TENANT_UUID = UUID("00000000-0000-0000-0000-000000000000")
    tenant_uuid = DEFAULT_TENANT_UUID
    if user_data.tenant_id:
        try:
            tenant_uuid = UUID(user_data.tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tenant_id format: {user_data.tenant_id}"
            )
    
    db_user = User(
        id=uuid.uuid4(),
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        tenant_id=tenant_uuid,
        role=user_data.roles[0] if user_data.roles else "user",
        is_active=True,
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    logger.info(f"User registered: {user_data.username}")
    
    return UserResponse(
        id=str(db_user.id),
        username=db_user.username,
        email=db_user.email,
        tenant_id=user_data.tenant_id,
        roles=user_data.roles,
        created_at=db_user.created_at,
        is_active=db_user.is_active,
    )


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Login and get access token (validates against PostgreSQL)."""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "roles": [user.role],
            "tenant_id": str(user.tenant_id) if user.tenant_id else "tenant-default",
        },
        expires_delta=access_token_expires
    )
    
    logger.info(f"User logged in: {user.username}")
    
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """Get current user information"""
    return current_user
