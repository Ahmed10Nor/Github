# telegram_bot.py — Architecture v2
# Zero LLM in /start handler. All routing delegated to orchestrator.
import asyncio
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext,
)
from telegram.request import HTTPXRequest

from orchestrator import (
    LuminAgentsOrchestrator,
    GREETING_AR,
    GREETING_EN,
    LEVEL_Q_AR,
    LEVEL_Q_EN,
)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USERS = (
    list(map(int, os.getenv("ALLOWED_USERS", "").split(",")))
    if os.getenv("ALLOWED_USERS")
    else []
)

orc = LuminAgentsOrchestrator()


# ─── Whitelist guard ──────────────────────────────────────────
async def check_whitelist(update: Update) -> bool:
    if ALLOWED_USERS and update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ غير مصرح. / Not authorized.")
        return False
    return True


# ─── /start — Sentinel greeting, zero LLM ────────────────────
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Three cases — all zero LLM:
      1. Brand-new user       → Sentinel one-shot onboarding prompt
      2. Onboarding in-progress → resume from current FSM step
      3. Returning user       → Sentinel welcome-back + plan summary
    """
    if not await check_whitelist(update):
        return

    user_id = str(update.effective_user.id)
    lc      = (update.effective_user.language_code or "en").lower()
    tg_lang = "ar" if lc.startswith("ar") else "en"

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    profile = orc._get_profile(user_id)

    # ── Case 1: brand-new user ────────────────────────────────
    # Create stub directly — no routing overhead, no /setup reference.
    if not profile:
        await orc._create_partial_user(user_id, tg_lang)
        reply = GREETING_AR if tg_lang == "ar" else GREETING_EN
        await update.message.reply_text(reply)
        return

    lang = profile.language or tg_lang

    # ── Case 2: onboarding in-progress ───────────────────────
    if profile.onboarding_complete == 0:
        step         = getattr(profile, "onboarding_step", "awaiting_goal")
        display_name = profile.name or ("صديقي" if lang == "ar" else "friend")

        if step == "awaiting_level" and profile.goal:
            # User gave goal but not level yet — resume that exact step
            reply = (
                LEVEL_Q_AR.format(name=display_name, goal=profile.goal)
                if lang == "ar"
                else LEVEL_Q_EN.format(name=display_name, goal=profile.goal)
            )
        else:
            # Step = awaiting_goal or unknown — restart with full Sentinel prompt
            reply = GREETING_AR if lang == "ar" else GREETING_EN

        await update.message.reply_text(reply)
        return

    # ── Case 3: returning user — Sentinel welcome-back ────────
    plan       = orc.get_plan(user_id)
    milestones = plan.get("milestones", [])

    if milestones:
        if lang == "ar":
            ms_lines = "\n".join(
                f"  {i+1}. {m.get('title','?')}"
                f" (أسبوع {m.get('week_start')}→{m.get('week_end')})"
                for i, m in enumerate(milestones)
            )
            reply = (
                f"⚡ مرحباً مجدداً {profile.name}.\n\n"
                f"الهدف: {profile.goal} | {profile.estimated_weeks} أسابيع\n\n"
                f"المراحل:\n{ms_lines}\n\n"
                f"أخبرني بتقدمك أو اسألني أي شيء."
            )
        else:
            ms_lines = "\n".join(
                f"  {i+1}. {m.get('title','?')}"
                f" (Week {m.get('week_start')}→{m.get('week_end')})"
                for i, m in enumerate(milestones)
            )
            reply = (
                f"⚡ Welcome back, {profile.name}.\n\n"
                f"Goal: {profile.goal} | {profile.estimated_weeks} weeks\n\n"
                f"Milestones:\n{ms_lines}\n\n"
                f"Tell me your progress or ask me anything."
            )
    else:
        # Milestones missing (edge case) — prompt like a new user
        reply = GREETING_AR if lang == "ar" else GREETING_EN

    await update.message.reply_text(reply)


# ─── /reset — full wipe + fresh onboarding ───────────────────
async def reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /reset (alias: /restart) — clears all learning data and restarts onboarding.
    Archives the current skill before wiping (accessible via resurrection).
    """
    if not await check_whitelist(update):
        return

    user_id = str(update.effective_user.id)
    lc      = (update.effective_user.language_code or "en").lower()

    profile = orc._get_profile(user_id)
    lang    = getattr(profile, "language", "ar" if lc.startswith("ar") else "en")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    if not profile:
        msg = (
            "لا يوجد ملف شخصي لحذفه. استخدم /start للبدء."
            if lang == "ar"
            else "No profile found. Use /start to begin."
        )
        await update.message.reply_text(msg)
        return

    orc._hard_reset_user(user_id)

    # v6.8 — System Purged confirmation + full onboarding greeting
    purge_msg = (
        "✅ تم مسح النظام بالكامل."
        if lang == "ar"
        else "✅ System Purged."
    )
    await update.message.reply_text(purge_msg)
    greeting = GREETING_AR if lang == "ar" else GREETING_EN
    await update.message.reply_text(greeting)


# ─── Text messages — fully delegated to orchestrator ─────────
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_whitelist(update):
        return

    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    message = update.message.text or ""

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # User receives reply instantly — no blocking on agent discourse
    reply = await orc._handle_message_async(user_id, message)
    await update.message.reply_text(reply)

    # ── Background Discourse: fire-and-forget sovereign agent loop ──────
    # Scheduled AFTER reply is sent. Runs on the persistent run_polling()
    # event loop. Coach + Fixer evaluate progress, time-drift, and
    # behavioral signals. If they agree on intervention → sends proactive
    # outbound message to the user without waiting for the next request.
    asyncio.create_task(
        orc.background_discourse(user_id, chat_id, context.bot)
    )


# ─── Entry point ─────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found in .env")
        return

    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request)
        .build()
    )
    app.add_handler(CommandHandler("start",   start_handler))
    app.add_handler(CommandHandler("reset",   reset_handler))
    app.add_handler(CommandHandler("restart", reset_handler))  # alias
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    async def error_handler(update: object, context: CallbackContext) -> None:
        print(f"[BOT ERROR] {context.error}")
        import traceback
        traceback.print_exc()

    app.add_error_handler(error_handler)

    print("🤖 LuminAgents Bot running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
