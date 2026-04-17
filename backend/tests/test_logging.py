"""Structured JSON logging (Phase 2.2)."""

import io
import json
import logging

import pytest

from app.core import logging as gs_logging


@pytest.fixture
def capture():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(gs_logging.JsonFormatter())
    root = logging.getLogger("gs.test")
    root.handlers = [handler]
    root.setLevel("DEBUG")
    root.propagate = False
    yield root, buf
    root.handlers = []


def _last_record(buf: io.StringIO) -> dict:
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    return json.loads(lines[-1])


def test_basic_record_has_fields(capture):
    logger, buf = capture
    logger.info("hello")
    rec = _last_record(buf)
    assert rec["level"] == "INFO"
    assert rec["msg"] == "hello"
    assert rec["logger"] == "gs.test"
    assert "ts" in rec


def test_extras_are_included(capture):
    logger, buf = capture
    logger.info("boom", extra={"node_id": "env-02", "count": 3})
    rec = _last_record(buf)
    assert rec["node_id"] == "env-02"
    assert rec["count"] == 3


def test_request_id_flows_through_contextvar(capture):
    logger, buf = capture
    token = gs_logging.request_id_var.set("req-abc")
    try:
        logger.info("inside")
    finally:
        gs_logging.request_id_var.reset(token)
    rec = _last_record(buf)
    assert rec["request_id"] == "req-abc"


def test_non_serialisable_extras_coerced_to_repr(capture):
    logger, buf = capture

    class Exotic:
        def __repr__(self) -> str:
            return "<Exotic>"

    logger.info("x", extra={"obj": Exotic()})
    rec = _last_record(buf)
    assert rec["obj"] == "<Exotic>"


def test_exception_info_included(capture):
    logger, buf = capture
    try:
        raise RuntimeError("kaboom")
    except RuntimeError:
        logger.exception("failed")
    rec = _last_record(buf)
    assert "kaboom" in rec["exc_info"]
