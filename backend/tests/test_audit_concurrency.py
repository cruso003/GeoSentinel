"""Audit chain concurrency guard (Phase 2.1 §9 follow-up).

The brutal review found that ``services.audit.record`` read
``_latest_hash`` and wrote the new row without any locking.  Two writers
that both read the same ``prev`` would both insert rows claiming it as
their predecessor, and ``verify_chain`` — which recomputes forward from
each row's stored ``prev_hash`` — would deterministically flag the
second-committed row as a broken chain.  On any busy system (login +
alert-ack within a millisecond) the chain's own verifier would then
falsely cry tamper.

The fix is a Postgres transaction-scoped advisory lock taken BEFORE the
``_latest_hash`` read.  SQLite tests see a no-op because SQLite
serialises writers natively; the lock only matters under Postgres.

These tests pin the call order (lock then read) and the dialect
dispatch, so a refactor that re-orders either falls at CI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("sqlalchemy")

from app.services import audit as audit_service  # noqa: E402


class _FakeUser:
    email = "op@site.io"
    role = "operator"


class _StubResult:
    def scalar_one_or_none(self):
        return None


def _mock_session(dialect_name: str) -> MagicMock:
    """Return an AsyncSession-shaped mock whose ``execute`` records every
    SQL text it was handed, so we can assert ordering.
    """

    calls: list[str] = []

    async def _execute(stmt, params=None):
        rendered = str(stmt)
        calls.append(rendered)
        return _StubResult()

    async def _flush():
        return None

    sess = MagicMock()
    sess.bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))
    sess.execute = AsyncMock(side_effect=_execute)
    sess.flush = AsyncMock(side_effect=_flush)
    sess.add = MagicMock()
    sess._calls = calls  # inspection handle for assertions
    return sess


@pytest.mark.asyncio
async def test_acquire_chain_lock_runs_pg_advisory_on_postgres():
    sess = _mock_session("postgresql")
    await audit_service._acquire_chain_lock(sess)
    assert any("pg_advisory_xact_lock" in c for c in sess._calls), (
        f"expected pg_advisory_xact_lock call, got: {sess._calls}"
    )


@pytest.mark.asyncio
async def test_acquire_chain_lock_is_noop_on_sqlite():
    sess = _mock_session("sqlite")
    await audit_service._acquire_chain_lock(sess)
    assert sess._calls == [], (
        f"SQLite dialect must not emit an advisory lock, got: {sess._calls}"
    )


@pytest.mark.asyncio
async def test_record_takes_lock_before_reading_latest_hash():
    """The core invariant: the lock MUST be acquired before the SELECT
    that reads ``_latest_hash``, otherwise two concurrent writers can
    read the same ``prev``. Any refactor that reorders this fails here.
    """

    sess = _mock_session("postgresql")

    await audit_service.record(
        sess,
        user=_FakeUser(),
        action="test.action",
        target_type="audit",
        target_id="t-1",
        details="race-check",
    )

    # Collect indices of the lock call and the first SELECT against
    # audit_log.  Both must exist; lock must come first.
    try:
        lock_idx = next(
            i for i, c in enumerate(sess._calls) if "pg_advisory_xact_lock" in c
        )
    except StopIteration:  # pragma: no cover - test failure message
        pytest.fail(f"advisory lock was never acquired; calls={sess._calls}")

    try:
        select_idx = next(
            i
            for i, c in enumerate(sess._calls)
            if "audit_log" in c.lower() and "pg_advisory_xact_lock" not in c
        )
    except StopIteration:  # pragma: no cover
        pytest.fail(f"_latest_hash SELECT was never issued; calls={sess._calls}")

    assert lock_idx < select_idx, (
        "advisory lock must be taken BEFORE the _latest_hash SELECT. "
        f"calls={sess._calls}"
    )


@pytest.mark.asyncio
async def test_record_sets_prev_hash_from_latest_and_computes_row_hash():
    """Sanity check that the lock didn't accidentally change the body of
    ``record`` — it still populates prev_hash + row_hash and flushes."""

    sess = _mock_session("postgresql")
    before = datetime.now(timezone.utc)

    entry = await audit_service.record(
        sess,
        user=_FakeUser(),
        action="test.action",
    )

    assert entry.row_hash and len(entry.row_hash) == 64  # sha256 hex
    assert entry.actor_email == "op@site.io"
    assert entry.actor_role == "operator"
    assert entry.action == "test.action"
    assert entry.created_at >= before
    sess.add.assert_called_once()
    sess.flush.assert_awaited_once()
