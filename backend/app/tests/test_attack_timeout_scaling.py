"""Tests for attack-engine timeout sizing (engine_utils.scaled_timeout).

Two layers are exercised:

* the static ``attack_timeout_multiplier`` manual floor/override, and
* the adaptive sizing that derives a factor from the observed model latency.

With the default config and no observed latency, every timeout must be left
unchanged so the attack engine behaves exactly as before unless an operator
opts in or the live model is measurably slow.
"""
import pytest

from app.config import settings
from app.services import latency_tracker
from app.services.engine_utils import scaled_timeout


@pytest.fixture(autouse=True)
def _clean_latency():
    latency_tracker.reset_for_tests()
    yield
    latency_tracker.reset_for_tests()


def test_default_is_identity_without_observed_latency():
    assert settings.attack_timeout_multiplier == 1.0
    assert settings.attack_timeout_adaptive is True
    assert scaled_timeout(12.0) == 12.0
    assert scaled_timeout(8.0) == 8.0


def test_manual_multiplier_acts_as_floor(monkeypatch):
    monkeypatch.setattr(settings, "attack_timeout_multiplier", 4.0)
    assert scaled_timeout(12.0) == 48.0
    assert scaled_timeout(30.0) == 120.0


def test_non_positive_multiplier_falls_back_to_base(monkeypatch):
    monkeypatch.setattr(settings, "attack_timeout_multiplier", 0.0)
    assert scaled_timeout(12.0) == 12.0
    monkeypatch.setattr(settings, "attack_timeout_multiplier", -3.0)
    assert scaled_timeout(12.0) == 12.0


def test_fast_model_latency_does_not_shorten(monkeypatch):
    # Observed latency at/under the reference must not change the base timeout.
    monkeypatch.setattr(settings, "attack_timeout_reference_latency_s", 4.0)
    latency_tracker.record_latency(2.0)
    assert scaled_timeout(12.0) == 12.0


def test_slow_model_latency_scales_up(monkeypatch):
    monkeypatch.setattr(settings, "attack_timeout_reference_latency_s", 4.0)
    monkeypatch.setattr(settings, "attack_timeout_max_factor", 6.0)
    # 24s observed / 4s reference => factor 6.0 (also at the cap).
    latency_tracker.record_latency(24.0)
    assert scaled_timeout(12.0) == pytest.approx(72.0)


def test_max_factor_caps_runaway_latency(monkeypatch):
    monkeypatch.setattr(settings, "attack_timeout_reference_latency_s", 4.0)
    monkeypatch.setattr(settings, "attack_timeout_max_factor", 6.0)
    latency_tracker.record_latency(400.0)  # a near-timeout/stuck call
    assert scaled_timeout(12.0) == pytest.approx(72.0)


def test_adaptive_disabled_uses_only_multiplier(monkeypatch):
    monkeypatch.setattr(settings, "attack_timeout_adaptive", False)
    latency_tracker.record_latency(60.0)
    assert scaled_timeout(12.0) == 12.0  # latency ignored when adaptive off


def test_adaptive_and_manual_take_the_larger(monkeypatch):
    monkeypatch.setattr(settings, "attack_timeout_reference_latency_s", 4.0)
    monkeypatch.setattr(settings, "attack_timeout_max_factor", 6.0)
    monkeypatch.setattr(settings, "attack_timeout_multiplier", 5.0)
    # observed factor = 8/4 = 2.0 < manual 5.0 -> manual wins
    latency_tracker.record_latency(8.0)
    assert scaled_timeout(12.0) == 60.0
