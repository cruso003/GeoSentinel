"""In-process Prometheus collector (Phase 2.2)."""

import pytest

from app.services import metrics


@pytest.fixture(autouse=True)
def _reset():
    metrics.reset_for_tests()
    yield
    metrics.reset_for_tests()


def test_counter_increments():
    c = metrics.counter("test_counter", "help")
    c.inc()
    c.inc(2.0)
    out = metrics.render()
    assert "test_counter 3.0" in out
    assert "# TYPE test_counter counter" in out


def test_counter_with_labels():
    c = metrics.counter("labelled", "labels")
    c.inc(kind="env")
    c.inc(kind="geo")
    c.inc(kind="env")
    out = metrics.render()
    assert 'labelled{kind="env"} 2.0' in out
    assert 'labelled{kind="geo"} 1.0' in out


def test_gauge_set_and_inc():
    g = metrics.gauge("pressure", "help")
    g.set(5, site_id="tokadeh")
    assert 'pressure{site_id="tokadeh"} 5' in metrics.render()
    g.inc(site_id="tokadeh")
    assert 'pressure{site_id="tokadeh"} 6' in metrics.render()
    g.dec(site_id="tokadeh")
    assert 'pressure{site_id="tokadeh"} 5' in metrics.render()


def test_histogram_buckets():
    h = metrics.histogram("latency", "seconds", buckets=(0.1, 0.5, 1))
    h.observe(0.05)
    h.observe(0.3)
    h.observe(0.9)
    out = metrics.render()
    assert 'latency_bucket{le="0.1"} 1' in out
    assert 'latency_bucket{le="0.5"} 2' in out
    assert 'latency_bucket{le="1.0"} 3' in out
    assert "latency_count 3" in out


def test_label_escaping():
    c = metrics.counter("esc", "help")
    c.inc(path='/a"b\\c')
    out = metrics.render()
    # Quotes and backslashes must be escaped.
    assert '\\"b\\\\c' in out


def test_render_includes_help_and_type():
    metrics.counter("with_help", "describes it")
    out = metrics.render()
    assert "# HELP with_help describes it" in out
    assert "# TYPE with_help counter" in out


def test_counter_returns_same_instance_on_reregister():
    a = metrics.counter("shared", "help")
    b = metrics.counter("shared", "different help")
    assert a is b
