"""
Sign-in, sessions and passwords. See utils/auth.py for the session model.

Brute-force protection (in-memory, per process):
  - 5 failed logins per email+IP per 15 minutes, 30 attempts per IP
  - 5 reset requests per IP and 3 per email per hour
"""
import secrets
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import PasswordResetToken, User, UserSession
from ..schemas import (
    ChangePasswordRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    SessionOut,
    UserCreate,
    UserLogin,
    UserResponse,
)
from ..utils import ratelimit
from ..utils.auth import (
    authenticate_user,
    clear_session_cookie,
    create_session,
    current_session,
    get_current_user,
    get_password_hash,
    hash_token,
    password_problem,
    revoke_sessions,
    session_is_live,
    set_session_cookie,
    verify_password,
)
from ..utils.mailer import send_email
from ..utils.timeutil import as_utc, utcnow

router = APIRouter(prefix="/auth", tags=["Authentication"])

FAIL_WINDOW = 15 * 60
RESET_WINDOW = 60 * 60
RESET_TOKEN_TTL = timedelta(hours=1)


def _check_password(password: str, email: str):
    problem = password_problem(password, email)
    if problem:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=problem)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, request: Request, response: Response, db: Session = Depends(get_db)):
    """Create an account and sign it in."""
    ratelimit.check(f"register:{ratelimit.client_ip(request)}", 10, RESET_WINDOW)
    email = user_data.email.lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    _check_password(user_data.password, email)
    user = User(email=email, name=user_data.name, password_hash=get_password_hash(user_data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, create_session(db, user, request))
    return user


@router.post("/login", response_model=UserResponse)
def login(credentials: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    """Sign in; sets the httpOnly session cookie."""
    ip = ratelimit.client_ip(request)
    email = credentials.email.lower()
    fail_key = f"login-fail:{email}:{ip}"
    ratelimit.check(f"login-ip:{ip}", 30, FAIL_WINDOW)
    ratelimit.check(fail_key, 5, FAIL_WINDOW, record=False)

    user = authenticate_user(db, email, credentials.password)
    if not user:
        ratelimit.record(fail_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    ratelimit.clear(fail_key)
    set_session_cookie(response, create_session(db, user, request))
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """End this browser's session (safe to call when already signed out)."""
    s = current_session(request, db)
    if s is not None:
        s.revoked_at = utcnow()
        db.commit()
    clear_session_cookie(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(response: Response, current_user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Sign out every device, including this one."""
    revoke_sessions(db, current_user.id)
    clear_session_cookie(response)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/sessions", response_model=List[SessionOut])
def list_sessions(request: Request, current_user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Devices currently signed in to this account."""
    rows = (db.query(UserSession)
            .filter(UserSession.user_id == current_user.id, UserSession.revoked_at.is_(None))
            .order_by(UserSession.last_seen_at.desc()).all())
    this_id = getattr(request.state, "session_id", None)
    return [
        SessionOut(id=s.id, created_at=s.created_at, last_seen_at=s.last_seen_at,
                   user_agent=s.user_agent, ip_address=s.ip_address, current=s.id == this_id)
        for s in rows if session_is_live(s)
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(session_id: int, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    s = db.query(UserSession).filter(UserSession.id == session_id,
                                     UserSession.user_id == current_user.id).first()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    s.revoked_at = utcnow()
    db.commit()


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: ChangePasswordRequest, request: Request,
                    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Change password; every other device is signed out."""
    ratelimit.check(f"change-pw:{current_user.id}", 5, FAIL_WINDOW, record=False)
    if not verify_password(payload.current_password, current_user.password_hash):
        ratelimit.record(f"change-pw:{current_user.id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    _check_password(payload.new_password, current_user.email)
    current_user.password_hash = get_password_hash(payload.new_password)
    db.commit()
    revoke_sessions(db, current_user.id, except_id=getattr(request.state, "session_id", None))


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    """Email a reset link if the account exists. Always answers the same,
    so it can't be used to discover which emails have accounts."""
    email = payload.email.lower()
    ratelimit.check(f"reset-ip:{ratelimit.client_ip(request)}", 5, RESET_WINDOW)
    ratelimit.check(f"reset-email:{email}", 3, RESET_WINDOW)
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user:
        token = secrets.token_urlsafe(32)
        now = utcnow()
        db.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(token), created_at=now,
                                  expires_at=now + RESET_TOKEN_TTL))
        db.commit()
        link = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/reset-password?token={token}"
        send_email(
            user.email, "Reset your GreenThread password",
            f"Hi {user.name},\n\nUse this link within the next hour to choose a new password:\n\n{link}\n\n"
            "If you didn't ask for this, ignore this email — your password won't change.\n",
        )
    return {"status": "If that email has an account, a reset link is on its way."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirm, request: Request, db: Session = Depends(get_db)):
    """Set a new password with a reset token; signs out every device."""
    ratelimit.check(f"reset-confirm:{ratelimit.client_ip(request)}", 10, FAIL_WINDOW)
    row = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == hash_token(payload.token)).first()
    if row is None or row.used_at is not None or as_utc(row.expires_at) <= utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This reset link is invalid or has expired. Request a new one.")
    user = db.query(User).filter(User.id == row.user_id).first()
    _check_password(payload.new_password, user.email)
    user.password_hash = get_password_hash(payload.new_password)
    row.used_at = utcnow()
    db.commit()
    revoke_sessions(db, user.id)
