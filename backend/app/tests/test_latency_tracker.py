"""Tests for the process-global observed-latency EWMA (latency_tracker)."""
import pytest

from app.services import latency_tracker


@pytest.fixture(autouse=True)
def _clean():
    latency_tracker.reset_for_tests()
    yield
    latency_tracker.reset_for_tests()


def test_unknown_is_zero():
    assert latency_tracker.observed_latency_s() == 0.0


def test_first_sample_seeds_directly():
    latency_tracker.record_latency(10.0)
    assert latency_tracker.observed_latency_s() == 10.0


def test_ewma_smooths_subsequent_samples():
    latency_tracker.record_latency(10.0)
    latency_tracker.record_latency(20.0)
    # 0.7 * 10 + 0.3 * 20 = 13.0
    assert latency_tracker.observed_latency_s() == pytest.approx(13.0)


def test_non_positive_samples_ignored():
    latency_tracker.record_latency(10.0)
    latency_tracker.record_latency(0.0)
    latency_tracker.record_latency(-5.0)
    assert latency_tracker.observed_latency_s() == 10.0


def test_reset_clears_estimate():
    latency_tracker.record_latency(10.0)
    latency_tracker.reset_for_tests()
    assert latency_tracker.observed_latency_s() == 0.0
