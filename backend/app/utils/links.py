"""
Shared rules for login-free token links (buyer share, job-work, supplier
data requests).

  - Tokens are 128-bit random (secrets.token_urlsafe(16)), so they can't
    be guessed; public lookups are also rate-limited per IP.
  - Links expire (None = links minted before expiry existed, never).
  - Revoking clears or flags the token so the old URL stops working.
  - Submission links cap how many times they can be used, and each IP is
    rate-limited, so a leaked link can't flood a factory with data.

Product passports are deliberately NOT expiring: their QR codes are printed
on garment labels and must keep working.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request, status

from . import ratelimit
from .timeutil import is_past, utcnow

PUBLIC_LOOKUP_LIMIT = (120, 10 * 60)     # per IP: lookups per 10 minutes
PUBLIC_SUBMIT_LIMIT = (10, 60 * 60)      # per IP: submissions per hour


def new_token() -> str:
    return secrets.token_urlsafe(16)


def expiry(days: Optional[int]) -> Optional[datetime]:
    return utcnow() + timedelta(days=days) if days else None


def throttle_lookup(request: Request, kind: str) -> None:
    limit, window = PUBLIC_LOOKUP_LIMIT
    ratelimit.check(f"lookup:{kind}:{ratelimit.client_ip(request)}", limit, window)


def throttle_submit(request: Request, kind: str) -> None:
    limit, window = PUBLIC_SUBMIT_LIMIT
    ratelimit.check(f"submit:{kind}:{ratelimit.client_ip(request)}", limit, window)


def ensure_usable(*, expires_at: Optional[datetime], revoked: bool = False) -> None:
    """410 Gone for revoked or expired links (vs 404 for unknown tokens)."""
    if revoked:
        raise HTTPException(status_code=status.HTTP_410_GONE,
                            detail="This link is no longer valid. Ask the factory for a new one.")
    if is_past(expires_at):
        raise HTTPException(status_code=status.HTTP_410_GONE,
                            detail="This link has expired. Ask the factory for a new one.")


def ensure_submissions_left(used: int, maximum: Optional[int]) -> None:
    if maximum is not None and used >= maximum:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="This link has reached its submission limit. Ask the factory for a new one.")
