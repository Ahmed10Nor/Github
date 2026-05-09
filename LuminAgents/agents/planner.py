# agents/planner.py
# ═══════════════════════════════════════════════════════════════
# LuminAgents — Planner Agent (Architecture v2)
# Three-tier: Macro (milestones) + Micro (daily tasks) + Validation loop.
# ═══════════════════════════════════════════════════════════════
from __future__ import annotations

import asyncio
import json
import math
import os
import re
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional

import aiosqlite

import db.database as _db_module          # dynamic — tests patch DB_PATH here
from llm.llm_client import call_llm
from models.schemas import (
    Category, ContextFrame, CurriculumMap, DailyTask,
    LearningTemplate, LessonNode, MacroPlan, Milestone,
    MicroPlan, UserProfile,
)
from tools.math_tool import validate_plan

DEMO_MODE  = os.getenv("DEMO_MODE", "false").lower() == "true"
MAX_RETRIES = 3

U_MULTIPLIER: dict[str, float] = {
    "beginner":     1.4,
    "intermediate": 1.0,
    "advanced":     0.75,
}

CATEGORY_TEMPLATE: dict[str, LearningTemplate] = {
    "academic":     "linear_mastery",
    "professional": "80_20_project_based",
    "personal":     "habit_stacking",
    "physical":     "progressive_overload",
}


class PlanningError(Exception):
    pass


# ──────────────────────────────────────────────────────────────
# MAIN AGENT
# ──────────────────────────────────────────────────────────────
class PlannerAgent:

    # ── Public API ────────────────────────────────────────────
    async def build(
        self,
        profile:       UserProfile,
        context_frame: Optional[ContextFrame] = None,
    ) -> tuple[MacroPlan, MicroPlan]:
        """
        Full pipeline: recalculate weeks → macro plan → micro plan
        (with self-correction loop) → persist to DB.
        """
        if context_frame is None:
            context_frame = _kb_context_frame(profile) or _demo_context_frame(profile)

        curriculum = context_frame.curriculum_map
        lessons    = _topological_sort(curriculum.lessons)

        # Recalculate estimated_weeks from curriculum
        u_mult  = U_MULTIPLIER.get(profile.level, 1.0)
        h_need  = sum(l.hours_std * u_mult for l in lessons)
        profile.estimated_weeks = max(
            1, math.ceil(h_need / (profile.hours_per_day * profile.days_per_week))
        )

        macro = self._build_macro(lessons, curriculum.template, profile)
        micro = await self._build_micro_with_retry(lessons, profile, context_frame)

        await self._save(profile, macro, micro)
        return macro, micro

    def revise(self, profile: UserProfile, message: str) -> str:
        """Handle manual plan-change requests — sync, LLM explains the revision."""
        if DEMO_MODE:
            return (
                f"تم تعديل خطتك! قللت الجلسات اليومية لتناسب جدولك. استمر بخطوات أصغر."
                if profile.language == "ar"
                else f"Plan adjusted! Reduced your daily sessions to fit your schedule. Keep going with smaller steps."
            )
        if profile.language == "ar":
            prompt = (
                f"أنت Planner في LuminAgents.\n"
                f"المستخدم: {profile.name} — الهدف: {profile.goal}\n"
                f"الجدول الحالي: {profile.hours_per_day}س/يوم × {profile.days_per_week}أيام/أسبوع.\n"
                f"طلب التعديل: {message}\n\n"
                f"عدّل الخطة وأخبر المستخدم بالتغيير في جملتين بالعربية."
            )
        else:
            prompt = (
                f"You are the Planner in LuminAgents.\n"
                f"User: {profile.name} — Goal: {profile.goal}\n"
                f"Current schedule: {profile.hours_per_day}h/day × {profile.days_per_week}d/week.\n"
                f"Adjustment request: {message}\n\n"
                f"Adjust the plan and explain the change in two sentences in English."
            )
        return call_llm(prompt)

    def rebuild(self, profile: UserProfile) -> str:
        """Fixer-triggered full rebuild — sync, LLM generates easier plan message."""
        if DEMO_MODE:
            return (
                f"أعدت بناء خطتك بأسلوب أسهل. الآن 30 دقيقة يومياً بدل ساعة. أنت قادر!"
                if profile.language == "ar"
                else f"Rebuilt your plan to be easier. Now 30 min/day instead of 1 hour. You can do this!"
            )
        if profile.language == "ar":
            prompt = (
                f"أنت Planner في LuminAgents.\n"
                f"المستخدم: {profile.name} — الهدف: {profile.goal} — المستوى: {profile.level}.\n"
                f"فشل المستخدم أكثر من 3 مرات متتالية. أعد بناء الخطة بأسلوب أسهل وأكثر واقعية "
                f"(قلل الساعات أو الأيام أو طوّل المدة). "
                f"أخبر المستخدم بالتغيير في جملتين تحفيزيتين بالعربية."
            )
        else:
            prompt = (
                f"You are the Planner in LuminAgents.\n"
                f"User: {profile.name} — Goal: {profile.goal} — Level: {profile.level}.\n"
                f"User failed 3+ times in a row. Rebuild the plan to be easier and more realistic. "
                f"Explain the change in two motivating sentences in English."
            )
        return call_llm(prompt)

    # ── Macro Plan ────────────────────────────────────────────
    def _build_macro(
        self,
        lessons:  list[LessonNode],
        template: LearningTemplate,
        profile:  UserProfile,
    ) -> MacroPlan:
        n_milestones = min(5, max(3, len(lessons) // 2 + 1))
        groups       = _group_lessons(lessons, n_milestones)
        u_mult       = U_MULTIPLIER.get(profile.level, 1.0)

        titles   = (
            _demo_titles(len(groups), profile.language)
            if DEMO_MODE
            else _generate_titles(groups, profile)
        )

        milestones: list[Milestone] = []
        week_cursor = 1
        for group, title in zip(groups, titles):
            group_hours = sum(l.hours_std * u_mult for l in group)
            group_weeks = max(1, math.ceil(
                group_hours / (profile.hours_per_day * profile.days_per_week)
            ))
            milestones.append(Milestone(
                title=title,
                week_start=week_cursor,
                week_end=week_cursor + group_weeks - 1,
                lesson_ids=[l.id for l in group],
            ))
            week_cursor += group_weeks

        total_weeks = week_cursor - 1
        snapshot    = _make_snapshot(milestones, profile)

        return MacroPlan(
            milestones=milestones,
            total_weeks=total_weeks,
            template=template,
            snapshot=snapshot,
        )

    # ── Micro Plan + Self-Correction ──────────────────────────
    async def _build_micro_with_retry(
        self,
        lessons:       list[LessonNode],
        profile:       UserProfile,
        context_frame: ContextFrame,
    ) -> MicroPlan:
        last_error: Optional[str] = None

        for attempt in range(MAX_RETRIES):
            micro  = _build_micro(lessons, profile, context_frame)
            result = validate_plan(micro, profile)

            if result.passed:
                return micro

            last_error = result.error_trace
            # Self-correction: extend weeks to absorb the overrun
            min_weeks = math.ceil(
                result.h_total / (profile.hours_per_day * profile.days_per_week)
            )
            profile.estimated_weeks = min_weeks

        raise PlanningError(
            f"Plan validation failed after {MAX_RETRIES} attempts. "
            f"Last: {last_error}"
        )

    # ── DB Persistence ────────────────────────────────────────
    async def _save(
        self,
        profile: UserProfile,
        macro:   MacroPlan,
        micro:   MicroPlan,
    ) -> None:
        db_path = str(_db_module.DB_PATH)   # read at runtime — tests patch this

        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")

            # Clear old plan for this user
            await conn.execute(
                "DELETE FROM milestones WHERE user_id=?", (profile.user_id,)
            )
            await conn.execute(
                "DELETE FROM daily_tasks WHERE user_id=?", (profile.user_id,)
            )

            for m in macro.milestones:
                await conn.execute(
                    "INSERT INTO milestones "
                    "(user_id, title, week_start, week_end, lesson_ids) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        profile.user_id, m.title,
                        m.week_start, m.week_end,
                        json.dumps(m.lesson_ids, ensure_ascii=False),
                    ),
                )

            for t in micro.daily_tasks:
                await conn.execute(
                    "INSERT INTO daily_tasks "
                    "(user_id, day, week, lesson_id, description, hours) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        profile.user_id, t.day, t.week,
                        t.lesson_id, t.description, t.hours,
                    ),
                )

            await conn.execute(
                "INSERT INTO snapshots (user_id, milestone_index, snapshot) "
                "VALUES (?, ?, ?)",
                (profile.user_id, 0, macro.snapshot),
            )

            await conn.execute(
                "UPDATE users SET estimated_weeks=? WHERE user_id=?",
                (macro.total_weeks, profile.user_id),
            )

            await conn.commit()


# ──────────────────────────────────────────────────────────────
# MODULE-LEVEL HELPERS (pure functions — easier to test)
# ──────────────────────────────────────────────────────────────

def _topological_sort(lessons: list[LessonNode]) -> list[LessonNode]:
    """Kahn's algorithm — dependency-safe order."""
    by_id     = {l.id: l for l in lessons}
    in_degree: dict[str, int] = defaultdict(int)
    children:  dict[str, list[str]] = defaultdict(list)  # parent → dependents

    for l in lessons:
        in_degree.setdefault(l.id, 0)
        for dep in l.depends_on:
            if dep in by_id:
                children[dep].append(l.id)
                in_degree[l.id] += 1

    queue  = deque(l for l in lessons if in_degree[l.id] == 0)
    result: list[LessonNode] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for child_id in children[node.id]:
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(by_id[child_id])

    # Guard: append anything left (cycle-safe fallback)
    seen = {l.id for l in result}
    result.extend(l for l in lessons if l.id not in seen)
    return result


def _group_lessons(lessons: list[LessonNode], n: int) -> list[list[LessonNode]]:
    """Split topologically-sorted lessons into n equal-weight buckets."""
    if not lessons:
        return []
    n = min(n, len(lessons))
    target = 1.0 / n
    groups: list[list[LessonNode]] = [[]]
    cumulative = 0.0

    for i, lesson in enumerate(lessons):
        groups[-1].append(lesson)
        cumulative += lesson.weight
        remaining_lessons = len(lessons) - i - 1
        remaining_groups  = n - len(groups)
        # Open a new bucket only if: target reached AND enough lessons left to fill remaining buckets
        if remaining_groups > 0 and cumulative >= target * len(groups) and remaining_lessons >= remaining_groups:
            groups.append([])

    return groups


def _build_micro(
    lessons:       list[LessonNode],
    profile:       UserProfile,
    context_frame: ContextFrame,
) -> MicroPlan:
    """Convert lessons to day-by-day tasks. Pure function — no LLM, no DB."""
    u_mult       = U_MULTIPLIER.get(profile.level, 1.0)
    descriptions = _batch_descriptions(lessons, profile, context_frame)

    daily_tasks: list[DailyTask] = []
    day_num      = 1
    week_num     = 1
    day_in_week  = 0

    for lesson in lessons:
        lesson_hours = round(lesson.hours_std * u_mult, 2)
        remaining    = lesson_hours
        desc         = descriptions.get(lesson.id, f"Study: {lesson.title}")

        while remaining > 1e-4:
            task_hours = round(min(profile.hours_per_day, remaining), 2)
            daily_tasks.append(DailyTask(
                day=day_num, week=week_num,
                lesson_id=lesson.id,
                description=desc,
                hours=task_hours,
            ))
            remaining   = round(remaining - task_hours, 4)
            day_num    += 1
            day_in_week += 1
            if day_in_week >= profile.days_per_week:
                day_in_week = 0
                week_num   += 1

    h_total = round(sum(t.hours for t in daily_tasks), 4)
    return MicroPlan(
        daily_tasks=daily_tasks,
        total_days=len(daily_tasks),
        h_total=h_total,
        user_id=profile.user_id,
    )


def _batch_descriptions(
    lessons:       list[LessonNode],
    profile:       UserProfile,
    context_frame: ContextFrame,
) -> dict[str, str]:
    """One LLM call for all lesson descriptions. Returns {lesson_id: description}."""
    if DEMO_MODE:
        if profile.language == "ar":
            return {l.id: f"ادرس: {l.title} ({l.hours_std} ساعة)" for l in lessons}
        return {l.id: f"Study: {l.title} ({l.hours_std}h)" for l in lessons}

    kb_context = "\n".join(context_frame.chunks[:3]) if context_frame.chunks else ""
    items = "\n".join(
        f"{i+1}. [{l.id}] {l.title}  ({round(l.hours_std * U_MULTIPLIER.get(profile.level, 1.0), 1)}h at {profile.level})"
        for i, l in enumerate(lessons)
    )

    if profile.language == "ar":
        prompt = (
            f"أنت مدرب تعلم. اكتب وصف مهمة يومية موجزة وعملية لكل درس:\n{items}\n\n"
            f"السياق: {kb_context[:400]}\n\n"
            f"أجب بـ JSON فقط: {{\"descriptions\": {{\"lesson_id\": \"وصف\", ...}}}}"
        )
    else:
        prompt = (
            f"You are a learning coach. Write a concise daily task description for each lesson:\n{items}\n\n"
            f"Context: {kb_context[:400]}\n\n"
            f"Reply with JSON only: {{\"descriptions\": {{\"lesson_id\": \"description\", ...}}}}"
        )

    try:
        raw  = call_llm(prompt, max_tokens=900, thinking_budget=1024)
        raw  = re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()
        data = json.loads(re.search(r"\{[\s\S]*\}", raw).group())
        return data.get("descriptions", {})
    except Exception:
        # Fallback: template descriptions
        return {l.id: f"Study: {l.title}" for l in lessons}


def _generate_titles(
    groups:  list[list[LessonNode]],
    profile: UserProfile,
) -> list[str]:
    """Single LLM call to name each milestone group."""
    items = "\n".join(
        f"Group {i+1}: {', '.join(l.title for l in g)}"
        for i, g in enumerate(groups)
    )
    if profile.language == "ar":
        prompt = (
            f"أعطِ عنواناً قصيراً (2-4 كلمات) لكل مجموعة دروس:\n{items}\n\n"
            f"JSON فقط: {{\"titles\": [\"عنوان1\", ...]}}"
        )
    else:
        prompt = (
            f"Give a short title (2-4 words) for each lesson group:\n{items}\n\n"
            f"JSON only: {{\"titles\": [\"Title1\", ...]}}"
        )
    try:
        raw   = call_llm(prompt, max_tokens=200, thinking_budget=1024)
        raw   = re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()
        data  = json.loads(re.search(r"\{[\s\S]*\}", raw).group())
        titles = data["titles"]
        while len(titles) < len(groups):
            titles.append(f"Phase {len(titles)+1}")
        return titles[:len(groups)]
    except Exception:
        return _demo_titles(len(groups), profile.language)


def _demo_titles(n: int, language: str) -> list[str]:
    ar = ["الأساسيات", "المفاهيم الأساسية", "التطبيق العملي", "التعمق", "المشروع النهائي"]
    en = ["Foundations", "Core Concepts", "Applied Practice", "Deep Dive", "Final Project"]
    pool = ar if language == "ar" else en
    return [pool[i % len(pool)] for i in range(n)]


def _make_snapshot(milestones: list[Milestone], profile: UserProfile) -> str:
    """
    Returns a compressed pipe-format snapshot for LLM context injection.
    Format: GOAL|TOTAL_WEEKS|M1>M2>M3|Xh*Yd
    ~15 tokens vs ~30 tokens for the old human-readable format.
    Use snapshot_to_human() for user-facing display.
    """
    phases = ">".join(m.title for m in milestones)
    total  = milestones[-1].week_end if milestones else profile.estimated_weeks
    return f"{profile.goal}|{total}|{phases}|{profile.hours_per_day}h*{profile.days_per_week}d"


def snapshot_to_human(snapshot: str, language: str) -> str:
    """
    Converts pipe-format snapshot to readable text for user display.
    Falls back gracefully if snapshot is already in old format.
    """
    try:
        goal, weeks, phases_raw, schedule = snapshot.split("|", 3)
        phases = phases_raw.replace(">", " → ")
        h, d   = schedule.replace("h*", "|").replace("d", "").split("|")
        if language == "ar":
            return (
                f"خطة {weeks} أسبوع لـ {goal}:\n{phases}\n"
                f"الجدول: {h} ساعة × {d} أيام/أسبوع"
            )
        return (
            f"{weeks}-week plan for {goal}:\n{phases}\n"
            f"Schedule: {h}h × {d}d/week"
        )
    except Exception:
        # Old format or malformed — return as-is
        return snapshot


def _kb_context_frame(profile: UserProfile) -> Optional[ContextFrame]:
    """Build a ContextFrame from KB content + LLM lesson generation.
    Returns None if KB has no matching content or LLM output can't be parsed."""
    try:
        from knowledge_base import kb_router
        result = kb_router.search(
            tags=[profile.category, profile.level],
            query=profile.goal,
        )
        if not result.chunks:
            return None

        kb_text = "\n\n".join(result.chunks[:3])
        if profile.language == "ar":
            prompt = (
                f"أنت خبير تعليمي. بناءً على محتوى قاعدة المعرفة هذا لمهارة '{profile.goal}':\n\n"
                f"{kb_text[:600]}\n\n"
                f"أنشئ 5 دروس تعليمية متسلسلة للمستوى {profile.level}.\n"
                f"أجب بـ JSON فقط:\n"
                f'{{\"lessons\": [{{\"id\": \"l1\", \"title\": \"عنوان الدرس\", \"hours_std\": 4.0}}, ...]}}'
            )
        else:
            prompt = (
                f"You are a curriculum designer. Based on this knowledge base for '{profile.goal}':\n\n"
                f"{kb_text[:600]}\n\n"
                f"Create 5 sequential lessons for {profile.level} level. Use specific titles from the content.\n"
                f"Reply with JSON only:\n"
                f'{{\"lessons\": [{{\"id\": \"l1\", \"title\": \"Specific Lesson Title\", \"hours_std\": 4.0}}, ...]}}'
            )

        raw  = call_llm(prompt, max_tokens=400, thinking_budget=1024)
        raw  = re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()
        data = json.loads(re.search(r"\{[\s\S]*\}", raw).group())
        raw_lessons = data.get("lessons", [])
        if not raw_lessons:
            return None

        # Build LessonNode list with equal normalized weights
        lesson_list = raw_lessons[:5]
        weight = round(1.0 / len(lesson_list), 4)
        lessons: list[LessonNode] = []
        for i, l in enumerate(lesson_list):
            lessons.append(LessonNode(
                id=l.get("id", f"lesson_{i+1}"),
                title=l.get("title", f"Lesson {i+1}"),
                weight=weight,
                depends_on=[lessons[-1].id] if lessons else [],
                hours_std=float(l.get("hours_std", 4.0)),
            ))
        # Fix rounding so weights sum exactly to 1.0
        delta = round(1.0 - sum(l.weight for l in lessons), 4)
        if delta and lessons:
            lessons[-1] = LessonNode(
                id=lessons[-1].id, title=lessons[-1].title,
                weight=round(lessons[-1].weight + delta, 4),
                depends_on=lessons[-1].depends_on,
                hours_std=lessons[-1].hours_std,
            )

        curriculum = CurriculumMap(
            skill=profile.goal,
            category=profile.category,
            template=CATEGORY_TEMPLATE.get(profile.category, "linear_mastery"),
            total_hours_std=round(sum(l.hours_std for l in lessons), 2),
            lessons=lessons,
        )
        return ContextFrame(
            user_id=profile.user_id,
            skill=profile.goal,
            user_level=profile.level,
            chunks=result.chunks,
            curriculum_map=curriculum,
            user_state={},
            fallback_used=False,
            retrieved_at=datetime.utcnow(),
        )
    except Exception:
        return None



def _demo_context_frame(profile: UserProfile) -> ContextFrame:
    """
    Fallback when KB has no matching content.
    DEMO_MODE -> static generic lessons (no LLM cost).
    Live mode  -> LLM generates 5 goal-specific lessons for the actual skill.
    """
    if DEMO_MODE:
        lessons = [
            LessonNode(id="intro",    title="مقدمة"             if profile.language == "ar" else "Introduction",   weight=0.15, depends_on=[],          hours_std=3.0),
            LessonNode(id="basics",   title="الأساسيات"         if profile.language == "ar" else "Basics",         weight=0.20, depends_on=["intro"],    hours_std=4.0),
            LessonNode(id="core",     title="المفاهيم الأساسية" if profile.language == "ar" else "Core Concepts",  weight=0.25, depends_on=["basics"],   hours_std=5.0),
            LessonNode(id="practice", title="التطبيق"           if profile.language == "ar" else "Practice",       weight=0.25, depends_on=["core"],     hours_std=5.0),
            LessonNode(id="project",  title="مشروع تطبيقي"     if profile.language == "ar" else "Applied Project", weight=0.15, depends_on=["practice"], hours_std=3.0),
        ]
    else:
        lessons = _llm_generate_lessons(profile)

    curriculum = CurriculumMap(
        skill=profile.goal,
        category=profile.category,
        template=CATEGORY_TEMPLATE.get(profile.category, "linear_mastery"),
        total_hours_std=sum(l.hours_std for l in lessons),
        lessons=lessons,
    )
    return ContextFrame(
        user_id=profile.user_id,
        skill=profile.goal,
        user_level=profile.level,
        chunks=[],
        curriculum_map=curriculum,
        user_state={},
        fallback_used=True,
        retrieved_at=datetime.utcnow(),
    )


def _llm_generate_lessons(profile: UserProfile) -> list:
    """Single LLM call -> 5 goal-specific sequential lessons (live mode only)."""
    import json as _json, re as _re
    from llm.llm_client import call_llm as _call_llm
    goal, level, lang = profile.goal, profile.level, profile.language
    if lang == "ar":
        prompt = (
            f"أنت خبير تعليمي. المهارة: '{goal}'، المستوى: {level}.\n"
            f"أنشئ 5 دروس تعليمية متسلسلة ومحددة لهذه المهارة.\n"
            f"أجب بـ JSON فقط: [{{\"id\":\"l1\",\"title\":\"عنوان تفصيلي\",\"hours_std\":3.0}},...] لا عناوين عامة."
        )
    else:
        prompt = (
            f"You are a curriculum designer. Skill: '{goal}', Level: {level}.\n"
            f"Create 5 sequential specific lessons for THIS exact skill.\n"
            f"JSON only: [{{\"id\":\"l1\",\"title\":\"Specific title\",\"hours_std\":3.0}},...] No generic titles."
        )
    try:
        raw  = _call_llm(prompt, max_tokens=300, thinking_budget=1024)
        raw  = _re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()
        m    = _re.search(r"\[.+\]", raw, _re.DOTALL)
        data = _json.loads(m.group()) if m else []
        lessons, prev = [], []
        for i, item in enumerate(data[:5]):
            lid = item.get("id", f"l{i+1}")
            lessons.append(LessonNode(
                id=lid,
                title=item.get("title", f"{goal} — Step {i+1}"),
                weight=round(1.0 / max(len(data), 1), 2),
                depends_on=prev[:],
                hours_std=float(item.get("hours_std", 4.0)),
            ))
            prev = [lid]
        if lessons:
            return lessons
    except Exception as e:
        print(f"[_llm_generate_lessons ERROR] {e}")
    ids = ["l1", "l2", "l3", "l4", "l5"]
    steps_ar = ["أساسيات", "تقنيات", "تطبيق عملي", "مشروع متقدم", "إتقان"]
    steps_en = ["Fundamentals", "Techniques", "Practical Application", "Advanced Project", "Mastery"]
    steps = steps_ar if lang == "ar" else steps_en
    return [
        LessonNode(id=ids[i], title=f"{goal} — {steps[i]}",
                   weight=0.2, depends_on=[ids[i-1]] if i > 0 else [],
                   hours_std=4.0)
        for i in range(5)
    ]
