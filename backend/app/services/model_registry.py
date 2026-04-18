"""Model registry + promotion gate (Phase 2.4 §5).

The gate is a small pure function so it's unit-testable without a DB:

  - Candidate must beat production on ROC-AUC by at least
    ``MIN_AUC_IMPROVEMENT`` (defaults to 0 — no regression).
  - Candidate must not regress on PR-AUC by more than
    ``MAX_PR_AUC_REGRESSION`` (2 % per the roadmap).
  - Per-slice AUC (when reported as ``slice_aucs: {slice: auc}``) must
    not regress more than ``MAX_SLICE_AUC_REGRESSION`` (also 2 %).
  - First-ever production row is a free promotion — there's no
    incumbent to compare against.

Promotions land in the hash-chain audit log so every model swap is
provably traceable to a user and a timestamp.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.model_version import ModelVersion
from ..models.user import User
from . import audit

# Tunables — surface as settings if a customer ever asks for a stricter
# gate. The defaults match the roadmap; changing them is a conscious
# decision, not a per-environment switch.
MIN_AUC_IMPROVEMENT = 0.0
MAX_PR_AUC_REGRESSION = 0.02
MAX_SLICE_AUC_REGRESSION = 0.02

STAGES = ("candidate", "staging", "production", "archived")


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return {"passed": self.passed, "reasons": list(self.reasons)}


def _get(metrics: dict, key: str) -> float | None:
    v = metrics.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def evaluate_gate(
    candidate: dict[str, Any], incumbent: dict[str, Any] | None
) -> GateResult:
    """Decide whether ``candidate`` should replace ``incumbent``.

    Both arguments are metric dicts (as produced by
    ``services.evaluation.compute_metrics().as_dict()`` or
    ``evaluate_with_slices`` with an added ``slice_aucs`` dict). When
    ``incumbent`` is ``None`` the candidate always wins — first promotion
    is unconditional.
    """

    reasons: list[str] = []

    cand_auc = _get(candidate, "roc_auc")
    if cand_auc is None:
        return GateResult(
            False, ("candidate metrics missing roc_auc",)
        )

    if incumbent is None:
        return GateResult(True, ("no incumbent; first-ever promotion",))

    inc_auc = _get(incumbent, "roc_auc")
    if inc_auc is not None and cand_auc < inc_auc + MIN_AUC_IMPROVEMENT:
        reasons.append(
            f"roc_auc regression: {cand_auc:.4f} < {inc_auc:.4f} + "
            f"{MIN_AUC_IMPROVEMENT:.4f}"
        )

    cand_pr = _get(candidate, "pr_auc")
    inc_pr = _get(incumbent, "pr_auc")
    if (
        cand_pr is not None
        and inc_pr is not None
        and cand_pr < inc_pr - MAX_PR_AUC_REGRESSION
    ):
        reasons.append(
            f"pr_auc regression > {MAX_PR_AUC_REGRESSION:.2%}: "
            f"{cand_pr:.4f} vs {inc_pr:.4f}"
        )

    cand_slices = candidate.get("slice_aucs") or {}
    inc_slices = incumbent.get("slice_aucs") or {}
    for slice_label, inc_val in inc_slices.items():
        cand_val = cand_slices.get(slice_label)
        if cand_val is None or inc_val is None:
            continue
        if float(cand_val) < float(inc_val) - MAX_SLICE_AUC_REGRESSION:
            reasons.append(
                f"slice {slice_label!r} regressed > "
                f"{MAX_SLICE_AUC_REGRESSION:.2%}: "
                f"{cand_val:.4f} vs {inc_val:.4f}"
            )

    if not reasons:
        return GateResult(True, ("all gates passed",))
    return GateResult(False, tuple(reasons))


async def register_candidate(
    db: AsyncSession,
    *,
    name: str,
    version: str,
    metrics: dict[str, Any],
    data_sha256: str | None = None,
    artifact_uri: str | None = None,
    mlflow_run_id: str | None = None,
) -> ModelVersion:
    """Insert a candidate row. Idempotent on ``(name, version)`` — if a
    row already exists we update its metrics rather than raising, so
    re-running a failed promotion isn't a landmine."""

    existing = (
        await db.execute(
            select(ModelVersion).where(
                ModelVersion.name == name, ModelVersion.version == version
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.metrics_json = json.dumps(metrics, sort_keys=True)
        existing.data_sha256 = data_sha256 or existing.data_sha256
        existing.artifact_uri = artifact_uri or existing.artifact_uri
        existing.mlflow_run_id = mlflow_run_id or existing.mlflow_run_id
        return existing

    row = ModelVersion(
        name=name,
        version=version,
        stage="candidate",
        data_sha256=data_sha256,
        artifact_uri=artifact_uri,
        mlflow_run_id=mlflow_run_id,
        metrics_json=json.dumps(metrics, sort_keys=True),
    )
    db.add(row)
    await db.flush()
    return row


async def get_production(
    db: AsyncSession, name: str
) -> ModelVersion | None:
    return (
        await db.execute(
            select(ModelVersion).where(
                ModelVersion.name == name, ModelVersion.stage == "production"
            )
        )
    ).scalar_one_or_none()


async def get_version(
    db: AsyncSession, version_id: str
) -> ModelVersion | None:
    return await db.get(ModelVersion, version_id)


async def promote(
    db: AsyncSession,
    *,
    version: ModelVersion,
    user: User,
    force: bool = False,
) -> dict:
    """Apply the gate and, if it passes (or ``force`` is set), rotate
    production → archived and this row → production. Always writes an
    audit entry — including rejected attempts, so a reviewer can see
    when someone tried to bypass the gate."""

    candidate_metrics = json.loads(version.metrics_json or "{}")
    current = await get_production(db, version.name)
    incumbent_metrics = (
        json.loads(current.metrics_json) if current and current.metrics_json else None
    )
    gate = evaluate_gate(candidate_metrics, incumbent_metrics)

    if not gate.passed and not force:
        await audit.record(
            db,
            user=user,
            action="promote_model_rejected",
            target_type="model_version",
            target_id=version.id,
            details=(
                f"name={version.name};version={version.version};"
                f"reasons={'; '.join(gate.reasons)}"
            ),
        )
        return {"promoted": False, "gate": gate.as_dict()}

    now = datetime.now(UTC)
    if current is not None and current.id != version.id:
        current.stage = "archived"
    version.stage = "production"
    version.promoted_at = now
    version.promoted_by = user.email

    await audit.record(
        db,
        user=user,
        action="promote_model" if gate.passed else "promote_model_forced",
        target_type="model_version",
        target_id=version.id,
        details=(
            f"name={version.name};version={version.version};"
            f"previous={current.version if current else 'none'};"
            f"reasons={'; '.join(gate.reasons)}"
        ),
    )
    return {"promoted": True, "gate": gate.as_dict()}
