"""Notification preferences + ESG admin view + test-alert (Phase 2.3)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...core.deps import get_current_user, require_roles
from ...models.notifications import NotificationSubscription
from ...models.site import Site
from ...models.user import User
from ...schemas.notifications import (
    ProfileOut,
    ProfileUpdate,
    SubscriberRowOut,
    SubscriptionIn,
    SubscriptionOut,
    TestAlertRequest,
)
from ...services import audit
from ...services.notifications import notifications
from ...services.rbac import allowed_site_ids, user_can_access_site

router = APIRouter(tags=["notifications"])

esg_admin = require_roles("esg_admin")


# --- Profile (notification-relevant fields) ----------------------------------


@router.get("/profile", response_model=ProfileOut)
async def get_profile(
    user: Annotated[User, Depends(get_current_user)],
):
    return ProfileOut(
        id=user.id,
        name=user.name,
        email=user.email,
        phone_number=user.phone_number,
        role=user.role,
    )


@router.patch("/profile", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if body.name is not None:
        user.name = body.name
    if body.phone_number is not None or (
        body.model_fields_set and "phone_number" in body.model_fields_set
    ):
        user.phone_number = body.phone_number
    await audit.record(db, user=user, action="update_profile")
    await db.commit()
    return ProfileOut(
        id=user.id,
        name=user.name,
        email=user.email,
        phone_number=user.phone_number,
        role=user.role,
    )


# --- Subscriptions (self-service) --------------------------------------------


@router.get("/subscriptions", response_model=list[SubscriptionOut])
async def list_my_subscriptions(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = (
        await db.execute(
            select(NotificationSubscription).where(
                NotificationSubscription.user_id == user.id
            )
        )
    ).scalars().all()
    return [SubscriptionOut.model_validate(r) for r in rows]


@router.put("/subscriptions", response_model=SubscriptionOut)
async def upsert_subscription(
    body: SubscriptionIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not await user_can_access_site(
        db, user, body.site_id, roles=("operator", "esg_admin", "community")
    ):
        raise HTTPException(status_code=403, detail="Not a member of that site")

    existing = (
        await db.execute(
            select(NotificationSubscription).where(
                NotificationSubscription.user_id == user.id,
                NotificationSubscription.site_id == body.site_id,
                NotificationSubscription.channel == body.channel,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = NotificationSubscription(
            user_id=user.id,
            site_id=body.site_id,
            channel=body.channel,
            min_severity=body.min_severity,
            active=body.active,
        )
        db.add(existing)
    else:
        existing.min_severity = body.min_severity
        existing.active = body.active
    await audit.record(
        db,
        user=user,
        action="upsert_subscription",
        target_type="notification_subscription",
        site_id=body.site_id,
        details=f"channel={body.channel};min={body.min_severity};active={body.active}",
    )
    await db.commit()
    await db.refresh(existing)
    return SubscriptionOut.model_validate(existing)


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    sub = await db.get(NotificationSubscription, subscription_id)
    if sub is None or sub.user_id != user.id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.execute(
        delete(NotificationSubscription).where(NotificationSubscription.id == sub.id)
    )
    await audit.record(
        db,
        user=user,
        action="delete_subscription",
        target_type="notification_subscription",
        target_id=subscription_id,
        site_id=sub.site_id,
    )
    await db.commit()


# --- Test alert --------------------------------------------------------------


@router.post("/subscriptions/test", status_code=status.HTTP_202_ACCEPTED)
async def send_test_alert(
    body: TestAlertRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Send a dummy WARNING to the current user to validate notification
    setup. Channel must be ``email`` or ``sms``; ``push`` is no-op for now.
    The request 202s even if the provider is unconfigured — the dev log will
    show the noop."""
    if not await user_can_access_site(
        db, user, body.site_id, roles=("operator", "esg_admin", "community")
    ):
        raise HTTPException(status_code=403, detail="Not a member of that site")
    site = await db.get(Site, body.site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")

    subject = f"[GeoSentinel TEST] {site.name}"
    await notifications.direct(
        subject=subject,
        body=body.message,
        email=user.email if body.channel == "email" else None,
        phone=user.phone_number if body.channel == "sms" else None,
    )
    await audit.record(
        db,
        user=user,
        action="test_alert",
        site_id=body.site_id,
        details=f"channel={body.channel}",
    )
    await db.commit()
    return {"accepted": True, "channel": body.channel}


# --- ESG admin view ----------------------------------------------------------


@router.get("/admin/subscribers", response_model=list[SubscriberRowOut])
async def list_subscribers(
    _: Annotated[User, Depends(esg_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = (
        select(NotificationSubscription, User)
        .join(User, User.id == NotificationSubscription.user_id)
        .order_by(User.email, NotificationSubscription.site_id)
    )
    rows = (await db.execute(stmt)).all()
    return [
        SubscriberRowOut(
            user_id=u.id,
            user_email=u.email,
            user_name=u.name,
            site_id=s.site_id,
            channel=s.channel,
            min_severity=s.min_severity,
            active=s.active,
        )
        for s, u in rows
    ]


# --- Sites visible to the current user (frontend scope) ----------------------


@router.get("/me/sites")
async def my_sites(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ids = await allowed_site_ids(db, user)
    if not ids:
        return []
    rows = (await db.execute(select(Site).where(Site.id.in_(ids)))).scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "region": s.region,
            "country": s.country,
            "centroid": {"lat": s.centroid_lat, "lng": s.centroid_lng},
        }
        for s in rows
    ]
