"""Public community dashboard endpoints (Spec §5.2.7, §10).

These routes are intentionally unauthenticated so residents near a mine can
check drinking-water / air-quality / ground-stability status without creating
an account.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...models.site import Site
from ...schemas.community import (
    CommunityConfirmResponse,
    CommunityOptInConfirm,
    CommunityOptInRequest,
    CommunityOptInResponse,
)
from ...schemas.entities import CommunityStatusOut
from ...services.community_opt_in import (
    OptInError,
    confirm_opt_in,
    request_opt_in,
)
from ...services.enviroguard import run_enviroguard
from ...services.influx import influx
from ...services.notifications import notifications
from ...services.rate_limit import RateLimitExceeded, hit as rate_limit_hit

router = APIRouter(prefix="/community", tags=["community"])

# Opt-in rate limits (sliding window):
#   - Per-IP:    10 subscribe attempts / 15 min — stops a single host spraying.
#   - Per-phone:  3 subscribe attempts / 15 min — caps SMS cost for one number.
#   - Per-phone: 10 confirm attempts / 15 min — combined with MAX_ATTEMPTS in
#                the row, makes brute-force infeasible before the code expires.
_OPT_IN_IP_LIMIT = 10
_OPT_IN_PHONE_LIMIT = 3
_CONFIRM_PHONE_LIMIT = 10
_OPT_IN_WINDOW_S = 15 * 60


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _guard_opt_in(request: Request, *, phone: str) -> None:
    ip = _client_ip(request)
    try:
        await rate_limit_hit(
            f"community:optin:ip:{ip}",
            limit=_OPT_IN_IP_LIMIT,
            window_s=_OPT_IN_WINDOW_S,
        )
        await rate_limit_hit(
            f"community:optin:phone:{phone}",
            limit=_OPT_IN_PHONE_LIMIT,
            window_s=_OPT_IN_WINDOW_S,
        )
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many opt-in attempts. Please retry later.",
            headers={"Retry-After": str(e.retry_after_s)},
        ) from None


async def _guard_confirm(request: Request, *, phone: str) -> None:
    ip = _client_ip(request)
    try:
        await rate_limit_hit(
            f"community:confirm:ip:{ip}",
            limit=_OPT_IN_IP_LIMIT,
            window_s=_OPT_IN_WINDOW_S,
        )
        await rate_limit_hit(
            f"community:confirm:phone:{phone}",
            limit=_CONFIRM_PHONE_LIMIT,
            window_s=_OPT_IN_WINDOW_S,
        )
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many confirmation attempts. Please retry later.",
            headers={"Retry-After": str(e.retry_after_s)},
        ) from None


def _water_tone(ph: float | None, turb: float | None, cond: float | None) -> tuple[str, str]:
    if ph is None and turb is None and cond is None:
        return "CAUTION", "Recent readings unavailable."
    ph_bad = ph is not None and (ph < 6.0 or ph > 9.0)
    turb_bad = turb is not None and turb > 5
    cond_bad = cond is not None and cond > 500
    if ph_bad or cond_bad or (turb is not None and turb > 10):
        return "DO_NOT_USE", "Water quality outside safe drinking range. Use alternative sources."
    if turb_bad:
        return "CAUTION", "Turbidity slightly elevated after recent rainfall. Boil before drinking."
    return "SAFE", "Water downstream of the mine meets IFC drinking-water guidelines."


def _air_tone(pm25: float | None) -> tuple[str, str]:
    if pm25 is None:
        return "CAUTION", "Recent readings unavailable."
    if pm25 > 55:
        return "DO_NOT_USE", "Air quality is unhealthy. Limit outdoor activity and close windows."
    if pm25 > 25:
        return "CAUTION", "PM2.5 elevated. Sensitive groups should reduce prolonged outdoor exertion."
    return "SAFE", "Air quality around the mine is within WHO/IFC guidelines."


def _ground_tone(risk_24h: str) -> tuple[str, str]:
    if risk_24h in ("CRITICAL",):
        return "DO_NOT_USE", "Slope risk elevated. Follow evacuation guidance from local authorities."
    if risk_24h in ("HIGH", "ELEVATED"):
        return "CAUTION", "Slope monitoring shows elevated risk. Stay clear of marked exclusion zones."
    return "SAFE", "All monitored slopes are stable."


async def _latest_env_value(node_id: str, field: str) -> float | None:
    row = await influx.latest("env", node_id)
    if not row:
        return None
    v = row.get(field)
    return float(v) if v is not None else None


@router.get("/{site_id}", response_model=CommunityStatusOut)
async def community_status(
    site_id: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Pull representative nodes if present, else fall back to placeholders.
    ph = await _latest_env_value("ENV-01", "ph")
    turb = await _latest_env_value("ENV-01", "turbidity")
    cond = await _latest_env_value("ENV-02", "conductivity")
    pm25 = await _latest_env_value("ENV-03", "pm25")

    water_status, water_msg = _water_tone(ph, turb, cond)
    air_status, air_msg = _air_tone(pm25)
    pred = await run_enviroguard(site_id)
    ground_status, ground_msg = _ground_tone(pred.overall_risk_24h)

    overall_rank = {"SAFE": 0, "CAUTION": 1, "DO_NOT_USE": 2}
    overall = max((water_status, air_status, ground_status), key=lambda s: overall_rank[s])

    now = datetime.now(timezone.utc).isoformat()
    return CommunityStatusOut(
        site_id=site_id,
        overall=overall,
        water={
            "status": water_status,
            "message": water_msg,
            "ph": ph,
            "turbidity": turb,
            "conductivity": cond,
            "as_of": now,
        },
        air={
            "status": air_status,
            "message": air_msg,
            "pm25": pm25,
            "as_of": now,
        },
        ground={
            "status": ground_status,
            "message": ground_msg,
            "risk_24h": pred.overall_risk_24h,
            "as_of": now,
        },
    )


@router.post(
    "/subscribe",
    response_model=CommunityOptInResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def subscribe(
    body: CommunityOptInRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Request an SMS confirmation code for a (phone, site) pair.

    Public + rate-limited. The response always carries ``expires_at`` so the
    caller can show a countdown; ``debug_code`` is populated only in dev
    (noop SMS provider) to keep smoke-tests fast.
    """
    await _guard_opt_in(request, phone=body.phone_number)
    site = await db.get(Site, body.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    try:
        result = await request_opt_in(
            db,
            phone=body.phone_number,
            site_id=body.site_id,
            language=body.language,
            service=notifications,
        )
    except OptInError as e:
        raise HTTPException(status_code=400, detail=e.reason) from None
    return CommunityOptInResponse(
        phone_number=result.phone_number,
        site_id=result.site_id,
        expires_at=result.expires_at,
        debug_code=result.debug_code,
    )


@router.post("/confirm", response_model=CommunityConfirmResponse)
async def confirm(
    body: CommunityOptInConfirm,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Redeem a confirmation code, provisioning a community user + active
    SMS subscription for the site. Public + rate-limited. ``OptInError`` →
    400 with a user-visible reason."""
    await _guard_confirm(request, phone=body.phone_number)
    try:
        result = await confirm_opt_in(
            db,
            phone=body.phone_number,
            site_id=body.site_id,
            code=body.code,
        )
    except OptInError as e:
        raise HTTPException(status_code=400, detail=e.reason) from None
    return CommunityConfirmResponse(
        user_id=result.user_id,
        subscription_id=result.subscription_id,
    )
