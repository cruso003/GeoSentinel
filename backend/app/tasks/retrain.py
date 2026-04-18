"""Weekly retraining scaffold (Phase 2.4 §5).

This task is a **scaffold**. It doesn't run TensorFlow training inside
the Celery worker (the default backend image doesn't ship TF, and the
one that does is GPU-bound). What it does do:

  1. Check ``settings.enable_retrain_loop`` — if False, log and return.
     That keeps this cheap to leave in the beat schedule.
  2. If enabled, shell out to ``python -m ai.enviroguard.train`` /
     ``ai.slopewatch.train``, capturing stdout for the audit log.
  3. Let the train script register a candidate via ``ai/promote.py``.
     Promotion itself goes through the gated API endpoint, so the Celery
     task never blesses a model on its own.

Wiring retraining to the Celery beat means cadence lives in one place
(``celery_app.py``) rather than cron + CI + operator memory.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys

from ..core.config import get_settings
from ..core.db import SessionLocal
from ..models.user import User
from ..services import audit
from .celery_app import celery_app

log = logging.getLogger(__name__)

# Pseudo-user for audit attribution when a scheduled task (not a human)
# triggers a retrain. The hash chain still verifies; the email makes the
# provenance obvious in the UI.
_SYSTEM_USER = User(
    id="system-retrain",
    email="system@geosentinel.internal",
    role="esg_admin",
    name="retraining scheduler",
    hashed_password="-",
)


async def _record_retrain(model: str, outcome: str, details: str) -> None:
    async with SessionLocal() as db:
        await audit.record(
            db,
            user=_SYSTEM_USER,
            action=f"retrain_{outcome}",
            target_type="model",
            target_id=model,
            details=details[:500],
        )
        await db.commit()


def _run_trainer(model: str) -> tuple[bool, str]:
    """Invoke the trainer as a subprocess. Capturing stdout/stderr and
    bounding the timeout keeps a runaway fit from pinning the worker."""

    cmd = [sys.executable, "-m", f"ai.{model}.train"]
    try:
        result = subprocess.run(  # noqa: S603 — argv is fixed, not user-supplied
            cmd,
            capture_output=True,
            text=True,
            timeout=60 * 60,  # 1 h hard ceiling; real training rarely exceeds
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        return False, f"timeout: {e}"
    ok = result.returncode == 0
    # Trim — the audit row caps at 500 chars anyway, and trailer lines
    # are usually the useful ones (metrics, artifact paths).
    tail = (result.stdout or "").splitlines()[-8:] + (result.stderr or "").splitlines()[-4:]
    return ok, "\n".join(tail)


@celery_app.task(
    name="app.tasks.retrain.sweep_retrain",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    time_limit=60 * 60 + 300,
)
def sweep_retrain() -> dict:
    settings = get_settings()
    if not settings.enable_retrain_loop:
        log.info("Retrain loop disabled (enable_retrain_loop=False); skipping.")
        return {"skipped": True, "reason": "disabled"}

    outcomes: dict[str, dict] = {}
    for model in ("enviroguard", "slopewatch"):
        ok, trail = _run_trainer(model)
        outcomes[model] = {"ok": ok, "trail": trail}
        asyncio.run(
            _record_retrain(model, "succeeded" if ok else "failed", trail)
        )
    return outcomes
