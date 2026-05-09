# DEMO_REHEARSAL.md — LuminAgents v5.4 (Agenticthon 2026)

> **الهدف:** بروفة Demo قابلة للتنفيذ في 8-10 دقائق، تغطي كل المعمار الذهبي،
> ومرنة كفاية إن القاضي يسأل عن أي مهارة. كل خطوة فيها **Expected Output**
> + **Fallback** إن انكسرت.

---

## 0) Pre-Flight Checklist (T-30 دقيقة)

### A. متغيرات البيئة (`.env`)

```bash
# لازمة (real keys في الديمو الحي — DEMO_MODE=false)
GEMINI_API_KEY=...           # primary LLM
ANTHROPIC_API_KEY=...        # fallback عبر LiteLLM
TELEGRAM_BOT_TOKEN=...
ALLOWED_USERS=<chat_id_1>,<chat_id_2>   # حسابك + حساب جهاز القاضي

# اختيارية
TAVILY_API_KEY=...           # لو بنعرض Tier 3
KB_ONLY_MODE=false           # خله false في الديمو لإظهار Tier 4 synthesis
DEMO_MODE=false              # حي: false. للبروفة الجافة: true
```

### B. حالة الـ DB

```bash
# قبل الديمو، صفّر luminagents.db لمستخدم الاختبار فقط (مو reset كامل)
sqlite3 luminagents.db "DELETE FROM users WHERE user_id = '<judge_chat_id>';"
sqlite3 luminagents.db "DELETE FROM milestones WHERE user_id = '<judge_chat_id>';"
sqlite3 luminagents.db "DELETE FROM agent_log WHERE user_id = '<judge_chat_id>';"
sqlite3 luminagents.db "DELETE FROM archived_skills WHERE user_id = '<judge_chat_id>';"

# تأكد من WAL mode
sqlite3 luminagents.db "PRAGMA journal_mode;"   # توقّع: wal
```

### C. تسخين الـ KB

تأكد إن knowledge_base/ فيه ملفات Markdown لـ 3 مهارات على الأقل:

- `python_beginner.md`, `python_intermediate.md`
- `data_analysis_beginner.md`
- `english_beginner.md`

**لماذا:** المهارة المختارة تعتمد عليه. لو مفقودة → الـ Researcher يسقط لـ Tier 4 (LLM Synthesis) — وهذي ميزة تباع كـ "graceful degradation".

### D. اختبار صحة فوري

```bash
# الاختبارات
DEMO_MODE=true python test_scenarios.py    # متوقع: 18/18

# تشغيل فعلي بـ DEMO_MODE=true (دون حرق API)
DEMO_MODE=true python -c "
from orchestrator import LuminAgentsOrchestrator
import asyncio
orc = LuminAgentsOrchestrator()
print(asyncio.run(orc._handle_message_async('test_user', 'هلا')))
"
```

---

## 1) Demo Flow — 7 Steps

### نظرة عامة على الإعداد المسرحي

- **شاشة يسار:** هاتف يعرض Telegram (القاضي يقدر يأخذ الجهاز ويسأل بنفسه).
- **شاشة يمين:** لابتوب يعرض **Streamlit Dashboard** (`agent_log` + plan + Consensus + Hot Swap timeline).
- **خطة احتياطية:** فيديو screencast 90 ثانية للمسار كاملاً، يشتغل لو الإنترنت انقطع.

---

### الخطوة 1 — Cold Start (Sentinel Greeting)

**Action:** أرسل `/start` بالعربي.

**Expected Output (Telegram):**
```
⚡ أنا The Sentinel — مدربك الشخصي للمهارات في LuminAgents.
أبني لك خطة تعلم مخصصة بالكامل، خطوة بخطوة...
أخبرني في رسالة واحدة:
• اسمك  • المهارة...  • مستواك  • كم ساعة يومياً
```

**ما يحصل خلف الكواليس:**
- صفر استدعاء LLM (instant response).
- `_create_partial_user()` ينشئ profile stub في DB.

**Dashboard:** صف جديد في `users` بـ `onboarding_complete=0`.

**Talking Point:** *"عشان نقلل التكلفة والـ latency، الترحيب الأول templated. الـ LLM يدخل بس لما لازم."*

**Fallback:** لو الـ bot ما رد → افتح Streamlit، اعرض الـ greeting من orchestrator مباشرة.

---

### الخطوة 2 — Onboarding بلغة طبيعية (One-Shot Extraction)

**Action:** اكتب جملة واحدة طبيعية، مثلاً:
> *"أنا أحمد، أبي أتعلم Python، مستواي مبتدئ، ساعتين يومياً 4 أيام في الأسبوع"*

**Expected Output:**
```
رائع أحمد! 🎯 خطتك جاهزة.
خطة 6 أسابيع لـ Python:
الأساسيات → المفاهيم الجوهرية → التطبيق العملي
```

**ما يحصل:**
- `OnboardingAgent` يستخرج (name, goal, level, hours, days) في استدعاء LLM واحد.
- معادلة `W = ceil((H_base / (h × d)) × 1.2)` تحسب 6 أسابيع.
- `Planner.build()` يولد 3 milestones.

**Dashboard:** جدول `milestones` فيه 3 صفوف، `users.onboarding_complete=1`.

**Talking Point:** *"حذفنا `/setup` بالكامل. الـ LLM يستخرج 5 حقول من جملة واحدة. والـ ×1.2 معامل واقعية مبني على دراسات تعلم الكبار."*

**Fallback:** لو الاستخراج فشل → الـ FSM يرجع لـ `awaiting_level` ويسأل سؤال محدد.

---

### الخطوة 3 — Daily Check (Coach Passive Mode)

**Action:** أرسل `"هلا"` أو `"صباح الخير"`.

**Expected Output:**
```
أهلاً أحمد! مهمة اليوم: جلسة Python لمدة 30 دقيقة على الأساسيات.
سجّل تقدمك لما تخلص.
```

**ما يحصل:**
- `regex` ضمن `_GREETING_PATTERNS` يلتقط الترحيب.
- Coach يقرأ `daily_task` من snapshot — **زيرو LLM**.

**Talking Point:** *"الـ snapshot pattern يحفظ summary مضغوط عند كل milestone. بدل ما نعيد بناء prompt كامل كل مرة، Coach يقرأ مباشرة."*

**Dashboard:** صف جديد في `agent_log` بـ `agent='coach'`, `tokens_est=0`.

---

### الخطوة 4 — Content Question + Semantic Gap

**Action:** اسأل سؤال تقني عن المهارة:
> *"ايش الفرق بين list و tuple في Python؟"*

ثم رد رد سطحي عمداً:
> *"تمام فهمت"*

**Expected Output (Step 4a — السؤال):**
- إجابة من 3-4 نقاط من الـ KB.

**Expected Output (Step 4b — الرد السطحي):**
- إجابة Coach + **Practical Challenge** ملحقة:
> *"تحدي: اكتب مثال صغير تستخدم فيه list mutability."*

**ما يحصل:**
- `Researcher.fetch()` يمر على Tier 1 (KB) → يلقى chunks.
- `Researcher.evaluate_comprehension()` يقارن عمق الرد بمصدر KB → `gap_detected=True`.
- Coach يحقن Practical Challenge في الرد.

**Dashboard:** سطر `semantic_gap` في `agent_log`.

**Talking Point:** *"الـ Semantic Gap detection يميّز الفهم السطحي عن العميق. لو سطحي، نضيف تحدي عملي بدل ما نمشي للموضوع التالي."*

**Fallback (للقاضي اللي يسأل عن مهارة غير مدعومة):**
- Tier 1 KB يرجع فاضي → Tier 2 Wikipedia → Tier 3 Tavily (مع whitelist) → Tier 4 LLM Synthesis (Foundational Concept Guide).
- **النقطة المسرحية:** *"ما نرجع `NO_INFO` للقاضي أبداً. حتى لو ما عندنا KB، الـ LLM Synthesis يولّد دليل مفاهيم أساسي + يسأل القاضي عن مرجعه المفضل."*

---

### الخطوة 5 — Plan Change → Consensus Engine

**Action:**
> *"ما عندي وقت اليوم، أبي أخفف"*

**Expected Output:**
- رد متوازن: *"عدّلت خطتك. خفّضت الجلسة لـ 20 دقيقة. واصل بخطوات أصغر."*

**ما يحصل (هذا الـ wow factor الحقيقي):**
- Router يصنّف: `route=plan_change`.
- `run_consensus()` يطلق **Coach vs Fixer** بالتوازي (`asyncio.gather`).
- Coach يقول: *"الزخم قائم — تخفيف خفيف يكفي"*.
- Fixer يقول: *"إشارات ضغط — خفّض 20%"*.
- Orchestrator يصنّف القرار النهائي.

**Dashboard:** **3 صفوف متتالية** في `agent_log` (coach / fixer / orchestrator) — اعرضها.

**Talking Point:** *"بدل ما agent واحد يقرر، Coach و Fixer يتجادلوا بالتوازي. الـ orchestrator يصنّف. هذا مو CrewAI auto-orchestration — هذا routing صريح، deterministic، اختبار له."*

---

### الخطوة 6 — Failure Streak → Fixer Recovery

**Action:** أرسل 3 رسائل فشل متتالية:
> *"ما قدرت اليوم"* × 3

**Expected Output (الرسالة الثالثة):**
```
وقعت في حائط — هذا طبيعي تماماً! خلنا نبسّط ونمشي خطوة خطوة.
بعدّل خطتك لتكون أسهل. الآن 30 دقيقة باليوم بدل ساعة. تقدر!
```

**ما يحصل:**
- بعد 3 fails: `failure_streak >= 3` يطلق `Fixer.intervene_streak()`.
- Plan rebuild + `failure_streak = 0` فوراً.

**Dashboard:** عمود `failure_streak` ينزل من 3 إلى 0.

**Talking Point:** *"Fixer منفصل عن Coach. ما يدخل إلا عند الفشل المتكرر. ويصفّر العداد عشان ما يدخل في حلقة لا نهائية."*

---

### الخطوة 7 — Hot Swap + Resurrection

**Action (Step 7a — Hot Swap):**
> *"أبي أغير مهارتي، أبي أتعلم تحليل البيانات"*

**Expected Output:**
```
تم أرشفة مهارتك السابقة (Python) ويمكنك العودة إليها لاحقاً.
أخبرني بمهارتك الجديدة ومستواك ووقتك اليومي.
```

**Action (Step 7b — Resurrection بعد ما يبدأ data analysis):**
> *"أبي أرجع لـ Python"*

**Expected Output:**
- النظام يلقى الـ archived skill → يستعيد الـ milestones والـ snapshot.

**ما يحصل:**
- `_archive_and_reset()` ينقل الـ skill لـ `archived_skills` (مو DELETE).
- `_check_resurrection()` يبحث في الأرشيف عند ذكر مهارة قديمة.

**Dashboard:** جدول `archived_skills` فيه entry جديد بـ `success_rate`.

**Talking Point:** *"Hot Swap = أرشفة، مو حذف. كل مهارة عمل عليها المستخدم محفوظة. لو رجع لها بعد شهر، يكمل من نفس النقطة."*

---

## 2) Q&A Cheat Sheet — أجوبة للقاضي

| السؤال المتوقع | الجواب |
|---|---|
| *ليش ما تستخدمون CrewAI؟* | استخدمنا في v3 — الـ agents كانت تختار orchestration بنفسها وكسرت الـ determinism. v5 رجعنا لـ explicit routing. أسرع بـ 3x، اختباره ممكن. |
| *كيف تتعامل مع الـ hallucinations؟* | 4 tiers: KB أولاً (ground truth)، ثم Wikipedia local (vector + goal filter)، ثم Tavily (whitelist)، ثم LLM Synthesis مع تنبيه واضح. |
| *الـ Consensus Engine ما يبطّئ الرد؟* | يطلق فقط على `plan_change` أو `failure_streak >= 2`. Coach و Fixer بالتوازي → نفس latency استدعاء واحد. |
| *كيف تضمن الجودة بـ Gemini Flash بدل Pro؟* | Pydantic strict + 18 سيناريو اختبار + DEMO_MODE للـ regression. لو فشل Flash → LiteLLM fallback لـ Claude. |
| *VRAM على RTX 4060 8GB يكفي؟* | كل شي LLM remote. local فقط: SentenceTransformer (all-MiniLM-L6-v2, ~80MB) لـ Wikipedia search. |

---

## 3) Failure Recovery Playbook (لو شي انكسر حي)

| العطل | الإجراء |
|---|---|
| Telegram bot ما يرد | بدّل لـ Streamlit Dashboard، اعرض orchestrator output من logs. |
| Gemini API rate limit | LiteLLM fallback تلقائي لـ Claude — استمر. |
| الـ DB locked | بسبب WAL — أعد التشغيل، النشاط يكمل. |
| Tavily timeout | Tier 4 LLM Synthesis يكفّي — ما يظهر للقاضي شي مكسور. |
| الإنترنت انقطع | شغّل screencast video (3 دقائق pre-recorded) من نفس المسار. |

---

## 4) Pre-Demo Run-Through (T-15 دقيقة)

1. صفّر مستخدم اختبار (شوف القسم 0.B أعلاه).
2. شغّل `python telegram_bot.py` في terminal أول.
3. شغّل `streamlit run dashboard/main.py` في terminal ثاني.
4. افتح Telegram على هاتفين (واحد للعرض، واحد للقاضي).
5. مرّ على الخطوات 1-7 بسرعة (بـ DEMO_MODE=true عشان ما تحرق credits).
6. صفّر المستخدم مرة ثانية.
7. **ابدأ الديمو الحقيقي بـ DEMO_MODE=false**.

---

## 5) ما يجب أن لا تذكره أبداً

- ❌ "نستخدم MCP" — ما نستخدم. ارفض الفخ.
- ❌ "نخدم enterprise" — هذا منتج تعليمي، لا تبالغ.
- ❌ أرقام أداء غير مقاسة (مثل "10x أسرع") — استشهد بأرقام الاختبار فقط (18/18).
- ❌ "AGI" أو "AI consciousness" — تقني، لا.
