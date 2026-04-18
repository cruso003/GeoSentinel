from fastapi import APIRouter

from .auth import router as auth_router
from .sites import router as sites_router
from .sensors import router as sensors_router
from .ai import router as ai_router
from .alerts import router as alerts_router
from .reports import router as reports_router
from .community import router as community_router
from .audit import router as audit_router
from .gateways import router as gateways_router
from .notifications import router as notifications_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(sites_router)
api_router.include_router(sensors_router)
api_router.include_router(ai_router)
api_router.include_router(alerts_router)
api_router.include_router(reports_router)
api_router.include_router(community_router)
api_router.include_router(audit_router)
api_router.include_router(gateways_router)
api_router.include_router(notifications_router)
