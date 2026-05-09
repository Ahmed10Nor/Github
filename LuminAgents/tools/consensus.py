# tools/consensus.py
# ═══════════════════════════════════════════════════════════════
# LuminAgents — Consensus Engine (Architecture v5.1)
# Conditional debate loop between Coach and Fixer.
# Triggered only on: route == plan_change OR failure_streak >= 2.
# Both LLM perspectives run concurrently via asyncio.gather.
# Results logged to agent_log → shown in Streamlit Dashboard.
# ═══════════════════════════════════════════════════════════════
from __future__ import annotations

import asyncio
import os
from typing import Optional

from db.database import log_agent
from llm.llm_client import call_llm
from models.schemas import ConsensusResult, UserProfile

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# ─── Demo fallbacks — zero LLM cost ──────────────────────────
_DEMO_COACH = {
    "ar": "الزخم لا يزال قائماً — أنصح بالمواصلة مع تعديل طفيف في الوتيرة.",
    "en": "Momentum is intact — I recommend proceeding with a slight pace adjustment.",
}
_DEMO_FIXER = {
    "ar": "أرى إشارات ضغط مبكرة — أقترح تخفيف المهمة القادمة لمنع الإرهاق.",
    "en": "Early stress signals detected — suggest easing the next task to prevent burnout.",
}
_DEMO_DECISION = {
    "ar": "القرار: نواصل مع تخفيف 20% في مهمة اليوم مع الاحتفاظ بالهدف الأسبوعي. ACTION: proceed_adjusted",
    "en": "Decision: Proceed with 20% ease on today's task while keeping the weekly goal. ACTION: proceed_adjusted",
}


async def run_consensus(
    profile: UserProfile,
    route: str,
    context: str,
    db_path: Optional[str] = None,
) -> ConsensusResult:
    """
    Run the Coach vs Fixer debate concurrently, then synthesize.
    Logs three entries to agent_log (coach / fixer / orchestrator).
    Never raises — consensus failure must not crash the main flow.
    """
    try:
        lang = profile.language

        if DEMO_MODE:
            coach_view = _DEMO_COACH.get(lang, _DEMO_COACH["en"])
            fixer_view = _DEMO_FIXER.get(lang, _DEMO_FIXER["en"])
            decision   = _DEMO_DECISION.get(lang, _DEMO_DECISION["en"])
            action     = "proceed_adjusted"
            _log_all(profile.user_id, route, coach_view, fixer_view, decision, db_path)
            return ConsensusResult(
                coach_view=coach_view,
                fixer_view=fixer_view,
                decision=decision,
                action=action,
            )

        # ── Concurrent LLM calls (Coach + Fixer in parallel) ─
        loop = asyncio.get_event_loop()
        coach_view, fixer_view = await asyncio.gather(
            loop.run_in_executor(None, _coach_perspective, profile, context),
            loop.run_in_executor(None, _fixer_perspective, profile, context),
        )

        # ── Synthesis (Orchestrator decides) ─────────────────
        decision, action = await loop.run_in_executor(
            None, _synthesize, profile, coach_view, fixer_view
        )

        _log_all(profile.user_id, route, coach_view, fixer_view, decision, db_path)
        return ConsensusResult(
            coach_view=coach_view,
            fixer_view=fixer_view,
            decision=decision,
            action=action,
        )

    except Exception as e:
        # Safety net — log error, return neutral result, never crash
        _safe_log(profile.user_id, route, f"consensus_error: {e}", db_path)
        return ConsensusResult(
            coach_view="",
            fixer_view="",
            decision="",
            action="proceed",
        )


# ─── Coach perspective ────────────────────────────────────────
def _coach_perspective(profile: UserProfile, context: str) -> str:
    lang = profile.language
    if lang == "ar":
        prompt = (
            f"أنت Coach في LuminAgents — مركّز على التقدم والمواصلة.\n"
            f"المستخدم: {profile.name} — الهدف: {profile.goal} — المستوى: {profile.level}\n"
            f"السياق الحالي: {context}\n"
            f"قدّم وجهة نظرك في جملة واحدة بالعربية: هل نواصل أم نعدّل، ولماذا؟"
        )
    else:
        prompt = (
            f"You are the Coach in LuminAgents — focused on progress and continuity.\n"
            f"User: {profile.name} — Goal: {profile.goal} — Level: {profile.level}\n"
            f"Current context: {context}\n"
            f"State your perspective in ONE sentence: proceed or adjust, and why?"
        )
    return call_llm(prompt, max_tokens=80)


# ─── Fixer perspective ────────────────────────────────────────
def _fixer_perspective(profile: UserProfile, context: str) -> str:
    lang = profile.language
    if lang == "ar":
        prompt = (
            f"أنت Fixer في LuminAgents — مركّز على الاستقرار ومنع الإرهاق.\n"
            f"المستخدم: {profile.name} — الهدف: {profile.goal} — المستوى: {profile.level}\n"
            f"السياق الحالي: {context}\n"
            f"قدّم وجهة نظرك في جملة واحدة بالعربية: هل يحتاج تدخلاً، ولماذا؟"
        )
    else:
        prompt = (
            f"You are the Fixer in LuminAgents — focused on stability and burnout prevention.\n"
            f"User: {profile.name} — Goal: {profile.goal} — Level: {profile.level}\n"
            f"Current context: {context}\n"
            f"State your perspective in ONE sentence: does this need intervention, and why?"
        )
    return call_llm(prompt, max_tokens=80)


# ─── Synthesis (Orchestrator arbitrates) ─────────────────────
def _synthesize(
    profile: UserProfile,
    coach_view: str,
    fixer_view: str,
) -> tuple[str, str]:
    """Returns (decision_text, action_key)."""
    lang = profile.language
    valid_actions = ("rebuild", "simplify", "proceed_adjusted", "proceed")

    if lang == "ar":
        prompt = (
            f"أنت Orchestrator في LuminAgents — تحكّم بين Coach وFixer.\n"
            f"المستخدم: {profile.name} — الهدف: {profile.goal}\n\n"
            f"رأي Coach: {coach_view}\n"
            f"رأي Fixer: {fixer_view}\n\n"
            f"اتخذ قراراً نهائياً في جملة واحدة بالعربية، ثم أضف في نهايتها:\n"
            f"ACTION: [proceed | proceed_adjusted | simplify | rebuild]\n"
            f"مثال: نواصل مع تخفيف طفيف. ACTION: proceed_adjusted"
        )
    else:
        prompt = (
            f"You are the Orchestrator in LuminAgents — arbitrating between Coach and Fixer.\n"
            f"User: {profile.name} — Goal: {profile.goal}\n\n"
            f"Coach says: {coach_view}\n"
            f"Fixer says: {fixer_view}\n\n"
            f"Make a final decision in ONE sentence, then append:\n"
            f"ACTION: [proceed | proceed_adjusted | simplify | rebuild]\n"
            f"Example: We proceed with a slight ease. ACTION: proceed_adjusted"
        )
    raw = call_llm(prompt, max_tokens=100)

    # Parse action keyword from LLM output
    action = "proceed"  # safe default
    for key in valid_actions:
        if key in raw:
            action = key
            break

    return raw, action


# ─── Logging helpers ──────────────────────────────────────────
def _log_all(
    user_id: str,
    route: str,
    coach_view: str,
    fixer_view: str,
    decision: str,
    db_path: Optional[str],
) -> None:
    kw = {"db_path": db_path} if db_path else {}
    log_agent(user_id, "coach",        "consensus_perspective", coach_view[:200],
              route=route, tokens_est=80,  **kw)
    log_agent(user_id, "fixer",        "consensus_perspective", fixer_view[:200],
              route=route, tokens_est=80,  **kw)
    log_agent(user_id, "orchestrator", "consensus_decision",    decision[:200],
              route=route, tokens_est=100, **kw)


def _safe_log(user_id: str, route: str, detail: str, db_path: Optional[str]) -> None:
    kw = {"db_path": db_path} if db_path else {}
    log_agent(user_id, "orchestrator", "consensus_error", detail, route=route, **kw)
