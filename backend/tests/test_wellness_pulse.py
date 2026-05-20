"""Wellness Pulse tests — observational discipline + confidence-limited copy."""
from wellness_pulse import compose_pulse, MIN_MED_COMPLETIONS, MIN_REHAB_COMPLETIONS, MIN_TURNOUT_MOVES


def _ev(category: str, outcome: str = "completed") -> dict:
    return {"category": category, "event_type": f"task.{outcome}"}


def test_empty_events_stays_quiet():
    assert compose_pulse("Halo", []) is None


def test_low_sample_stays_quiet():
    """Below the confidence threshold → no observation."""
    events = [_ev("medication") for _ in range(MIN_MED_COMPLETIONS - 1)]
    assert compose_pulse("Halo", events) is None


def test_med_consistency_when_zero_skips():
    events = [_ev("medication") for _ in range(MIN_MED_COMPLETIONS)]
    line = compose_pulse("Halo", events)
    assert line is not None
    assert "medication adherence" in line
    assert "consistent this week" in line
    # No alarming or speculative phrasing
    lower = line.lower()
    for forbidden in ("missed", "failed", "warning", "alert", "should", "must", "concerning"):
        assert forbidden not in lower


def test_med_skip_silences_the_pulse():
    """Any skip in the window cancels the medication observation."""
    events = [_ev("medication") for _ in range(MIN_MED_COMPLETIONS)] + [_ev("medication", "skipped")]
    # Without enough rehab/turnout activity, we should stay quiet rather
    # than overreach.
    assert compose_pulse("Halo", events) is None


def test_rehab_followthrough():
    events = [_ev("rehab") for _ in range(MIN_REHAB_COMPLETIONS)]
    line = compose_pulse("Mercury", events)
    assert line == "Mercury completed all scheduled rehab sessions this week."


def test_rehab_skip_silences():
    events = [_ev("rehab") for _ in range(MIN_REHAB_COMPLETIONS)] + [_ev("rehab", "skipped")]
    assert compose_pulse("Mercury", events) is None


def test_turnout_steadiness_combined():
    """turnout_out + turnout_in completions sum toward the threshold."""
    half = MIN_TURNOUT_MOVES // 2
    events = [_ev("turnout_out") for _ in range(half)] + [_ev("turnout_in") for _ in range(MIN_TURNOUT_MOVES - half)]
    line = compose_pulse("Halo", events)
    assert line is not None
    assert "Turnout routines" in line
    assert "stayed steady" in line


def test_turnout_skip_silences():
    events = ([_ev("turnout_out") for _ in range(MIN_TURNOUT_MOVES)]
              + [_ev("turnout_in", "skipped")])
    assert compose_pulse("Halo", events) is None


def test_priority_is_med_over_rehab_over_turnout():
    """When multiple confident observations are possible, medication wins
    (most operationally meaningful to owners). Only one line ever emitted."""
    events = (
        [_ev("medication") for _ in range(MIN_MED_COMPLETIONS)]
        + [_ev("rehab") for _ in range(MIN_REHAB_COMPLETIONS)]
        + [_ev("turnout_out") for _ in range(MIN_TURNOUT_MOVES)]
    )
    line = compose_pulse("Halo", events)
    assert line is not None
    assert "medication adherence" in line
    # never combine
    assert "rehab" not in line.lower()
    assert "turnout" not in line.lower()


def test_no_medical_or_predictive_language():
    """Any output must avoid speculative or medical interpretation."""
    cases = [
        [_ev("medication") for _ in range(MIN_MED_COMPLETIONS)],
        [_ev("rehab") for _ in range(MIN_REHAB_COMPLETIONS)],
        [_ev("turnout_out") for _ in range(MIN_TURNOUT_MOVES)],
    ]
    forbidden = ["recommend", "diagnos", "predict", "likely",
                 "probably", "expect", "concerning", "abnormal"]
    for events in cases:
        line = compose_pulse("Halo", events)
        assert line is not None
        lower = line.lower()
        for word in forbidden:
            assert word not in lower, f"forbidden language '{word}' surfaced in: {line}"


def test_irrelevant_categories_ignored():
    """Events outside the curated 7d-pulse categories don't trigger anything."""
    events = [_ev("stall_clean") for _ in range(10)]
    assert compose_pulse("Halo", events) is None
