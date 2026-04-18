"""Common request dependencies (auth, role guards)."""

from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from ..services.rbac import user_can_access_site
from .db import get_db
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = await db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*roles: str):
    async def _guard(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _guard


def require_site_role(*roles: str):
    """Guard a ``/.../{site_id}/...`` route by membership + platform role.

    Phase 2.3 §3: ``require_site_role("operator","esg_admin")`` enforces a
    ``user_sites`` membership whose role is in ``roles`` — except
    ``esg_admin`` users, who see every site by default unless an explicit
    membership narrows them. Use this in place of ``require_roles`` on any
    route that receives a ``site_id`` path param.
    """

    async def _guard(
        user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
        site_id: Annotated[str, Path()],
    ) -> User:
        ok = await user_can_access_site(db, user, site_id, roles=roles)
        if not ok:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _guard
