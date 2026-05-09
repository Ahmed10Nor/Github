# api/main.py — Architecture v2
# Async endpoints — كل route تستدعي async method مباشرة بدون asyncio.run()
# هذا يمنع "event loop already running" لما FastAPI يشغّل الـ routes
import os
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

from db.database import get_connection, init_db           # noqa: E402
from models.schemas import MessageInput, OnboardingInput  # noqa: E402
from orchestrator import LuminAgentsOrchestrator          # noqa: E402

init_db()  # تأكد DB موجودة عند بدء التشغيل

app = FastAPI(
    title="LuminAgents API",
    version="2.0.0",
    description="Multi-Agent Skill Coaching System — Agenticthon 2026",
)

orc = LuminAgentsOrchestrator()


# ─── Health ──────────────────────────────────────────────────
@app.get("/health")
async def health():
    """فحص الـ API والـ DB."""
    try:
        conn       = get_connection()
        row        = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        conn.close()
        user_count = row[0] if row else 0
        return {
            "status":      "ok",
            "system":      "LuminAgents v2",
            "demo_mode":   os.getenv("DEMO_MODE", "false"),
            "users_in_db": user_count,
            "date":        str(date.today()),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB error: {e}")


# ─── Onboarding مباشر (للاختبار عبر API) ────────────────────
@app.post("/start")
async def start(data: OnboardingInput):
    """
    Onboarding مباشر — يقبل OnboardingInput الكامل.
    الـ Telegram bot يستخدم FSM عبر /message،
    لكن هذا مفيد للاختبار المباشر عبر API / Swagger.
    """
    try:
        result  = await orc._handle_new_user_async(data)
        profile = result["profile"]
        plan    = result["plan"]
        return {
            "status":           "ok",
            "user_id":          profile.user_id,
            "name":             profile.name,
            "goal":             profile.goal,
            "estimated_weeks":  profile.estimated_weeks,
            "milestones_count": len(plan.milestones),
            "milestones": [
                {
                    "title":      m.title,
                    "week_start": m.week_start,
                    "week_end":   m.week_end,
                }
                for m in plan.milestones
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Main Message Handler (FSM + routing) ────────────────────
@app.post("/message")
async def message(data: MessageInput):
    """
    Entry point الرئيسي — يمر على FSM onboarding ثم Hybrid Router.
    نفس المسار الذي يستخدمه Telegram bot.
    """
    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")
    try:
        reply = await orc._handle_message_async(data.user_id, data.message)
        return {"status": "ok", "reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Progress ────────────────────────────────────────────────
@app.get("/progress/{user_id}")
async def progress(user_id: str):
    """حالة المستخدم: goal، streak، estimated_weeks."""
    result = orc.get_progress(user_id)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return result


# ─── Plan ────────────────────────────────────────────────────
@app.get("/plan/{user_id}")
async def plan(user_id: str):
    """الخطة الكاملة مع Milestones."""
    profile = orc._get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return orc.get_plan(user_id)


# ─── Daily Task — Passive Mode ───────────────────────────────
@app.get("/daily/{user_id}")
async def daily(user_id: str):
    """
    المهمة اليومية — Coach يقرأ من DB (Passive Mode، zero LLM في normal flow).
    """
    profile = orc._get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    if not profile.onboarding_complete:
        raise HTTPException(status_code=400, detail="Onboarding not complete")
    try:
        report = orc.coach.daily_task(profile)
        return {
            "status":           "ok",
            "day_index":        report.day_index,
            "task":             report.notes,
            "failure_streak":   report.failure_streak,
            "updated_estimate": report.updated_estimate,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Demo: Reset User ────────────────────────────────────────
@app.delete("/reset/{user_id}")
async def reset_user(user_id: str):
    """
    يمسح المستخدم وكل بياناته — للاستخدام في بروفة الـ Demo فقط.
    """
    try:
        conn   = get_connection()
        tables = [
            "users", "milestones", "daily_tasks",
            "snapshots", "context_frames", "failure_log",
            "tasks", "sources",
        ]
        for table in tables:
            conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return {"status": "ok", "deleted": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Demo: Inject Streak ─────────────────────────────────────
@app.post("/demo/inject_streak/{user_id}")
async def inject_streak(user_id: str, streak: int = 3):
    """
    يحقن failure_streak — لإظهار سلوك Fixer في الـ Demo.
    """
    profile = orc._get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO tasks (user_id, date, description, failure_streak) "
            "VALUES (?, ?, ?, ?)",
            (user_id, str(date.today()), "demo_injected", streak),
        )
        conn.commit()
        conn.close()
        return {"status": "ok", "injected_streak": streak, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
