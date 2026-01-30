"""Authentication configuration with FastAPI-Users."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.models.user import User

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """User manager for FastAPI-Users."""

    reset_password_token_secret = get_settings().jwt_secret
    verification_token_secret = get_settings().jwt_secret

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        """Called after successful registration."""
        # Could send welcome email, log event, etc.
        pass

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        """Called after password reset requested."""
        # Send password reset email
        pass

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        """Called after verification requested."""
        # Send verification email
        pass


async def get_user_db(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncGenerator[SQLAlchemyUserDatabase[User, uuid.UUID], None]:
    """Get SQLAlchemy user database."""
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(
    user_db: Annotated[SQLAlchemyUserDatabase[User, uuid.UUID], Depends(get_user_db)],
) -> AsyncGenerator[UserManager, None]:
    """Get user manager instance."""
    yield UserManager(user_db)


# JWT Bearer transport
bearer_transport = BearerTransport(tokenUrl="/v1/auth/login")


def get_jwt_strategy() -> JWTStrategy[User, uuid.UUID]:
    """Get JWT strategy with settings."""
    settings = get_settings()
    return JWTStrategy(
        secret=settings.jwt_secret,
        lifetime_seconds=settings.jwt_expire_minutes * 60,
        algorithm=settings.jwt_algorithm,
    )


# Authentication backend
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI Users instance
fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Dependencies for route protection
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
current_user_optional = fastapi_users.current_user(active=True, optional=True)

# Type alias for dependency injection
CurrentUser = Annotated[User, Depends(current_active_user)]


async def get_current_user_optional(request: Request) -> User | None:
    """Get current user if authenticated, None otherwise.

    Checks both Bearer token (API) and session cookie (web).
    """
    from sqlalchemy import select

    from api.database import async_session_maker

    # First try session cookie (for web UI)
    session_token = request.cookies.get("findable_session")
    if session_token:
        try:
            settings = get_settings()
            payload = jwt.decode(
                session_token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )
            user_id = payload.get("sub")
            if user_id:
                async with async_session_maker() as db:
                    result = await db.execute(
                        select(User).where(User.id == uuid.UUID(user_id))
                    )
                    user = result.scalar_one_or_none()
                    if user and user.is_active:
                        return user
        except Exception:
            pass

    # Fall back to Bearer token
    try:
        user_dependency = current_user_optional
        user = await user_dependency(request)
        return user
    except Exception:
        return None


def _truncate_password(password: str) -> str:
    """Truncate password to 72 bytes for bcrypt compatibility."""
    # bcrypt has a 72-byte limit on passwords
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hash."""
    return pwd_context.verify(_truncate_password(plain_password), hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(_truncate_password(password))


def create_access_token(user_id: str) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "aud": "fastapi-users:auth",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
