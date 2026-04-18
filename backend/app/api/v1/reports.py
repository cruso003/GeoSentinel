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
from ...services import audit
from ...services.report_generator import REPORTS_DIR, generate_report
from ...services.report_stats import collect_compliance_stats

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
    await audit.record(
        db,
        user=user,
        action="generate_report",
        target_type="compliance_report",
        target_id=report.id,
        site_id=body.site_id,
        details=body.report_type,
    )
    await db.commit()
    await db.refresh(report)

    # Phase 3: synchronous generation with real stats from the alert log.
    # Moving to Celery is the next step once the PDF starts including
    # fetched InfluxDB telemetry windows.
    try:
        data = await collect_compliance_stats(
            db,
            site_id=body.site_id,
            period_start=body.period_start,
            period_end=body.period_end,
        )
        result = generate_report(
            report_id=report.id,
            site_name=site.name,
            period_start=body.period_start,
            period_end=body.period_end,
            report_type=body.report_type,
            data=data,
        )
        report.status = "ready"
        report.download_url = f"/api/v1/reports/{report.id}/download"
        report.data_integrity_hash = result.integrity_hash
        report.signature_b64 = result.signature_b64
        report.signing_pubkey_hex = result.signing_pubkey_hex
        report.generated_at = datetime.now(timezone.utc)
    except Exception as exc:  # pragma: no cover - defensive
        report.status = "failed"
        report.download_url = None
        report.data_integrity_hash = None
        report.signature_b64 = None
        report.signing_pubkey_hex = None
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


@router.get("/{report_id}/signature")
async def report_signature(
    report_id: str,
    _=Depends(esg_admin_only),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Detached Ed25519 signature + pubkey hex for external auditors.

    Auditors download the PDF from ``/download``, fetch the signature from
    this endpoint, and verify independently. ``pdf_sha256`` is the
    integrity hash that was written into the PDF itself (Executive Summary
    section) so a reviewer can cross-check without re-hashing the bytes.
    """

    r = await db.get(ComplianceReport, report_id)
    if not r or r.status != "ready":
        raise HTTPException(status_code=404, detail="Report not available")
    if not r.signature_b64 or not r.signing_pubkey_hex:
        raise HTTPException(status_code=404, detail="Report not signed")
    return {
        "report_id": r.id,
        "signature_b64": r.signature_b64,
        "pubkey_hex": r.signing_pubkey_hex,
        "pdf_sha256": r.data_integrity_hash,
    }
