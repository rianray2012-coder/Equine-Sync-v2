"""wellness_pulse.py — quiet operational intelligence.

A single, calm 7-day observation per horse, derived strictly from
`task_events` already produced by the unified Task Engine. Layered into
the existing digest pipeline so no new operational surface is created.

Design constraints (per Feb 20 2026 product direction):
  - observational, never speculative
  - calm, confidence-limited language
  - no scoring, no predictions, no medical interpretation
  - returns None when there is no high-confidence observation
  - one line maximum per horse, per pulse pass
"""
from __future__ import annotations

from typing import Optional, List, Dict


# Minimum sample sizes required before we feel confident enough to
# emit a positive observation. Tuned conservatively — if the barn
# doesn't have enough activity in a category, we stay quiet.
MIN_MED_COMPLETIONS = 3
MIN_REHAB_COMPLETIONS = 2
MIN_TURNOUT_MOVES = 4


def _counts_by_outcome(events: List[dict], category: str) -> Dict[str, int]:
    """Count completed vs skipped events for a category over the window."""
    completed = sum(
        1 for e in events
        if e.get("category") == category and e.get("event_type") == "task.completed"
    )
    skipped = sum(
        1 for e in events
        if e.get("category") == category and e.get("event_type") == "task.skipped"
    )
    return {"completed": completed, "skipped": skipped}


def compose_pulse(horse_name: str, events_7d: List[dict]) -> Optional[str]:
    """Return a single calm 7-day observation, or None when nothing is
    confident enough to surface.

    Order of priority is intentional: we surface medication consistency
    first because it is the most operationally meaningful to owners,
    then rehab progress, then turnout steadiness. We never combine
    observations into a longer sentence.
    """
    if not events_7d:
        return None

    # 1. Medication consistency — only when sample is large enough AND
    #    there are zero skips/refusals across the week.
    med = _counts_by_outcome(events_7d, "medication")
    if med["completed"] >= MIN_MED_COMPLETIONS and med["skipped"] == 0:
        return f"{horse_name}'s medication adherence has remained consistent this week."

    # 2. Rehab follow-through — only when there are rehab sessions AND
    #    they were all completed.
    rehab = _counts_by_outcome(events_7d, "rehab")
    if rehab["completed"] >= MIN_REHAB_COMPLETIONS and rehab["skipped"] == 0:
        return f"{horse_name} completed all scheduled rehab sessions this week."

    # 3. Turnout steadiness — combined out + in over the 7d window.
    out = _counts_by_outcome(events_7d, "turnout_out")
    inn = _counts_by_outcome(events_7d, "turnout_in")
    total_turnout_completions = out["completed"] + inn["completed"]
    total_turnout_skips = out["skipped"] + inn["skipped"]
    if total_turnout_completions >= MIN_TURNOUT_MOVES and total_turnout_skips == 0:
        return f"Turnout routines for {horse_name} have stayed steady this week."

    # Otherwise — stay quiet. We only speak when we're confident.
    return None
