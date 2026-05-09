# CLAUDE.md — LuminAgents Project Conventions

> ارفع هذا الملف في Project Knowledge، والصق محتواه (أو مختصره) في Custom Instructions.

---

## السياق

أنا أحمد. أعمل على **LuminAgents** — نظام multi-agent بالعربي/إنجليزي يعمل كمدرب مهارات شخصي.
مسابقة **Agenticthon** - جامعة الأمير سطام بن عبدالعزيز.
الفريق: أحمد، خيري، عبدالرحمن.

مسار المشروع: `D:\Apps\LuminAgents`

التفاصيل الكاملة في `LuminAgents_Core_14.md` و `LuminAgents_Progress.md`.

---

## Tech Stack

| الطبقة | الأداة |
|--------|--------|
| LLM الرئيسي | Gemini Flash (primary) |
| LLM الاحتياطي | Claude Sonnet عبر LiteLLM |
| Orchestration | Python Orchestrator (routing صريح — لا CrewAI agents) |
| API | FastAPI |
| Data Validation | Pydantic |
| Bot | python-telegram-bot |
| DB | SQLite + WAL Mode |
| KB | Tag-Based Markdown |
| Web Search | Tavily (اختياري — يجب أن يكون off في KB-only mode) |
| Monitoring | Streamlit Dashboard |
| Python | 3.11.9 |

---

## أسلوب الرد

- مباشر، مختصر، صفر حشو أو مجاملات عامة
- Chain of Thought داخلي فقط؛ أظهر النتيجة بس، إلا إذا طلبت الشرح
- تقنياً دقيق، خصوصاً في AI/engineering
- لو السؤال غامض، اسأل قبل ما تكتب جواب طويل
- عربي للمحادثة، إنجليزي للكود والـ commits والـ identifiers
- بدون emojis إلا لو أضفتها أنا أول
- بدون كلمات "genuinely", "honestly", "straightforward"

---

## القواعد التقنية للمشروع

### اختبار
- `test_scenarios.py` = مصدر الحقيقة للسلوك المتوقع
- **قبل أي commit: شغّل `python test_scenarios.py` ولازم 18/18 نجحت**
- الاختبار يستخدم `DEMO_MODE=true` + DB منفصلة في `%TEMP%` — لا يلمس `luminagents.db` الأصلية
- لا تحرق API credits في الاختبار — استخدم DEMO_MODE دائماً

### المعمار الذهبي (لا تكسره)
1. **routing صريح** في `orchestrator.py` — لا تستخدم CrewAI agents اللي تختار orchestration بنفسها
2. **`/setup` محذوف** — الـ onboarding بلغة طبيعية. LLM يستخرج البيانات من رسالة المستخدم
3. **Fixer يتدخل فقط عند `failure_streak >= 3`** — ويصفّر العداد فوراً. منفصل عن Coach
4. **KB-only mode** — لو KB ما فيها إجابة → رد "لا معلومات كافية"، لا ترجع محتوى غير مرتبط بسبب tag match فقط
5. **Snapshot pattern** — Planner يحفظ summary مضغوط عند كل انتقال milestone، يقرأه Coach بدل إعادة بناء الـ prompt كامل
6. **Language detection** — `detect_language()` تعتمد على نسبة الأحرف العربية. كل رد يمر على LLM. صفر نصوص ثابتة
7. **WAL Mode** — `PRAGMA journal_mode=WAL` إلزامي على كل اتصال DB

### معادلة التقدير الزمني
```
W = ceil((H_base / (h × d)) × 1.2)
```
- `W` = عدد الأسابيع
- `H_base` = الساعات القياسية (جدول في `agents/onboarding.py`)
- `h` = ساعات يومية، `d` = أيام أسبوعياً
- `1.2` = معامل الواقعية (20% إضافي)

### قواعد الكود
- صفر نصوص ثابتة في الردود للمستخدم — كل شي يمر على `call_llm()`
- AR/EN بالتوازي — كل prompt له نسختين
- Pydantic models في `models/schemas.py` — لا تضع models في أماكن ثانية
- `detect_language()` ترد `ar` أو `en` فقط
- الـ routes: `out_of_scope | goal_reset | plan_change | content_question | daily_check`
- الأولوية: `out_of_scope > goal_reset > plan_change > content_question > daily_check`
- `SKIP_LOCAL_KB = True` في `agents/researcher.py` — constant صلب، لا تغيّره
- `background_discourse()` يُطلَق من `telegram_bot.py` فقط (على run_polling event loop)

---

## المهام المتبقية (بالأولوية)

1. ✅ **`/start` handler** — منجزة. يستخدم `GREETING_AR/EN` (one-shot natural language onboarding).
2. ✅ **`KB_ONLY_MODE` flag** — منجزة. `agents/researcher.py:19` يتخطى Tier 3 (Tavily) ويحتفظ بـ Tier 4 (LLM Synthesis).
3. ✅ **بروفة Demo كاملة** — `DEMO_REHEARSAL.md` منجزة: سيناريو 7 خطوات + pre-flight + Q&A cheat sheet + recovery playbook.
4. ✅ **شرائح العرض (pptx)** — `LuminAgents_Agenticthon_2026.pptx` منجزة: 14 شريحة (LAYOUT_WIDE)، إصلاح خط monospace + bidi العربي + تخطيط الإحصائية.

### v6.0 Lite (The Strategic Sprint)

5. ✅ **Semantic Dependency Graph** — `dashboard/streamlit_app.py` تاب `🕸️ Dependency Graph`: SVG نقي 13 node / 19 edge، ألوان حية من `agent_log`.
6. ✅ **`security_audit` table** — `llm/llm_client.py`: `_audit()` wrapper + `finally:` block في `call_llm()` و `async_call_llm()`. SHA-256 hash, tokens_in/out, duration_ms, status. Dashboard badge + sidebar stats.
7. ✅ **Milestone-boundary Consensus Verdict** — `orchestrator.py`: `_detect_completion()` + `_check_milestone_complete()` + `_milestone_verdict()`. يُشغَّل عند إكمال آخر task في milestone → Coach vs Fixer Consensus → milestone.completed=1 في DB.
8. ✅ **YouTube Video Intelligence** — `agents/researcher.py`: `_generate_video_query()`. Direct watch URLs عبر `_YT_WATCH_RE`. يُسجَّل في `agent_log` كـ `video_recommendation`.

### v6.3 (Reviewer Mandated — مكتمل بالكامل)

9. ✅ **Web-First Protocol** — `SKIP_LOCAL_KB=True` في `researcher.py`. Tier 3 (Tavily) أساسي + Knowledge Guard cosine ≥ 0.8.
10. ✅ **Stage-Gate** — `_check_stage_gate()` في `orchestrator.py`. Sequential content lock عند incomplete tasks في الأسبوع الحالي.
11. ✅ **Behavioral Pulse** — `_check_behavioral_pulse()`. Event-driven: 12h gap + repeated query → score ≥ 2 → Fixer Recovery Menu.
12. ✅ **Background Discourse Loop** — `background_discourse()` async. `asyncio.create_task` من `telegram_bot.py`. Cooldown Guard 5 دقائق. max_tokens=2048.
13. ✅ **`/reset` + `/restart` commands** — `_hard_reset_user()`: أرشفة + full wipe + fresh onboarding.
14. ✅ **Big Picture First** — Onboarding يعرض الخطة الكاملة أولاً + أول مصدر Tavily حي.

### v6.4 (Critical UX Refinement — مكتمل بالكامل)

15. ✅ **Fix Leakage** — `background_discourse` prompt يحتوي hard rule يمنع ذكر أي مصطلح داخلي (Coach/Fixer/consensus/streak/stage-gate). الـ `_behavior_prefix` لا يُلصق raw على رسالة المستخدم — Dashboard فقط.
16. ✅ **Reset Pulse Guard** — `_check_behavioral_pulse()` يقرأ أحدث `hard_reset`/`profile_complete` في `agent_log`؛ لو في الـ 24 ساعة الماضية → يُرجع 0 فوراً. الإشارات القديمة (قبل الـ reset) محجوبة بـ `id > min_id`.
17. ✅ **Adaptive Web Sourcing** — `_get_level_domains(level)` في `researcher.py`: beginner → w3schools/geeksforgeeks/realpython/freecodecamp؛ intermediate → realpython/medium/MDN؛ advanced → كامل بما فيه arxiv/IEEE. `level` ينتقل من `fetch()` إلى `tavily_search_constrained()`.
18. ✅ **Identity Enforcement** — "The Sentinel" استُبدل بـ "Khyres Elite Coach" في `GREETING_AR/EN` + `_sentinel_persona()` + `agent_identities.md`.

---

## Workflow عند بدء الجلسة

1. اكتب: "اقرأ Progress.md وقلي وين وقفنا"
2. اختر المهمة التالية من القائمة أعلاه (أو اقترح بديل)
3. اسأل قبل ما تبدأ لو في أكثر من احتمال
4. بعد التعديل: `python test_scenarios.py` → لازم 18/18
