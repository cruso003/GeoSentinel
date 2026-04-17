"""Async ESG report generation task (Spec §14)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from ..core.db import SessionLocal
from ..models.report import ComplianceReport
from ..models.site import Site
from ..services.report_generator import generate_report
from .celery_app import celery_app

log = logging.getLogger(__name__)


async def _generate(report_id: str) -> str:
    async with SessionLocal() as db:
        report = await db.get(ComplianceReport, report_id)
        if report is None:
            return "missing"
        site = await db.get(Site, report.site_id)
        if site is None:
            report.status = "failed"
            await db.commit()
            return "site-missing"
        try:
            _, integrity = generate_report(
                report_id=report.id,
                site_name=site.name,
                period_start=report.period_start,
                period_end=report.period_end,
                report_type=report.report_type,
            )
            report.status = "ready"
            report.data_integrity_hash = integrity
            report.download_url = f"/api/v1/reports/{report.id}/download"
            report.generated_at = datetime.now(timezone.utc)
        except Exception as e:  # pragma: no cover
            log.exception("report generation failed: %s", e)
            report.status = "failed"
        await db.commit()
    return report_id


@celery_app.task(name="app.tasks.report_generation.generate_compliance_report")
def generate_compliance_report(report_id: str) -> str:
    return asyncio.run(_generate(report_id))
