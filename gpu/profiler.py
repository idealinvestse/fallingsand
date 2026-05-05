"""Minimal pass profiler for GPU compute dispatch timings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
import time


@dataclass(slots=True)
class PassTiming:
    """Timing data for a single compute pass dispatch."""

    name: str
    elapsed_ms: float = 0.0
    calls: int = 0


@dataclass
class PassProfiler:
    """Tracks per-pass GPU dispatch timings without changing dispatch order."""

    _timings: dict[str, PassTiming] = field(default_factory=dict)

    def record(self, name: str, elapsed_ms: float) -> None:
        if name not in self._timings:
            self._timings[name] = PassTiming(name=name)
        t = self._timings[name]
        t.elapsed_ms = elapsed_ms
        t.calls += 1

    def get(self, name: str) -> PassTiming | None:
        return self._timings.get(name)

    def get_all(self) -> dict[str, PassTiming]:
        return dict(self._timings)

    def reset(self) -> None:
        self._timings.clear()

    def total_step_ms(self) -> float:
        return sum(t.elapsed_ms for t in self._timings.values())

    def timed_pass_names(self) -> tuple[str, ...]:
        return tuple(self._timings.keys())

    @staticmethod
    def measure(fn: Callable[[], None]) -> float:
        """Run *fn* and return elapsed wall-clock milliseconds."""
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0
