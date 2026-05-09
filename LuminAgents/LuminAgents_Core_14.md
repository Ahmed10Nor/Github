# 🧠 LuminAgents — Core Project Plan (Architecture v7.5)
### Agenticthon | جامعة الأمير سطام بن عبدالعزيز
### الفريق: أحمد، خيري، عبدالرحمن
### آخر تحديث: 2026-05-09 (v7.5 — Adaptive Challenge + Learning Package + Session Guards ✅ مكتمل — 18/18 ✅)

---

## 🎯 المشكلة والحل

> **المشكلة:** 80% من الناس يبدأون تعلم مهارة جديدة ويتوقفون خلال أسبوعين — لا لأنهم كسالى، بل لأنهم يفتقرون لمدرب يتابعهم، يعدّل مسارهم، ولا ينساهم.

**LuminAgents** نظام وكلاء ذكاء اصطناعي متعدد (Multi-Agent System) يعمل كمدرب شخصي حقيقي:
- يبني مساراً مخصصاً بتقدير زمني علمي دقيق (Hierarchical Planning + Dependency Graph)
- يتابع المستخدم يومياً بذاكرة تراكمية (Passive Mode — صفر LLM calls يومياً)
- يتدخل تلقائياً عند الفشل المتكرر أو الانقطاع قبل أن يستسلم المستخدم
- يوصّل **Learning Package** محدد (مصدر + فيديو + تمرين) — لا قوائم مقترحات

البنية مبنية على REST API — Telegram الآن، Mobile/Web لاحقاً، نفس الـ backend.

---

## 🏛️ Architecture v7.5

```
المستخدم
   │
   ▼
Telegram Bot  ←  Semantic Intent Detection عند أول تفاعل (بدون LLM)
   │
   ▼
LuminAgentsOrchestrator  [Full Async — aiosqlite]
   │
   ├── FSM Onboarding — One-shot (onboarding_complete flag في SQLite)
   │     رسالة واحدة → pipe extraction: NAME|GOAL|CATEGORY|LEVEL|HOURS|DAYS
   │     لو ناقص → سؤال واحد فقط عن اللي ناقص — ثم خطة فوراً
   │     Big Picture First: يعرض الخطة الكاملة + أول Tavily URL حي
   │
   ├── Date-Sync Logic  ←  gap ≥ 2 يوم → Fixer
   │
   ├── Hybrid Router
   │     Tier-0: Greeting Detection → greeting_checkin (LLM يغلّف المهمة)
   │     Tier-1: Regex/Keyword → out_of_scope | goal_reset | plan_change
   │                              | plan_status | content_question | daily_check
   │     Tier-2: LLM Fallback  ← للحالات الرمادية
   │     Priority: out_of_scope > goal_reset > plan_change > plan_status
   │                           > content_question > daily_check
   │
   ├── Source Intercept (v7.3 — في content_question handler)  ★ جديد
   │     كلمات مفتاحية: مصدر، وين أتعلم، رابط، كورس، دورة، موقع...
   │     → يتجاوز الـ LLM كلياً → fetch_learning_package() مباشرة
   │     → يُعيد Learning Package: 📚 Guide + 📺 Video + ✏️ Exercise
   │     → Fallback: YouTube Search Link (لا "لا أعرف")
   │
   ├── Adaptive Challenge — Level Upgrade (v7.5)  ★ جديد
   │     يكتشف: "سهل"، "ما فيه تحدي"، "too easy"، "give me harder"...
   │     → beginner→intermediate، intermediate→advanced، advanced يبقى advanced
   │     → يحدّث users.level في DB فوراً
   │     → يُعيد Learning Package بالمستوى الجديد + رسالة ترقية ⬆️
   │
   ├── Bootstrap Agent   [Offline — مرة واحدة لكل مهارة]
   │     KB Markdown → LLM → curriculum_map.json
   │     (Dependency Graph + Weights + hours_std)
   │
   ├── Researcher Agent (v7.x — Web-First Protocol)
   │     SKIP_LOCAL_KB = True  ← ثابت (hard-coded) — Tier 1 & 2 محذوفان
   │     Tier 2 (LanceDB): PERMANENTLY DISABLED (v7.1)
   │     الآن: Tier 3 (Tavily) → Tier 4 (LLM Synthesis)
   │
   │     fetch_learning_package() → Learning Package:
   │       📚 Primary Guide: Top 1 Tavily URL من whitelist المستوى
   │       📺 Visual Support: Direct YouTube watch URL أو Search Link
   │       ✏️ Actionable Exercise: مهمة صغيرة مبنية على المحتوى
   │
   │     Query Grounding (v7.3):
   │       استعلام غامض / قصير → يُعاد صياغته: "{goal} {level}"
   │       يمنع Tavily من إرجاع نتائج عشوائية لا علاقة لها بالهدف
   │
   │     Domain-Aware Whitelist (v6.5):
   │       يكتشف النطاق: code | language | fitness | professional | general
   │       يختار domains حسب النطاق + المستوى (beginner/intermediate/advanced)
   │       يمنع مواقع البرمجة من الظهور في نتائج اللغة والعكس
   │
   ├── Planner Agent  →  Hierarchical Planning:
   │     Macro: Milestones ← topological sort (depends_on)
   │     Micro: DailyTask[] ← H_total × U_multiplier / (h×d)
   │     Validation: math_tool.py (deterministic) + Self-Correction Loop (MAX=3)
   │
   ├── Coach Agent  →  Passive Mode:
   │     daily_task() ← يقرأ daily_tasks table (pre-generated) — صفر LLM
   │     answer_question() ← LLM يُستدعى هنا فقط (max_tokens=600)
   │     Anti-hallucination Rule (v7.3): لا يذكر Datadog/Wikipedia/أي منصة
   │                                      إلا إذا وردت صراحةً في context
   │
   │     Done → Next Package (v7.4):
   │       المستخدم يقول "خلصت"/"done" → evaluate_comprehension()
   │       → fetch_learning_package(next_task) تلقائياً
   │       → يُلحق Package بمحتوى رد التشجيع
   │
   ├── Fixer Agent  →  3 Triggers:
   │     streak ≥ 3   : LLM تحفيز + reset streak
   │     gap 2-3 days : reschedule (pure DB — بدون LLM)
   │     gap > 3 days : Planner.rebuild()
   │
   ├── Consensus Engine (v5.1 — tools/consensus.py)
   │     يُفعَّل عند 3 مناسبات:
   │       1. plan_change (دائماً)
   │       2. failure_streak ≥ 2 (تحذير مبكر)
   │       3. milestone boundary — كل مهام milestone اكتملت (Verdict)
   │     Coach + Fixer بالتوازي (asyncio.gather)
   │     action: proceed|proceed_adjusted|simplify|rebuild
   │     Milestone Verdict: milestone.completed=1 في DB بعد القرار
   │
   ├── Semantic Gap Analyzer (في ResearcherAgent)
   │     evaluate_comprehension(user_message, context, profile) → SemanticGapResult
   │     DEEP  → Coach يواصل عادياً
   │     GAP   → Coach يُضيف Practical Challenge في نهاية الرد
   │
   ├── Stage-Gate (v6.3)
   │     _check_stage_gate(user_id) → {current_week, incomplete, total, locked}
   │     locked=True → gate_note يُضاف لرد content_question
   │
   ├── Behavioral Pulse (v6.3 — event-driven)
   │     إشارة 1: فجوة نشاط > 12 ساعة بين آخر رسالتين
   │     إشارة 2: نفس الاستعلام 2+ مرات في آخر 3 fetch
   │     score ≥ 2 → Fixer(reason="behavior") → Recovery Menu
   │
   ├── Background Discourse (v6.3 + v7.3 guards)
   │     يُطلَق بعد رد المستخدم مباشرة (asyncio.create_task)
   │     Guards (بالترتيب):
   │       1. onboarding_complete == False → suppress
   │       2. interactions < 3 → suppress (fresh skill)
   │       3. session-start guard (v7.3): gap > 60 min بين آخر رسالتين → suppress
   │       4. eval_complete guard (v7.4): تقييم تمرين تم → suppress
   │       5. cooldown: < 5 دقائق من آخر outbound → suppress
   │       6. b_score < 2 (24h reset guard) → suppress
   │     إذا مرّ كل الـ guards: Consensus → Strategist Prompt → bot.send_message
   │     max_tokens=2048، صفر مصطلحات داخلية في رسالة المستخدم
   │
   ├── Hazem Protocol (v5.4)
   │     يكتشف طلبات تغيير الهوية: "سمّ نفسك X وكن صارماً"
   │     يحفظ agent_name + agent_vibe في users table
   │
   └── Hot Swap + Resurrection (v5.4)
         goal_reset → _archive_and_reset() (أرشفة، لا حذف)
         /reset + /restart → _hard_reset_user() → أرشفة + reset كامل
         _check_resurrection(): word-level match → يُعيد ArchivedSkill

LLM: google-genai SDK — Gemini Flash (gemini-flash-latest)
     thinking_budget=0 للـ Coach/Router | thinking_budget=1024 للـ Planner/Researcher
Streamlit Dashboard: 5 tabs — Agent Activity + Profile & Plan + Test Router
                     + 🤝 Consensus + 🕸️ Dependency Graph
Security Audit: SHA-256 hash + tokens_in/out + duration_ms + status (كل LLM call)
```

---

## 🔄 تدفق رسالة كاملة (v7.5)

```
المستخدم يكتب
       ↓
Telegram Bot → orchestrator.handle_message(user_id, text)
       ↓
[1] _get_profile(user_id)
       ↓
[2] مستخدم جديد؟
    نعم → Semantic Router (local embeddings — صفر LLM)
         → greeting | goal_stated | full_profile | question
       ↓
[3] onboarding_complete == 0؟ → One-shot FSM
    رسالة واحدة → LLM يستخلص NAME|GOAL|CATEGORY|LEVEL|HOURS|DAYS
    كل المعلومات موجودة → Researcher → Planner → complete=1
    لو ناقص → سؤال واحد عن اللي ناقص فقط
       ↓
[4] Date-Sync: gap = today - last_active
    gap ≥ 2 → Fixer(reason="gap", gap_days=gap)
       ↓
[5] Adaptive Challenge Check (v7.5)  ★ جديد
    هل النص يحتوي "سهل"/"too easy"/... ؟
    نعم → level_up() → fetch_learning_package() → return ⬆️ رد + package
       ↓
[6] Hybrid Router → route
       ↓
[7a] out_of_scope     → LLM رسالة رفض
[7b] content_question:
     ↓ Source Intercept (v7.3): هل هو سؤال مصدر؟
       نعم → fetch_learning_package() مباشرة → 📚📺✏️
       لا  → Researcher.fetch() (Query Grounding أولاً) → Coach.answer_question()
             هل المستخدم يقول "خلصت"/"done"? → fetch_learning_package(next_task)
[7c] plan_change      → Planner.revise()
[7d] daily_check      → Coach.daily_task() [Passive: DB read]
                         streak ≥ 3 → Fixer(reason="streak")
       ↓
[8] asyncio.create_task(background_discourse(...))  ← بعد الرد
       ↓
FastAPI → Telegram Bot → المستخدم
```

---

## 🔬 Learning Package Format (v7.4)

الـ Learning Package هو الوحدة الأساسية لتسليم المحتوى — لا قوائم، لا اقتراحات متعددة:

```
📚 المصدر الرئيسي: [عنوان] (URL من Tavily whitelist)
📺 الدعم البصري:  [YouTube direct watch URL أو Search Link]
✏️ التمرين العملي: [مهمة صغيرة ≤ 30 دقيقة مبنية على المحتوى أعلاه]
```

**متى يُرسَل:**
- طلب مصدر/رابط (Source Intercept)
- إكمال مهمة (Done → Next Package)
- ترقية مستوى (Level Upgrade → Package بالمستوى الجديد)

**مصادر:**
- Guide: أول URL من Tavily لـ `site:[whitelist_domain] {goal} {level} {task}`
- Video: `_generate_video_query()` → YouTube direct URL (regex `_YT_WATCH_RE`) أو Search fallback
- Exercise: LLM Synthesis مقيّد بالـ URL المختار — لا hallucination

---

## 🏗️ الوكلاء (v7.5)

### 0. Bootstrap Agent (Offline)
- يعمل مرة واحدة لكل مهارة: `python agents/bootstrap.py --skill X --category Y`
- يقرأ ملفات Markdown → LLM يستخرج: دروس، dependencies، weights، hours_std
- Pydantic يتحقق: مجموع weights = 1.0
- المخرج: `knowledge_base/<category>/<skill>/curriculum_map.json`

### 1. Onboarding Agent (One-shot FSM)
- رسالة واحدة تحتوي كل المعلومات → خطة فوراً (صفر أسئلة إضافية)
- Pipe extraction: `NAME|GOAL|CATEGORY|LEVEL|HOURS|DAYS`
- Defaults: hours=1.0, days=5, category=academic
- Big Picture First: يعرض الخطة الكاملة + أول Tavily URL حي عند الإكمال

### 2. Planner Agent (Hierarchical)
```
H_total = sum(lesson.weight × lesson.hours_std) × U_multiplier
U_multiplier: beginner=1.4, intermediate=1.0, advanced=0.75
W = ceil(H_total / (hours_per_day × days_per_week))
```
- Validation + Self-Correction: MAX_RETRIES=3
- Templates: 80/20_project_based | linear_mastery | habit_stacking | progressive_overload
- revise(): يعدّل الخطة الحالية بدون إعادة بناء
- rebuild(): يُعيد البناء من الصفر (عند gap > 3 days أو Consensus action=rebuild)

### 3. Researcher Agent (v7.x — Web-First)

**Pipeline المُفعَّل:**

| Tier | المصدر | الحالة |
|------|--------|--------|
| 1 | Local KB (Markdown) | ~~DISABLED~~ — SKIP_LOCAL_KB=True |
| 2 | LanceDB vector search | ~~PERMANENTLY DISABLED~~ — v7.1 |
| 3 | Tavily — whitelist native | ✅ PRIMARY |
| 4 | LLM Synthesis | ✅ FALLBACK — لا يقول "لا أعرف" |

**Query Grounding (v7.3):**
```python
_VAGUE_RE = re.compile(r'^(اي|اين|وين|ما|ايش|كيف|what|where|which|how|why|when)\b', ...)
if is_vague or goal_not_in_query:
    search_query = f"{profile.goal} {profile.level}"
```

**Domain-Aware Whitelist (v6.5):**
- يكتشف: code | language | fitness | professional | general
- يختار domains حسب النطاق + المستوى
- beginner language: BBC, British Council, Cambridge, Duolingo...
- beginner code: w3schools, geeksforgeeks, realpython, freecodecamp...
- advanced: arxiv, IEEE, Economist, TED...

**KB_ONLY_MODE=true:** emergency kill-switch يوقف Tavily فقط (Tier 3) — لا يوقف LLM Synthesis

### 4. Coach Agent (Passive Mode + v7.x)
- `daily_task()`: يقرأ `daily_tasks` table — صفر LLM في الحالة العادية
- `answer_question()`: max_tokens=600 (رُفع من 300 — v7.3)
- **Khyres Elite Coach Persona** (`_sentinel_persona()`):
  - هدف هندسي → "senior EE engineer" + EE analogies
  - هدف عام → "focused professional coach"
  - **Anti-hallucination (v7.3):** لا يذكر Datadog/Wikipedia/أي منصة إلا إذا وردت في context حرفياً
- **Sentiment Awareness**: إشارات إحباط → `_micro_task_reply()` (مهمة ≤15 دقيقة)
- **Semantic Gap injection**: Researcher كشف فهماً سطحياً → يُضيف Practical Challenge
- **Done → Next Package (v7.4)**: "خلصت"/"done" → تشجيع + fetch_learning_package(next_task)

### 5. Fixer Agent (3 Triggers)
| المُشغّل | الشرط | الإجراء |
|---------|-------|---------|
| streak | failure_streak >= 3 | LLM رسالة تحفيزية + reset streak |
| gap ≤ 3 أيام | gap >= 2 days | reschedule missed tasks (pure DB) |
| gap > 3 أيام | gap > 3 days | Planner.rebuild() |
| consensus warning | streak == 2 | Consensus Engine ينبّه مبكراً |
| milestone verdict | آخر task في milestone | Consensus → milestone.completed=1 |

---

## ⚙️ Tech Stack (v7.5)

| الطبقة | الأداة |
|--------|--------|
| LLM الرئيسي | Gemini Flash — google-genai SDK مباشرة |
| LLM الاحتياطي | Claude Sonnet (fallback — غير مفعّل) |
| Orchestration | Python Orchestrator — Explicit routing (لا CrewAI agents) |
| Async DB | aiosqlite (كل DB calls async) |
| API Layer | FastAPI |
| Data Validation | Pydantic v2 |
| Interface | python-telegram-bot 21.10 |
| Database | SQLite + WAL Mode (PRAGMA journal_mode=WAL إلزامي) |
| KB Engine | Markdown (Gen 1) — LanceDB disabled |
| Web Search | Tavily API — primary (KB_ONLY_MODE=true يوقفه) |
| Monitoring | Streamlit Dashboard — 5 tabs |
| Python | 3.11.9 |

---

## 🗄️ Database Schema

```
luminagents.db (10 جداول)

users:
  user_id, name, goal, category, level
  hours_per_day, days_per_week, estimated_weeks, start_date, language
  onboarding_complete (0/1)
  onboarding_step: awaiting_goal | awaiting_level | complete
  partial_profile (JSON string)
  age, weight, height (nullable — physical category فقط)
  agent_name, agent_vibe (Hazem Protocol)

milestones:       title, week_start, week_end, lesson_ids (JSON), completed (0/1)
daily_tasks:      day, week, lesson_id, description, hours, completed
snapshots:        ملخص pipe-format: GOAL|WEEKS|M1>M2>M3|Xh*Yd (~15 tokens)
context_frames:   Researcher→Planner handoff (frame_json)
failure_log:      failure_streak, gap_days, last_active
tasks:            backward compat + streak tracking
sources:          audit trail
agent_log:        agent, action, route, detail, tokens_est, duration_ms, ts
archived_skills:  goal, level, milestones, success_rate, snapshot (Hot Swap archive)
security_audit:   input_hash (SHA-256[:16]), route, model,
                  tokens_in, tokens_out, duration_ms, status
```

---

## 📐 Schemas (models/schemas.py)

```python
OnboardingInput   # user input — is_complete property (deterministic)
UserProfile       # + FSM fields + physical fields
LessonNode        # id, title, weight (0,1], depends_on[], hours_std
CurriculumMap     # validator: sum(weights) ≈ 1.0 ± 0.01
ContextFrame      # Researcher→Planner handoff
MacroPlan         # milestones[], template, snapshot
MicroPlan         # daily_tasks[], h_total, total_days
DailyTask         # day, week, lesson_id, description, hours
ValidationResult  # passed, h_total, h_available, delta, error_trace
CoachReport       # + day_index
FixerTrigger      # reason: streak|gap|manual_request|behavior
FixerReport       # message, rescheduled, rebuilt, streak_reset
SemanticGapResult # gap_detected: bool, challenge_hint: str
ConsensusResult   # coach_view, fixer_view, decision, action
                  # action: proceed|proceed_adjusted|simplify|rebuild
```

---

## 🌐 REST API Endpoints

```
POST /start     ← Onboarding (FSM)
POST /message   ← كل رسائل المستخدم
GET  /progress  ← حالة المستخدم + streak + current_day
GET  /plan      ← Macro + Micro plan
GET  /health    ← health check
```

---

## 🌐 دعم اللغتين

- `detect_language()`: نسبة الأحرف العربية ≥ 30% → `ar`
- كل رد يمر على LLM — صفر نصوص ثابتة (ماعدا static greeting)
- تغيير اللغة في الجلسة يُحدّث `users.language` في DB

---

## 🔒 القواعد التقنية الذهبية (لا تكسرها)

1. **Explicit Routing فقط** — CrewAI للـ LLM wrapper فقط، لا orchestration
2. **`/setup` محذوف** — onboarding بلغة طبيعية. LLM يستخلص البيانات
3. **Fixer عند `failure_streak >= 3` فقط** — يصفّر العداد فوراً في DB
4. **`SKIP_LOCAL_KB = True`** — ثابت (hard-coded)، لا تغيّره
5. **Snapshot Pattern** — Planner يحفظ summary مضغوط عند كل milestone، Coach يقرأه بدل إعادة البناء
6. **`detect_language()`** — تعتمد على نسبة الأحرف العربية. صفر نصوص ثابتة
7. **WAL Mode** — `PRAGMA journal_mode=WAL` إلزامي على كل اتصال DB
8. **لا hallucination** — Coach لا يذكر مصادر خارجية إلا إذا وردت في context
9. **Learning Package لا قوائم** — Source Intercept → fetch_learning_package() دائماً
10. **18/18 قبل كل commit** — `DEMO_MODE=true venv\Scripts\python.exe test_scenarios.py`

---

## 📋 Changelog

| الإصدار | التاريخ | التغييرات الرئيسية |
|---------|---------|-------------------|
| v7.5 | 2026-05-09 | Adaptive Challenge: "too easy" → level up → new Package |
| v7.4 | 2026-05-09 | Done → auto-fetch next Learning Package |
| v7.3 | 2026-05-09 | Source Intercept, Query Grounding, anti-hallucination, session-start guard |
| v7.2 | 2026-05-09 | Web-First enforcement, fetch_learning_package() format |
| v7.1 | 2026-05-09 | LanceDB permanently disabled |
| v6.4 | 2026-05-09 | Leakage Fix, Reset Pulse Guard, Adaptive Sourcing, Khyres Identity |
| v6.3 | 2026-05-08 | Background Discourse, Stage-Gate, Behavioral Pulse, /reset |
| v6.0 | 2026-05-07 | Dependency Graph, Security Audit, Milestone Verdict, YouTube Intelligence |
| v5.4 | 2026-05-06 | Hazem Protocol, Hot Swap, Resurrection |
| v5.1 | 2026-05-05 | Consensus Engine, Semantic Gap, 4-Tier Researcher |
