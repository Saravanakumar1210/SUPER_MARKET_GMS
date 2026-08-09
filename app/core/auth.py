import secrets
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Session, User

settings = get_settings()
security = HTTPBearer(auto_error=False)
_pwd_hasher = bcrypt.using(rounds=10)
SESSION_COOKIE_NAME = "gms_session"


def hash_password(password: str) -> str:
    return _pwd_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.verify(password, hashed)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_session(db: AsyncSession, user_id: uuid.UUID) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.session_expire_minutes)
    db.add(Session(user_id=user_id, session_token=hash_session_token(token), expires=expires))
    await db.flush()
    return token


async def get_user_by_session(db: AsyncSession, token: str | None) -> User | None:
    if not token:
        return None
    token_hash = hash_session_token(token)
    result = await db.execute(
        select(User)
        .join(Session, Session.user_id == User.id)
        .where(Session.session_token == token_hash, Session.expires > datetime.now(timezone.utc))
    )
    return result.scalar_one_or_none()


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    token = creds.credentials if creds else request.cookies.get(SESSION_COOKIE_NAME)
    return await get_user_by_session(db, token)


async def require_user(user: User | None = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def require_customer(user: User = Depends(require_user)) -> User:
    if user.role != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer access required")
    return user
