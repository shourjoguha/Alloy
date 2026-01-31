"""Authentication endpoints for user registration and login."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config.settings import get_settings
from app.db.database import get_db
from app.models.user import User, UserProfile
from app.security import get_password_hash, verify_password, create_access_token, verify_token

router = APIRouter()
settings = get_settings()


class UserRegister(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str
    name: str | None = None


class UserLogin(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user_id: int


class UserResponse(BaseModel):
    """User profile response."""
    id: int
    email: str
    name: str | None
    is_active: bool
    has_completed_onboarding: bool


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user.

    Args:
        user_data: User registration data (email, password, name)
        db: Database session

    Returns:
        JWT token and user ID

    Raises:
        HTTPException: If email already registered
    """
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    hashed_password = get_password_hash(user_data.password)

    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        name=user_data.name,
        is_active=True,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(new_user.id)},
        expires_delta=access_token_expires,
    )

    return TokenResponse(
        access_token=access_token,
        user_id=new_user.id,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return JWT token.

    Args:
        user_data: User login credentials (email, password)
        db: Database session

    Returns:
        JWT token and user ID

    Raises:
        HTTPException: If credentials are invalid
    """
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
    )


@router.get("/verify-token", response_model=UserResponse)
async def verify_token_endpoint(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Verify a JWT token and return user information.

    Args:
        token: JWT access token
        db: Database session

    Returns:
        User information

    Raises:
        HTTPException: If token is invalid or user not found
    """
    user_id = verify_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    from app.models.user import UserProfile
    profile = await db.scalar(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )

    has_completed_onboarding = profile is not None and profile.onboarding_completed_at is not None

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        has_completed_onboarding=has_completed_onboarding,
    )
