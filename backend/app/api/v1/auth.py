from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...core.deps import get_current_user
from ...core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from ...models.user import User
from ...schemas.auth import AccessToken, LoginRequest, RefreshRequest, TokenPair, UserOut
from ...services import audit, cookies, token_blocklist
from ...services.rate_limit import RateLimitExceeded, hit as rate_limit_hit

router = APIRouter(prefix="/auth", tags=["auth"])

# Per-email: 10 attempts per 15 min. Per-IP: 30 per 15 min (nginx is 5/min
# so this is a backstop if the edge is bypassed).
_LOGIN_EMAIL_LIMIT = 10
_LOGIN_IP_LIMIT = 30
_LOGIN_WINDOW_S = 15 * 60


async def _guard_login_rate(request: Request, email: str) -> None:
    ip = request.client.host if request.client else "unknown"
    try:
        await rate_limit_hit(f"login:email:{email.lower()}", limit=_LOGIN_EMAIL_LIMIT, window_s=_LOGIN_WINDOW_S)
        await rate_limit_hit(f"login:ip:{ip}", limit=_LOGIN_IP_LIMIT, window_s=_LOGIN_WINDOW_S)
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please retry later.",
            headers={"Retry-After": str(e.retry_after_s)},
        ) from None


@router.post("/login", response_model=TokenPair)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _guard_login_rate(request, body.email)
    user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user.last_login_at = datetime.now(timezone.utc)
    await audit.record(db, user=user, action="login")
    await db.commit()

    access = create_access_token(user.id, user.role)
    refresh = create_refresh_token(user.id)
    # Phase 2.1 §10: emit the refresh token as an HttpOnly cookie alongside
    # the body response. Clients that opt into cookie auth can ignore the
    # body's refresh_token; legacy clients keep working via the body field.
    cookies.set_refresh_cookie(response, refresh)
    cookies.issue_csrf_cookie(response)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
    )


async def _resolve_refresh(request: Request, body: Optional[RefreshRequest]) -> str:
    """Prefer the HttpOnly cookie; fall back to the body for legacy clients."""
    from_cookie = cookies.read_refresh_cookie(request)
    if from_cookie:
        return from_cookie
    if body and body.refresh_token:
        return body.refresh_token
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")


@router.post("/refresh", response_model=AccessToken)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: Optional[RefreshRequest] = None,
):
    # If the refresh came from the cookie, require a valid CSRF double-submit.
    if cookies.read_refresh_cookie(request) and not cookies.verify_csrf(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")

    token = await _resolve_refresh(request, body)
    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    jti = payload.get("jti")
    if jti and await token_blocklist.is_revoked(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")
    user = await db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    # Rotate the CSRF token on every refresh — defence-in-depth against XSS
    # that might have leaked the previous value.
    cookies.issue_csrf_cookie(response)
    return AccessToken(access_token=create_access_token(user.id, user.role))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    body: Optional[RefreshRequest] = None,
):
    """Revoke refresh token (from cookie or body), clear auth cookies."""
    if cookies.read_refresh_cookie(request) and not cookies.verify_csrf(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")

    token = cookies.read_refresh_cookie(request) or (body.refresh_token if body else None)
    if token:
        payload = decode_token(token)
        if payload and payload.get("type") == "refresh" and payload.get("sub") == user.id:
            jti = payload.get("jti")
            if jti:
                await token_blocklist.revoke(jti, token_blocklist.remaining_ttl_s(payload))
    cookies.clear_refresh_cookie(response)
    await audit.record(db, user=user, action="logout")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return UserOut.model_validate(user)
