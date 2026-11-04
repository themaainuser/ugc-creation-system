"""Tests for the JEV calibrated decision seam (tdd: one slice per test)."""
from ugc_system.core.decisions import decide, score_proper


def test_decide_returns_distribution_with_confidence_and_gate():
    d = decide("verdict", {"a": 2.0, "b": 0.5}, lambda n: (0, []))
    assert d.chosen in ("a", "b")
    assert abs(sum(o.p_calibrated for o in d.options) - 1.0) < 1e-6
    assert d.gate in ("automate", "escalate")
    assert 0 < d.confidence < 1
    assert d.brier_estimate >= 0


def test_high_confidence_automates_low_confidence_escalates():
    strong = decide("verdict", {"a": 5.0, "b": -2.0}, lambda n: (0, []))
    weak = decide("verdict", {"a": 0.1, "b": 0.0}, lambda n: (0, []))
    assert strong.confidence > weak.confidence
    assert strong.gate == "automate"
    assert weak.gate == "escalate"


def test_brier_rewards_calibrated_confidence():
    # outcomes: well-calibrated confident decision vs overconfident wrong
    good = decide("x", {"a": 2.2, "b": 0.1}, lambda n: (0, []))
    assert score_proper(good, "a") < 0.25
    assert score_proper(good, "b") > 0.30
