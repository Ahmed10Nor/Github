# agents/fixer.py
# ═══════════════════════════════════════════════════════════════
# LuminAgents — Fixer Agent (Architecture v2)
# Handles three trigger types: streak | gap | manual_request
# Streak: LLM motivational message + immediate reset
# Gap ≤3d: pure DB reschedule (no LLM)
# Gap >3d: Planner.rebuild()
# manual_request: deferred to Planner.revise()
# ═══════════════════════════════════════════════════════════════
from __future__ import annotations

import math
import os
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

import aiosqlite

import db.database as _db_module
from db.database import get_connection
from llm.llm_client import call_llm
from models.schemas import FixerReport, FixerTrigger, UserProfile

if TYPE_CHECKING:
    from agents.planner import PlannerAgent

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

_DEMO_STREAK = {
    "ar": (
        "واجهت عقبة — هذا طبيعي تماماً! إليك خياراتك:\n\n"
        "1. محتوى بديل — نفس المفهوم من زاوية مختلفة\n"
        "2. تبسيط — تقطيع المهمة لأجزاء أصغر\n"
        "3. إعادة جدولة — ضبط وتيرة التعلم"
    ),
    "en": (
        "You hit a wall — that's completely normal! Here are your options:\n\n"
        "1. Alternative Content — same concept, different angle\n"
        "2. Simplification — break the task into smaller chunks\n"
        "3. Reschedule — adjust your learning pace"
    ),
}
_DEMO_GAP = {
    "ar": "مرحباً من جديد! رحّلنا المهام الفائتة وأعدنا ترتيب جدولك.",
    "en": "Welcome back! We rescheduled your missed tasks and reorganized your plan.",
}
_DEMO_BEHAVIOR = {
    "ar": (
        "رصدت نمطاً سلوكياً — سأتدخل استباقياً.\n\n"
        "**قائمة التعافي التكتيكي:**\n"
        "1. محتوى بديل — نفس المفهوم من مصدر أو زاوية مختلفة\n"
        "2. تبسيط — تقطيع المهمة الحالية لأجزاء أصغر قابلة للإنجاز\n"
        "3. إعادة جدولة — ضبط الوتيرة اليومية لتناسب طاقتك"
    ),
    "en": (
        "Behavioral pattern detected — proactive intervention triggered.\n\n"
        "**Tactical Recovery Menu:**\n"
        "1. Alternative Content — same concept, different source or angle\n"
        "2. Simplification — chop the current task into smaller, completable units\n"
        "3. Reschedule — adjust your daily pace to match your current capacity"
    ),
}


class FixerAgent:

    # ── Public Entry Point ────────────────────────────────────
    async def intervene(
        self,
        profile: UserProfile,
        trigger: Optional[FixerTrigger] = None,
    ) -> FixerReport:
        """
        Dispatch to the correct handler based on trigger.reason.
        Default trigger = streak when called without explicit trigger.
        """
        if trigger is None:
            trigger = FixerTrigger(
                reason="streak",
                streak_count=self._get_streak(profile.user_id),
            )

        if trigger.reason == "streak":
            return await self._handle_streak(profile, trigger)

        if trigger.reason == "gap":
            return await self._handle_gap(profile, trigger)

        if trigger.reason == "behavior":
            return await self._handle_behavior(profile, trigger)

        # manual_request — Planner.revise() is the right tool
        lang = profile.language
        msg = (
            "لطلبات التعديل اليدوية، أخبرني بالتغيير الذي تريده وسأعدّل الخطة مباشرة."
            if lang == "ar"
            else "For manual adjustments, tell me what to change and I'll revise the plan directly."
        )
        return FixerReport(message=msg, rescheduled=False, rebuilt=False, streak_reset=False)

    # ── Streak Handler ────────────────────────────────────────
    async def _handle_streak(
        self, profile: UserProfile, trigger: FixerTrigger
    ) -> FixerReport:
        if DEMO_MODE:
            await self._reset_streak_async(profile.user_id)
            return FixerReport(
                message=_DEMO_STREAK.get(profile.language, _DEMO_STREAK["en"]),
                rescheduled=False,
                rebuilt=False,
                streak_reset=True,
            )

        streak = trigger.streak_count or self._get_streak(profile.user_id)
        if profile.language == "ar":
            prompt = (
                f"أنت Fixer في LuminAgents.\n"
                f"المستخدم: {profile.name} — الهدف: {profile.goal}\n"
                f"فشل {streak} مرات متتالية.\n\n"
                f"اكتب رسالة قصيرة بالعربية (جملتان تحفيزيتان)، ثم قدّم قائمة التعافي التكتيكي:\n"
                f"1. محتوى بديل — نفس المفهوم من مصدر أو زاوية مختلفة\n"
                f"2. تبسيط — تقطيع المهمة الحالية لأجزاء أصغر\n"
                f"3. إعادة جدولة — ضبط وتيرة التعلم اليومية\n"
                f"كن مباشراً وعملياً، صفر حشو."
            )
        else:
            prompt = (
                f"You are the Fixer in LuminAgents.\n"
                f"User: {profile.name} — Goal: {profile.goal}\n"
                f"Failed {streak} times in a row.\n\n"
                f"Write two motivational sentences, then present the Tactical Recovery Menu:\n"
                f"1. Alternative Content — same concept, different source or angle\n"
                f"2. Simplification — chop the current task into smaller units\n"
                f"3. Reschedule — adjust the daily learning pace\n"
                f"Be direct and practical, zero filler."
            )

        message = call_llm(prompt)
        await self._reset_streak_async(profile.user_id)

        return FixerReport(
            message=message,
            rescheduled=False,
            rebuilt=False,
            streak_reset=True,
        )

    # ── Behavior Handler — proactive intervention ─────────────
    async def _handle_behavior(
        self, profile: UserProfile, trigger: FixerTrigger
    ) -> FixerReport:
        """
        Triggered by behavioral pulse: long gap between messages OR repeated
        queries on the same topic — signals the user is stuck before failure_streak fires.
        Presents the 3-option Tactical Recovery Menu proactively.
        """
        if DEMO_MODE:
            return FixerReport(
                message=_DEMO_BEHAVIOR.get(profile.language, _DEMO_BEHAVIOR["en"]),
                rescheduled=False,
                rebuilt=False,
                streak_reset=False,
            )

        score = trigger.behavioral_score
        lang  = profile.language
        if lang == "ar":
            prompt = (
                f"أنت Fixer في LuminAgents — تتدخل استباقياً.\n"
                f"المستخدم: {profile.name} — الهدف: {profile.goal} — المستوى: {profile.level}\n"
                f"الإشارة السلوكية: {'تكرار استفسارات' if score >= 2 else 'فجوة زمنية طويلة'} "
                f"(نقاط سلوكية: {score}/2)\n\n"
                f"اكتب تشخيصاً مختصراً (جملة واحدة) ثم قدّم قائمة التعافي التكتيكي بالعربية:\n"
                f"1. محتوى بديل — نفس المفهوم من مصدر أو زاوية مختلفة\n"
                f"2. تبسيط — تقطيع المهمة الحالية لأجزاء أصغر قابلة للإنجاز\n"
                f"3. إعادة جدولة — ضبط الوتيرة اليومية\n"
                f"كن مباشراً، بدون حشو."
            )
        else:
            prompt = (
                f"You are the Fixer in LuminAgents — proactive intervention mode.\n"
                f"User: {profile.name} — Goal: {profile.goal} — Level: {profile.level}\n"
                f"Behavioral signal: {'repeated queries' if score >= 2 else 'long inactivity gap'} "
                f"(behavioral score: {score}/2)\n\n"
                f"Write a one-sentence diagnosis, then present the Tactical Recovery Menu:\n"
                f"1. Alternative Content — same concept, different source or angle\n"
                f"2. Simplification — chop the current task into smaller completable units\n"
                f"3. Reschedule — adjust the daily learning pace\n"
                f"Be direct, zero filler."
            )

        message = call_llm(prompt, max_tokens=200)
        return FixerReport(
            message=message,
            rescheduled=False,
            rebuilt=False,
            streak_reset=False,
        )

    # ── Gap Handler ───────────────────────────────────────────
    async def _handle_gap(
        self, profile: UserProfile, trigger: FixerTrigger
    ) -> FixerReport:
        gap         = trigger.gap_days
        current_day = _current_day(profile.start_date)

        if gap <= 3:
            # Reschedule missed tasks — pure DB, no LLM
            count = await self._reschedule_missed(profile.user_id, current_day, profile.days_per_week)
            lang  = profile.language
            if DEMO_MODE or count == 0:
                msg = _DEMO_GAP.get(lang, _DEMO_GAP["en"])
            elif lang == "ar":
                msg = f"مرحباً من جديد! رحّلنا {count} مهمة فائتة للأيام القادمة. استمر من حيث توقفت."
            else:
                msg = f"Welcome back! Rescheduled {count} missed task(s) to upcoming days. Pick up where you left off."

            return FixerReport(
                message=msg,
                rescheduled=count > 0,
                rebuilt=False,
                streak_reset=False,
            )

        # gap > 3 days → full rebuild via Planner
        from agents.planner import PlannerAgent  # avoid circular import at module level
        rebuild_msg = PlannerAgent().rebuild(profile)

        return FixerReport(
            message=rebuild_msg,
            rescheduled=False,
            rebuilt=True,
            streak_reset=False,
        )

    # ── Reschedule: push missed tasks forward (no delete) ─────
    async def _reschedule_missed(
        self, user_id: str, current_day: int, days_per_week: int
    ) -> int:
        """
        Find incomplete tasks from past days, renumber them starting
        at current_day + 1. Week is recalculated from the new day.
        Pure DB operation — no LLM.
        """
        db_path = str(_db_module.DB_PATH)

        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("PRAGMA journal_mode=WAL")
            conn.row_factory = aiosqlite.Row

            async with conn.execute(
                "SELECT id FROM daily_tasks "
                "WHERE user_id = ? AND day < ? AND completed = 0 "
                "ORDER BY day ASC",
                (user_id, current_day),
            ) as cur:
                missed = [row[0] for row in await cur.fetchall()]

            for offset, task_id in enumerate(missed):
                new_day  = current_day + 1 + offset
                new_week = math.ceil(new_day / max(1, days_per_week))
                await conn.execute(
                    "UPDATE daily_tasks SET day = ?, week = ? WHERE id = ?",
                    (new_day, new_week, task_id),
                )

            await conn.commit()

        return len(missed)

    # ── Streak Reset (async) ──────────────────────────────────
    async def _reset_streak_async(self, user_id: str) -> None:
        async with aiosqlite.connect(str(_db_module.DB_PATH)) as conn:
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute(
                "UPDATE tasks SET failure_streak = 0 WHERE user_id = ?",
                (user_id,),
            )
            await conn.commit()

    # ── Streak Read (sync — tests call this directly) ─────────
    def _get_streak(self, user_id: str) -> int:
        conn = get_connection()
        row  = conn.execute(
            "SELECT failure_streak FROM tasks "
            "WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        conn.close()
        return row["failure_streak"] if row else 0


# ─── Helper ──────────────────────────────────────────────────
def _current_day(start_date: str) -> int:
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        return max(1, (date.today() - start).days + 1)
    except Exception:
        return 1
