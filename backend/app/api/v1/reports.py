"""ESG compliance report endpoints (Spec §5.2.6, §14)."""

from datetime import datetime, timezone
from typing import Annotated, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_db
from ...core.deps import get_current_user, require_roles
from ...models.report import ComplianceReport
from ...models.site import Site
from ...models.user import User
from ...schemas.entities import ReportGenerateRequest, ReportOut
from ...services.report_generator import REPORTS_DIR, generate_report

router = APIRouter(prefix="/reports", tags=["reports"])

esg_admin_only = require_roles("esg_admin")


@router.get("", response_model=List[ReportOut])
async def list_reports(
    _=Depends(esg_admin_only),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    rows = (
        await db.execute(
            select(ComplianceReport).order_by(ComplianceReport.created_at.desc()).limit(100)
        )
    ).scalars().all()
    return [ReportOut.model_validate(r) for r in rows]


@router.post("/generate", response_model=ReportOut)
async def generate(
    body: ReportGenerateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    if user.role != "esg_admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    site = await db.get(Site, body.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    report = ComplianceReport(
        id=str(uuid4()),
        site_id=body.site_id,
        report_type=body.report_type,
        period_start=body.period_start,
        period_end=body.period_end,
        status="generating",
        requested_by=user.email,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    # Phase 1: synchronous generation; Phase 2 moves this to Celery.
    try:
        path, integrity = generate_report(
            report_id=report.id,
            site_name=site.name,
            period_start=body.period_start,
            period_end=body.period_end,
            report_type=body.report_type,
        )
        report.status = "ready"
        report.download_url = f"/api/v1/reports/{report.id}/download"
        report.data_integrity_hash = integrity
        report.generated_at = datetime.now(timezone.utc)
    except Exception as exc:  # pragma: no cover - defensive
        report.status = "failed"
        report.download_url = None
        report.data_integrity_hash = None
        _ = exc
    await db.commit()
    await db.refresh(report)
    return ReportOut.model_validate(report)


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: str,
    _=Depends(esg_admin_only),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    r = await db.get(ComplianceReport, report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportOut.model_validate(r)


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    _=Depends(esg_admin_only),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    r = await db.get(ComplianceReport, report_id)
    if not r or r.status != "ready":
        raise HTTPException(status_code=404, detail="Report not available")
    path = REPORTS_DIR / f"{r.id}.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file missing")
    return FileResponse(
        str(path),
        media_type="application/pdf",
        filename=f"GeoSentinel_{r.report_type}_{r.period_start.date()}_{r.period_end.date()}.pdf",
    )
