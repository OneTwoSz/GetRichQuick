"""
Authentication: password hashing, server-side sessions, CSRF guard.

Sessions
  Login creates a UserSession row and sets an httpOnly cookie holding a
  random token (JavaScript can't read it, so an XSS bug can't steal it).
  Only the token's SHA-256 is stored. A session ends when it is revoked
  (logout, password change, "sign out everywhere"), when it has been idle
  for SESSION_IDLE_DAYS, or SESSION_MAX_DAYS after sign-in.

  API clients without a browser may send the same token as
  `Authorization: Bearer <token>` instead of the cookie.

CSRF
  Cookies are SameSite=Lax, and every state-changing /api request must
  carry the `X-Requested-With` header (see main.py). Browsers only let
  pages from allowed origins attach custom headers cross-site, so a
  malicious page can't submit requests on a signed-in user's behalf.
"""
import hashlib
import re
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response, status
from passlib.context import CryptContext
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User, UserSession
from .timeutil import as_utc, utcnow

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash of a random password, verified against when the email is unknown so
# "no such user" takes as long as "wrong password" (no account enumeration).
_DUMMY_HASH = pwd_context.hash(secrets.token_hex(16))

# Refresh last_seen_at at most this often, to avoid a write per request.
_TOUCH_INTERVAL = timedelta(minutes=5)

MIN_PASSWORD_LENGTH = 8


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def password_problem(password: str, email: Optional[str] = None) -> Optional[str]:
    """Return why a password is unacceptable, or None if it's fine."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    if len(password.encode("utf-8")) > 72:
        return "Password must be at most 72 bytes"  # bcrypt's limit
    if len(set(password)) < 4:
        return "Password is too simple"
    if email and password.lower() == email.lower():
        return "Password can't be your email address"
    if re.fullmatch(r"(?i)(password|12345678|qwertyui|greenthread)\d*", password):
        return "Password is too common"
    return None


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
    if not user:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _cookie_secure() -> bool:
    if settings.COOKIE_SECURE is not None:
        return settings.COOKIE_SECURE
    return (settings.PUBLIC_BASE_URL or "").startswith("https://")


def create_session(db: Session, user: User, request: Request) -> str:
    """Start a session; returns the raw token (only its hash is stored)."""
    token = secrets.token_urlsafe(32)
    now = utcnow()
    db.add(UserSession(
        user_id=user.id, token_hash=hash_token(token), created_at=now, last_seen_at=now,
        expires_at=now + timedelta(days=settings.SESSION_MAX_DAYS),
        user_agent=(request.headers.get("user-agent") or "")[:300] or None,
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()
    return token


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.SESSION_COOKIE, token,
        max_age=settings.SESSION_MAX_DAYS * 86400,
        httponly=True, secure=_cookie_secure(), samesite="lax", path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.SESSION_COOKIE, path="/", httponly=True,
                           secure=_cookie_secure(), samesite="lax")


def session_is_live(s: UserSession) -> bool:
    now = utcnow()
    return (
        s.revoked_at is None
        and as_utc(s.expires_at) > now
        and as_utc(s.last_seen_at) + timedelta(days=settings.SESSION_IDLE_DAYS) > now
    )


def _token_from(request: Request) -> Optional[str]:
    cookie = request.cookies.get(settings.SESSION_COOKIE)
    if cookie:
        return cookie
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def current_session(request: Request, db: Session) -> Optional[UserSession]:
    token = _token_from(request)
    if not token:
        return None
    s = db.query(UserSession).filter(UserSession.token_hash == hash_token(token)).first()
    if s is None or not session_is_live(s):
        return None
    return s


def revoke_sessions(db: Session, user_id: int, *, except_id: Optional[int] = None) -> int:
    q = db.query(UserSession).filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_id is not None:
        q = q.filter(UserSession.id != except_id)
    count = 0
    now = utcnow()
    for s in q.all():
        s.revoked_at = now
        count += 1
    db.commit()
    return count


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """FastAPI dependency: the signed-in user, or 401."""
    s = current_session(request, db)
    if s is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    user = db.query(User).filter(User.id == s.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    if utcnow() - as_utc(s.last_seen_at) > _TOUCH_INTERVAL:
        s.last_seen_at = utcnow()
        db.commit()
    request.state.session_id = s.id
    return user
