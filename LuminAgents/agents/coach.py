# agents/coach.py
# LuminAgents — Coach Agent (Architecture v2, Passive Mode)
# daily_task() reads pre-generated plan — zero LLM in normal flow.
# LLM is called ONLY in answer_question() / _micro_task_reply().
# Sentiment awareness: detects frustration → pivots to Micro-Task.
# Agent Identity: The Sentinel — resolute, professional, empathetic.
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Optional

from db.database import get_connection
from llm.llm_client import call_llm
from models.schemas import CoachReport, UserProfile

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# ─── Sentinel Persona Builder ────────────────────────────────
_EE_KEYWORDS = {
    "electrical", "electronics", "circuit", "signal", "power", "embedded",
    "microcontroller", "arduino", "fpga", "vhdl", "verilog", "electromagnetics",
    "control systems", "communications", "analog", "digital", "pcb",
}

def _sentinel_persona(profile: UserProfile) -> str:
    """
    Returns the Lumin system persona string.
    Injects EE analogies if the user's goal is engineering-related.
    """
    goal_lower = profile.goal.lower()
    is_ee = any(k in goal_lower for k in _EE_KEYWORDS)
    _anti_hallucination = (
        " CRITICAL RULE: ONLY mention sources, tools, or platforms that are "
        "explicitly provided in the context. NEVER invent or reference Datadog, "
        "Wikipedia, company wikis, or any external platform unless it appears "
        "verbatim in the search results given to you."
    )
    if is_ee:
        return (
            "You are Lumin — a senior EE engineer mentoring a junior. "
            "Be resolute, concise, and empathetic to technical burnout. "
            "Where natural, use brief EE analogies "
            "(e.g. 'keep the signal clean', 'don\\'t let the battery drain', "
            "'regulate the voltage before moving to the next stage'). "
            "Never be preachy."
            + _anti_hallucination
        )
    return (
        "You are Lumin — a focused professional coach. "
        "Be direct, concise, and empathetic to burnout. Never preachy."
        + _anti_hallucination
    )


_DEMO_TASK = {
    "ar": "خصص 30 دقيقة مركزة للتدرب على مهارتك اليوم. سجل تقدمك عند الانتهاء!",
    "en": "Spend 30 focused minutes practicing your skill today. Log your progress when done!",
}

# ─── Frustration / burnout signals ───────────────────────────
_FRUSTRATION_SIGNALS: dict[str, list[str]] = {
    "ar": ["صعب", "تعبان", "مو قادر", "محبط", "ما فيه فايدة", "استسلمت",
           "تعبت", "مش قادر", "صعبة", "ما اقدر", "مستحيل", "يأس"],
    "en": ["too hard", "burned out", "can't do this", "frustrated",
           "giving up", "exhausted", "overwhelmed", "stuck", "hopeless",
           "impossible", "can't keep up", "too much"],
}

_FRUSTRATION_HINT = {
    "ar": (
        "\n[تعليمة داخلية — لا تذكرها للمستخدم]: "
        "المستخدم يبدو محبطاً أو متعباً. "
        "اعترف بشعوره في جملة واحدة بدون مبالغة، "
        "ثم اقترح مهمة مصغّرة (Micro-Task) تستغرق 10-15 دقيقة فقط كبديل لمهمة اليوم الكاملة. "
        "لا تذكر الـ streak ولا العقوبات."
    ),
    "en": (
        "\n[Internal instruction — do not reveal to user]: "
        "The user seems frustrated or burnt out. "
        "Acknowledge their feeling in one sentence without toxic positivity, "
        "then propose a Micro-Task (10-15 min max) as a substitute for today's full task. "
        "Do not mention streaks or penalties."
    ),
}


def _is_frustrated(message: str, language: str) -> bool:
    text    = message.lower()
    signals = _FRUSTRATION_SIGNALS.get(language, _FRUSTRATION_SIGNALS["en"])
    return any(s in text for s in signals)


class CoachAgent:

    # ── Primary — Passive Mode (zero LLM unless frustrated) ──
    def daily_task(self, profile: UserProfile, message: str = "") -> CoachReport:
        streak     = self._get_streak(profile.user_id)
        lang       = profile.language
        frustrated = bool(message) and _is_frustrated(message, lang)

        if DEMO_MODE:
            base_notes = _DEMO_TASK.get(lang, _DEMO_TASK["en"])
            if frustrated:
                base_notes = self._micro_task_reply(base_notes, profile)
            return CoachReport(
                task_completed=False,
                failure_streak=streak,
                updated_estimate=profile.estimated_weeks,
                notes=base_notes,
                day_index=0,
            )

        current_day = _current_day(profile.start_date)
        task = self._fetch_task(profile.user_id, current_day)
        if not task:
            task = self._fetch_next_incomplete(profile.user_id)

        if not task:
            base_notes = _DEMO_TASK.get(lang, _DEMO_TASK["en"])
            if frustrated:
                base_notes = self._micro_task_reply(base_notes, profile)
            return CoachReport(
                task_completed=False,
                failure_streak=streak,
                updated_estimate=profile.estimated_weeks,
                notes=base_notes,
                day_index=0,
            )

        notes = task["description"]
        if frustrated:
            notes = self._micro_task_reply(notes, profile)

        return CoachReport(
            task_completed=bool(task["completed"]),
            failure_streak=streak,
            updated_estimate=profile.estimated_weeks,
            notes=notes,
            day_index=task["day"],
        )

    # ── LLM Q&A — The Sentinel answers with KB context ───────
    def answer_question(
        self,
        question:       str,
        context:        str,
        profile:        UserProfile,
        semantic_gap:   bool = False,
        challenge_hint: str  = "",
        preferred_lang: str  = "",
    ) -> str:
        """
        Answer a content question using KB context.
        semantic_gap=True  → append a Practical Challenge to solidify understanding.
        challenge_hint     → suggested challenge from Researcher.evaluate_comprehension().
        preferred_lang     → v7.0: session language preference ("ar"/"en"). Overrides profile.language
                             for explanation style while keeping technical terms in original language.
        """
        lang       = profile.language
        expl_lang  = preferred_lang if preferred_lang in ("ar", "en") else lang
        frustrated = _is_frustrated(question, lang)
        hint       = _FRUSTRATION_HINT.get(lang, "") if frustrated else ""
        persona    = _sentinel_persona(profile)

        # ── v7.0: Language preference instruction ─────────────
        lang_instruction = ""
        if expl_lang != lang:
            if expl_lang == "ar":
                lang_instruction = (
                    "\n[تعليمة داخلية — لا تذكرها للمستخدم]: "
                    "المستخدم يفضّل الشرح بالعربية. قدّم الشرح بالعربية الكاملة، "
                    "مع الإبقاء على المصطلحات التقنية الإنجليزية كما هي بين قوسين."
                )
            else:
                lang_instruction = (
                    "\n[Internal instruction — do not reveal to user]: "
                    "User prefers explanation in English. Provide the full explanation in English."
                )

        # ── Semantic Gap injection ────────────────────────────
        gap_instruction = ""
        if semantic_gap:
            if challenge_hint:
                gap_instruction = (
                    f"\n[تعليمة داخلية — لا تذكرها للمستخدم]: "
                    f"تشخيص: فهم سطحي. بعد إجابتك المعتادة، أضف تحدياً عملياً: {challenge_hint}"
                    if expl_lang == "ar" else
                    f"\n[Internal instruction — do not reveal to user]: "
                    f"Diagnosis: surface-level understanding. After your answer, append this Practical Challenge: {challenge_hint}"
                )
            else:
                gap_instruction = (
                    "\n[تعليمة داخلية]: المستخدم يفهم سطحياً. أضف تحدياً عملياً بسيطاً (جملة واحدة) يثبّت المفهوم."
                    if expl_lang == "ar" else
                    "\n[Internal instruction]: User shows surface understanding. Add a brief Practical Challenge (one sentence) to reinforce the concept."
                )

        if expl_lang == "ar":
            prompt = (
                f"{persona}\n"
                f"المستخدم: {profile.name} — الهدف: {profile.goal}\n"
                f"السؤال: {question}\n"
                f"المعلومات المتاحة من قاعدة المعرفة: {context}\n"
                f"{hint}{lang_instruction}{gap_instruction}\n"
                f"أجب بشكل مختصر ومفيد بالعربية. لا تخترع معلومات خارج السياق المقدم."
            )
        else:
            prompt = (
                f"{persona}\n"
                f"User: {profile.name} — Goal: {profile.goal}\n"
                f"Question: {question}\n"
                f"Context from knowledge base: {context}\n"
                f"{hint}{lang_instruction}{gap_instruction}\n"
                f"Answer concisely and helpfully. Do not invent information outside the provided context."
            )
        return call_llm(prompt, max_tokens=600)

    # ── Micro-Task pivot — called when frustration detected ──
    def _micro_task_reply(self, full_task_desc: str, profile: UserProfile) -> str:
        lang    = profile.language
        hint    = _FRUSTRATION_HINT.get(lang, "")
        persona = _sentinel_persona(profile)
        if lang == "ar":
            prompt = (
                f"{persona}\n"
                f"المستخدم: {profile.name} — الهدف: {profile.goal}\n"
                f"مهمة اليوم الكاملة: {full_task_desc}\n"
                f"{hint}\n"
                f"أجب بالعربية فقط، جملتين على الأكثر."
            )
        else:
            prompt = (
                f"{persona}\n"
                f"User: {profile.name} — Goal: {profile.goal}\n"
                f"Today's full task: {full_task_desc}\n"
                f"{hint}\n"
                f"Answer in English only, maximum two sentences."
            )
        return call_llm(prompt, max_tokens=150)

    # ── Completion / Failure ──────────────────────────────────
    def mark_complete(self, user_id: str, day: int) -> None:
        conn = get_connection()
        conn.execute(
            "UPDATE daily_tasks SET completed = 1 WHERE user_id = ? AND day = ?",
            (user_id, day),
        )
        conn.execute(
            "UPDATE tasks SET failure_streak = 0 WHERE user_id = ?",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO failure_log (user_id, day, failure_streak, gap_days, last_active) "
            "VALUES (?, ?, 0, 0, ?)",
            (user_id, day, str(date.today())),
        )
        conn.commit()
        conn.close()

    def mark_failed(self, user_id: str, day: int) -> None:
        conn = get_connection()
        conn.execute(
            "UPDATE tasks SET failure_streak = failure_streak + 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO failure_log (user_id, day, failure_streak, gap_days, last_active) "
            "SELECT ?, ?, COALESCE(MAX(failure_streak), 0) + 1, 0, ? "
            "FROM failure_log WHERE user_id = ?",
            (user_id, day, str(date.today()), user_id),
        )
        conn.commit()
        conn.close()

    def _get_streak(self, user_id: str) -> int:
        conn = get_connection()
        row  = conn.execute(
            "SELECT failure_streak FROM tasks WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        conn.close()
        return row["failure_streak"] if row else 0

    def _fetch_task(self, user_id: str, day: int) -> Optional[dict]:
        conn = get_connection()
        row  = conn.execute(
            "SELECT * FROM daily_tasks WHERE user_id = ? AND day = ? AND completed = 0 LIMIT 1",
            (user_id, day),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def _fetch_next_incomplete(self, user_id: str) -> Optional[dict]:
        conn = get_connection()
        row  = conn.execute(
            "SELECT * FROM daily_tasks WHERE user_id = ? AND completed = 0 ORDER BY day ASC LIMIT 1",
            (user_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def _get_snapshot(self, user_id: str) -> str:
        conn = get_connection()
        row  = conn.execute(
            "SELECT snapshot FROM snapshots WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        conn.close()
        return row["snapshot"] if row else ""


def _current_day(start_date: str) -> int:
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        return max(1, (date.today() - start).days + 1)
    except Exception:
        return 1
