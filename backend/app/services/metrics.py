"""Minimal Prometheus collector (Phase 2.2).

Stdlib-only, thread-safe counters + gauges + histograms. The /metrics
route renders the registry in Prometheus text exposition format. We keep
this in-process rather than pulling prometheus_client to avoid a new dep
and to keep the memory profile of the backend image flat — the registry
is tiny and enough for the counters listed in the roadmap.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Iterable

_lock = threading.Lock()


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{_escape_label(v)}"' for k, v in labels)
    return "{" + inner + "}"


@dataclass
class _Series:
    value: float = 0.0
    buckets: dict[float, int] = field(default_factory=dict)  # histogram only
    count: int = 0  # histogram only
    sum: float = 0.0  # histogram only


class _Metric:
    def __init__(self, name: str, help_text: str, mtype: str) -> None:
        self.name = name
        self.help = help_text
        self.type = mtype  # "counter" | "gauge" | "histogram"
        self.series: dict[tuple[tuple[str, str], ...], _Series] = {}

    def _key(self, labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def _get(self, key) -> _Series:
        s = self.series.get(key)
        if s is None:
            s = _Series()
            self.series[key] = s
        return s


class Counter(_Metric):
    def inc(self, amount: float = 1.0, **labels: str) -> None:
        with _lock:
            self._get(self._key(labels)).value += amount


class Gauge(_Metric):
    def set(self, value: float, **labels: str) -> None:
        with _lock:
            self._get(self._key(labels)).value = value

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        with _lock:
            self._get(self._key(labels)).value += amount

    def dec(self, amount: float = 1.0, **labels: str) -> None:
        with _lock:
            self._get(self._key(labels)).value -= amount


DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)


class Histogram(_Metric):
    def __init__(self, name: str, help_text: str, buckets: Iterable[float] = DEFAULT_BUCKETS) -> None:
        super().__init__(name, help_text, "histogram")
        self.bucket_edges = tuple(sorted(float(b) for b in buckets))

    def observe(self, value: float, **labels: str) -> None:
        with _lock:
            s = self._get(self._key(labels))
            if not s.buckets:
                s.buckets = {b: 0 for b in self.bucket_edges}
            for edge in self.bucket_edges:
                if value <= edge:
                    s.buckets[edge] += 1
            s.sum += value
            s.count += 1


class _Registry:
    def __init__(self) -> None:
        self._metrics: dict[str, _Metric] = {}

    def register(self, metric: _Metric) -> _Metric:
        existing = self._metrics.get(metric.name)
        if existing is not None:
            return existing
        self._metrics[metric.name] = metric
        return metric

    def render(self) -> str:
        lines: list[str] = []
        for m in self._metrics.values():
            lines.append(f"# HELP {m.name} {m.help}")
            lines.append(f"# TYPE {m.name} {m.type}")
            if m.type == "histogram":
                for key, s in m.series.items():
                    for edge in sorted(s.buckets):
                        labels = dict(key)
                        labels["le"] = ("+Inf" if edge == float("inf") else str(edge))
                        lines.append(
                            f"{m.name}_bucket{_format_labels(tuple(sorted(labels.items())))} {s.buckets[edge]}"
                        )
                    inf_labels = dict(key)
                    inf_labels["le"] = "+Inf"
                    lines.append(
                        f"{m.name}_bucket{_format_labels(tuple(sorted(inf_labels.items())))} {s.count}"
                    )
                    lines.append(f"{m.name}_sum{_format_labels(key)} {s.sum}")
                    lines.append(f"{m.name}_count{_format_labels(key)} {s.count}")
            else:
                for key, s in m.series.items():
                    lines.append(f"{m.name}{_format_labels(key)} {s.value}")
        return "\n".join(lines) + "\n"


REGISTRY = _Registry()


def counter(name: str, help_text: str) -> Counter:
    return REGISTRY.register(Counter(name, help_text, "counter"))  # type: ignore[return-value]


def gauge(name: str, help_text: str) -> Gauge:
    return REGISTRY.register(Gauge(name, help_text, "gauge"))  # type: ignore[return-value]


def histogram(name: str, help_text: str, buckets: Iterable[float] = DEFAULT_BUCKETS) -> Histogram:
    return REGISTRY.register(Histogram(name, help_text, buckets))  # type: ignore[return-value]


def render() -> str:
    return REGISTRY.render()


# Canonical metrics used across the app. Keep names aligned with the roadmap.
alerts_emitted_total = counter(
    "gs_alerts_emitted_total", "Alerts generated by the alert engine."
)
ingest_rows_total = counter(
    "gs_ingest_rows_total", "Sensor readings accepted at /sensors/ingest."
)
ai_inference_seconds = histogram(
    "gs_ai_inference_seconds", "Wall-clock time spent in AI inference."
)
ws_subscribers = gauge(
    "gs_ws_subscribers", "Current subscribers per site on the WebSocket hub."
)
login_failures_total = counter(
    "gs_login_failures_total", "Failed /auth/login attempts (bad creds or rate-limited)."
)


def reset_for_tests() -> None:
    with _lock:
        for m in REGISTRY._metrics.values():
            m.series.clear()
