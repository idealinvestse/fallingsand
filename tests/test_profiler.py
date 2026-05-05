"""Tests for the GPU pass profiler."""

import time

from gpu.profiler import PassProfiler, PassTiming


class TestPassProfiler:
    def test_record_and_get(self):
        p = PassProfiler()
        p.record("state", 1.5)
        t = p.get("state")
        assert isinstance(t, PassTiming)
        assert t.name == "state"
        assert t.elapsed_ms == 1.5
        assert t.calls == 1

    def test_multiple_records_accumulate_calls(self):
        p = PassProfiler()
        p.record("heat", 0.5)
        p.record("heat", 1.0)
        t = p.get("heat")
        assert t.calls == 2
        assert t.elapsed_ms == 1.0  # last write wins

    def test_total_step_ms_sums_last_values(self):
        p = PassProfiler()
        p.record("a", 1.0)
        p.record("b", 2.5)
        assert p.total_step_ms() == 3.5

    def test_timed_pass_names_returns_keys(self):
        p = PassProfiler()
        p.record("state", 1.0)
        p.record("force", 2.0)
        assert p.timed_pass_names() == ("state", "force")

    def test_reset_clears(self):
        p = PassProfiler()
        p.record("x", 1.0)
        p.reset()
        assert p.get("x") is None
        assert p.total_step_ms() == 0.0

    def test_measure_runs_and_returns_non_negative(self):
        p = PassProfiler()
        elapsed = p.measure(lambda: time.sleep(0.001))
        assert elapsed >= 0.0
        assert isinstance(elapsed, float)

    def test_get_all_returns_copy(self):
        p = PassProfiler()
        p.record("state", 1.0)
        all_timings = p.get_all()
        assert all_timings == {"state": PassTiming("state", 1.0, 1)}
        # mutate returned dict should not affect profiler
        all_timings.clear()
        assert p.get("state") is not None
