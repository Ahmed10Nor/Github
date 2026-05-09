# tools/math_tool.py
# ═══════════════════════════════════════════════════════════════
# LuminAgents — Math Validation Tool (deterministic, zero LLM)
# Called by Planner before committing a MicroPlan to DB.
# ═══════════════════════════════════════════════════════════════
from __future__ import annotations
from models.schemas import MicroPlan, UserProfile, ValidationResult

# Tolerance: plan may use up to 5% more than available hours
_OVERRUN_TOLERANCE = 0.05


def validate_plan(micro_plan: MicroPlan, profile: UserProfile) -> ValidationResult:
    """
    Deterministic check — no LLM.

    h_available = hours_per_day * days_per_week * estimated_weeks
    Passes when h_total <= h_available * (1 + _OVERRUN_TOLERANCE).
    """
    if not micro_plan.daily_tasks:
        return ValidationResult(
            passed=False,
            h_total=0.0,
            h_available=_h_available(profile),
            delta=_h_available(profile),
            error_trace="MicroPlan has no daily tasks — Planner must generate tasks first.",
        )

    h_total     = round(sum(t.hours for t in micro_plan.daily_tasks), 4)
    h_avail     = round(_h_available(profile), 4)
    delta       = round(h_avail - h_total, 4)
    ceiling     = round(h_avail * (1 + _OVERRUN_TOLERANCE), 4)
    passed      = h_total <= ceiling
    error_trace = None

    if not passed:
        overrun_pct = round((h_total - h_avail) / h_avail * 100, 1) if h_avail else 0
        error_trace = (
            f"Plan overruns available time by {overrun_pct}%. "
            f"h_total={h_total}h > h_available={h_avail}h "
            f"({profile.hours_per_day}h/day x {profile.days_per_week}d/week "
            f"x {profile.estimated_weeks}weeks). "
            f"Reduce task hours by at least {abs(delta):.2f}h or extend estimated_weeks."
        )

    return ValidationResult(
        passed=passed,
        h_total=h_total,
        h_available=h_avail,
        delta=delta,
        error_trace=error_trace,
    )


# ──────────────────────────────────────────────────────────────
# HELPER
# ──────────────────────────────────────────────────────────────
def _h_available(profile: UserProfile) -> float:
    return profile.hours_per_day * profile.days_per_week * profile.estimated_weeks
