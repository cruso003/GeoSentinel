from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from ...services import audit
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
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _guard_login_rate(request, body.email)
    user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user.last_login_at = datetime.now(timezone.utc)
    await audit.record(db, user=user, action="login")
    await db.commit()
    return TokenPair(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=AccessToken)
async def refresh(body: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = await db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return AccessToken(access_token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return UserOut.model_validate(user)
