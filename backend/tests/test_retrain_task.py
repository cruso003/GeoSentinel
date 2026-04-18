"""Retrain Celery task scaffold (Phase 2.4 §5).

The task body has two branches worth locking down: disabled → no-op,
enabled → subprocess invocation. We skip the enabled branch's
subprocess since it shells out to the TF-heavy trainer; what matters is
that the flag switches cleanly.
"""

from __future__ import annotations

import pytest

pytest.importorskip("celery")

from app.tasks import retrain


def test_sweep_retrain_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_RETRAIN_LOOP", "false")
    # Clear the settings cache so the new env takes effect.
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        result = retrain.sweep_retrain.run()  # .run() bypasses the broker
    finally:
        get_settings.cache_clear()
    assert result == {"skipped": True, "reason": "disabled"}
