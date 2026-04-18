"""ESG compliance report generator (Spec §14).

Produces a ReportLab PDF with the seven sections required by IFC reporting.
Phase 3 pulls real stats from the alert log + slope-watch predictions via
:func:`app.services.report_stats.collect_compliance_stats`. When no report
data is supplied the renderer falls back to a deterministic synthetic set —
kept only so local smoke-tests still produce a non-trivial PDF.
"""

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .report_stats import ExceedanceLogRow, GeohazardSummary, ReportData, StatsRow

REPORTS_DIR = Path(os.environ.get("GEOSENTINEL_REPORTS_DIR", "/tmp/geosentinel-reports"))
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _data_integrity_hash(rows: Iterable[object]) -> str:
    h = hashlib.sha256()
    for r in rows:
        if hasattr(r, "__dataclass_fields__"):
            payload = sorted(asdict(r).items())  # type: ignore[arg-type]
        elif isinstance(r, dict):
            payload = sorted(r.items())
        else:
            payload = [("repr", repr(r))]
        h.update(str(payload).encode("utf-8"))
    return h.hexdigest()


def _synthetic_fallback() -> ReportData:
    """Used when the caller didn't precompute ``ReportData`` — keeps the
    generator usable from a shell / smoke-test without a populated DB."""

    return ReportData(
        stats_rows=(
            StatsRow("ph", "6.0-9.0 pH", 7.52, 8.1, 99.3, 1),
            StatsRow("turbidity", "≤ 5 NTU", 2.4, 19.8, 95.1, 4),
            StatsRow("conductivity", "≤ 500 uS/cm", 245, 468, 99.8, 0),
            StatsRow("pm25", "≤ 25 ug/m3", 12.1, 31.4, 97.6, 2),
            StatsRow("pm10", "≤ 50 ug/m3", 24.3, 49.2, 99.0, 1),
        ),
        exceedance_log=(),
        geohazard=GeohazardSummary(
            worst_tier="NORMAL",
            max_risk_score=0.21,
            evacuation_events=0,
            critical_events=0,
            slope_predictions_count=0,
        ),
        total_alerts=8,
        exceedance_count=8,
    )


def generate_report(
    report_id: str,
    site_name: str,
    period_start: datetime,
    period_end: datetime,
    report_type: str,
    data: ReportData | None = None,
) -> tuple[Path, str]:
    """Write a PDF and return (path, sha256-hash).

    ``data`` is the structured payload from :func:`collect_compliance_stats`.
    When absent, the renderer uses the synthetic fallback so an operator can
    still generate a PDF before any alerts have landed.
    """

    report_data = data or _synthetic_fallback()
    integrity = _data_integrity_hash(
        list(report_data.stats_rows)
        + list(report_data.exceedance_log)
        + [report_data.geohazard]
    )

    out_path = REPORTS_DIR / f"{report_id}.pdf"
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    story: list = []

    # Cover
    story.append(Paragraph("<b>GeoSentinel ESG Compliance Report</b>", styles["Title"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(f"<b>Site:</b> {site_name}", styles["Normal"]))
    story.append(
        Paragraph(
            f"<b>Period:</b> {period_start.date()} — {period_end.date()}",
            styles["Normal"],
        )
    )
    story.append(Paragraph(f"<b>Report type:</b> {report_type}", styles["Normal"]))
    story.append(
        Paragraph(
            f"<b>Generated:</b> {datetime.utcnow().isoformat()} UTC",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            f"<b>Data integrity (SHA-256):</b> <font face='Courier'>{integrity}</font>",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.6 * cm))

    # Executive Summary
    story.append(Paragraph("<b>Executive Summary</b>", styles["Heading2"]))
    story.append(Paragraph(_exec_summary(report_data), styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    # Compliance table
    story.append(Paragraph("<b>Parameter Compliance</b>", styles["Heading2"]))
    story.append(_compliance_table(report_data.stats_rows))
    story.append(PageBreak())

    # Exceedance log
    story.append(Paragraph("<b>Exceedance Event Log</b>", styles["Heading2"]))
    if report_data.exceedance_log:
        story.append(_exceedance_table(report_data.exceedance_log))
    else:
        story.append(
            Paragraph(
                "No CRITICAL or EVACUATION events during this period.",
                styles["Normal"],
            )
        )

    # Geohazard
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("<b>Geohazard Summary</b>", styles["Heading2"]))
    story.append(Paragraph(_geohazard_para(report_data.geohazard), styles["Normal"]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("<b>AI Model Performance</b>", styles["Heading2"]))
    story.append(
        Paragraph(
            "EnviroGuard and SlopeWatch precision/recall are tracked in MLflow; "
            "see the model registry for per-run metrics. Production models are "
            "Ed25519-signed and verified on load.",
            styles["Normal"],
        )
    )

    doc.build(story)
    out_path.write_bytes(buffer.getvalue())
    return out_path, integrity


# --- helpers ---------------------------------------------------------


def _exec_summary(data: ReportData) -> str:
    # Tone varies with the exceedance count — avoids the reviewer seeing
    # "exceeds 95 % compliance target" under a report that logged evacuations.
    if data.geohazard.evacuation_events > 0:
        headline = (
            f"The period recorded {data.geohazard.evacuation_events} EVACUATION-tier "
            "geohazard events. Mitigation actions are detailed in the event log."
        )
    elif data.exceedance_count == 0:
        headline = (
            "No IFC threshold exceedances were recorded during the period. "
            "All monitored parameters stayed within permitted bounds."
        )
    else:
        headline = (
            f"The period recorded {data.exceedance_count} IFC threshold exceedances "
            "across monitored parameters. Operational response is captured in the "
            "event log."
        )
    return (
        f"{headline} Of {data.total_alerts} total alerts logged, "
        f"{data.exceedance_count} reached CRITICAL or EVACUATION severity. AI-driven "
        "predictive alerts from EnviroGuard and SlopeWatch provide the lead-time "
        "basis for the preventive actions summarised below."
    )


def _compliance_table(rows: tuple[StatsRow, ...]) -> Table:
    header = ["Parameter", "IFC Limit", "Period Mean", "Period Max", "% Compliant", "Exceedances"]
    data: list[list[str]] = [header]
    for r in rows:
        data.append(
            [
                r.parameter,
                r.limit,
                f"{r.mean:.2f}" if isinstance(r.mean, float) else str(r.mean),
                f"{r.max:.2f}" if isinstance(r.max, float) else str(r.max),
                f"{r.compliant_pct:.1f}%",
                str(r.events),
            ]
        )
    t = Table(data, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F1F36")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
            ]
        )
    )
    return t


def _exceedance_table(log: tuple[ExceedanceLogRow, ...]) -> Table:
    header = ["Timestamp (UTC)", "Node", "Parameter", "Severity", "Value", "Threshold", "Ack"]
    data: list[list[str]] = [header]
    for r in log:
        data.append(
            [
                r.timestamp.strftime("%Y-%m-%d %H:%M"),
                r.node_id,
                r.parameter,
                r.severity,
                f"{r.value:.2f}" if r.value is not None else "—",
                f"{r.threshold:.2f}" if r.threshold is not None else "—",
                "yes" if r.acknowledged else "no",
            ]
        )
    t = Table(data, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7A1F1F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
            ]
        )
    )
    return t


def _geohazard_para(g: GeohazardSummary) -> str:
    if g.slope_predictions_count == 0:
        return (
            "No SlopeWatch predictions were recorded for this period. The preceding "
            "summary reflects telemetry-driven compliance only."
        )
    return (
        f"SlopeWatch recorded {g.slope_predictions_count} predictions in the period. "
        f"Peak risk score {g.max_risk_score:.2f}; worst alert tier reached: "
        f"<b>{g.worst_tier}</b>. Critical geohazard alerts: {g.critical_events}; "
        f"evacuation-tier events: {g.evacuation_events}."
    )
