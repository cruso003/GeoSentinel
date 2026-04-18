"""Broadcast concurrency + slow-client pruning (Phase 2.2 S13)."""

import asyncio

import pytest

pytest.importorskip("fastapi")

from app.services import ws_hub


class _FakeSocket:
    def __init__(self, *, delay: float = 0.0, fail: bool = False):
        self.delay = delay
        self.fail = fail
        self.sent: list[dict] = []

    async def send_json(self, msg):
        if self.fail:
            raise RuntimeError("peer gone")
        if self.delay:
            await asyncio.sleep(self.delay)
        self.sent.append(msg)


@pytest.fixture
def hub():
    h = ws_hub.WSHub()
    yield h


@pytest.mark.asyncio
async def test_broadcast_empty_site_is_noop(hub):
    # Should not raise, even with no subscribers.
    await hub.broadcast("empty", {"type": "NOOP"})


@pytest.mark.asyncio
async def test_broadcast_fans_out_to_all(hub):
    a, b, c = _FakeSocket(), _FakeSocket(), _FakeSocket()
    hub._subs["s1"].update({a, b, c})
    await hub.broadcast("s1", {"type": "X"})
    assert a.sent == [{"type": "X"}]
    assert b.sent == [{"type": "X"}]
    assert c.sent == [{"type": "X"}]


@pytest.mark.asyncio
async def test_broadcast_prunes_failing_client(hub):
    good = _FakeSocket()
    dead = _FakeSocket(fail=True)
    hub._subs["s1"].update({good, dead})
    await hub.broadcast("s1", {"type": "X"})
    assert good.sent
    assert dead not in hub._subs["s1"]
    assert good in hub._subs["s1"]


@pytest.mark.asyncio
async def test_broadcast_prunes_slow_client(hub, monkeypatch):
    monkeypatch.setattr(ws_hub, "_SEND_TIMEOUT_S", 0.05)
    good = _FakeSocket()
    slow = _FakeSocket(delay=0.5)
    hub._subs["s1"].update({good, slow})
    await hub.broadcast("s1", {"type": "X"})
    assert good.sent  # fast client delivered
    assert slow not in hub._subs["s1"]  # slow client got pruned


@pytest.mark.asyncio
async def test_broadcast_slow_does_not_block_fast(hub, monkeypatch):
    monkeypatch.setattr(ws_hub, "_SEND_TIMEOUT_S", 0.2)
    fast = _FakeSocket()
    slow = _FakeSocket(delay=0.15)
    hub._subs["s1"].update({fast, slow})
    start = asyncio.get_event_loop().time()
    await hub.broadcast("s1", {"type": "X"})
    elapsed = asyncio.get_event_loop().time() - start
    # Serial would be >=0.15s; concurrent should complete close to 0.15s,
    # definitely not >=0.30s. Give a generous ceiling for CI jitter.
    assert elapsed < 0.28
    assert fast.sent


def test_subscriber_count(hub):
    assert hub.subscriber_count("nope") == 0
    hub._subs["s1"].update({_FakeSocket(), _FakeSocket()})
    assert hub.subscriber_count("s1") == 2
