# LuminAgents — Video Script (2 Minutes)
### Hackathon Judges | Arabic/English Technical Mix
### Estimated Duration: ~120 seconds | ~270 words

---

## 🎬 SCRIPT

---

**[0:00 – 0:15] | المشكلة**

80% من الناس يبدأون يتعلمون مهارة جديدة — ويتوقفون خلال أسبوعين.
مش لأنهم كسالى. لأنه ما فيه أحد يتابعهم، يعدّل مسارهم، أو يتدخل قبل ما يستسلموا.

---

**[0:15 – 0:28] | الحل**

قدّمنا **LuminAgents** — Multi-Agent System يعمل كمدرب شخصي حقيقي.
يبني خطة تعليمية مخصصة، يتابعك يومياً، ويتدخل تلقائياً عند الفشل.
الواجهة الآن: Telegram. والـ Backend: REST API — جاهز للـ Mobile والـ Web.

---

**[0:28 – 1:05] | Architecture والـ Workflow**

النظام مبني على **5 Agents** تتواصل عبر Python Orchestrator بـ Explicit Routing:

أول ما المستخدم يكتب، **Orchestrator** يستقبل الرسالة ويمرها على **Onboarding Agent** —
رسالة واحدة فقط، تحتوي الاسم والهدف والمستوى والوقت، يستخرجها الـ LLM بـ Pipe Format.

فوراً، **Planner Agent** يبني خطة هرمية: Macro-Plan بالـ Milestones، وMicro-Plan بالمهام اليومية —
باستخدام Dependency Graph ومعادلة زمنية دقيقة: W = ⌈(H_total ÷ (h × d)) × 1.2⌉

**Researcher Agent** يسحب المحتوى من Knowledge Base محلية — بدون إنترنت — عبر Vector Search على Wikipedia dump بـ 48 جيجابايت.

**Coach Agent** يُرسل المهمة اليومية بـ Passive Mode — يقرأ من الـ Database مباشرة، صفر LLM Calls، تكلفة يومية تقريباً معدومة.

لو المستخدم فشل 3 مرات متتالية أو غاب يومين، **Fixer Agent** يتدخل تلقائياً:
يعيد الجدولة أو يبني الخطة من جديد، ويصفّر العداد في SQLite.

---

**[1:05 – 1:40] | نقاط القوة التقنية**

الـ Routing بـ Hybrid System: Regex أولاً للحالات الواضحة، ثم LLM Fallback للحالات الرمادية فقط.

الـ Database: SQLite مع WAL Mode وaiosqlite للـ Full Async — لا Lock، أداء عالٍ.

الـ LLM: Gemini 2.5 Flash مع thinking_budget=0 — سرعة قصوى بدون استهلاك tokens على Chain-of-Thought.

Sentiment Awareness في الـ Coach: يكشف إشارات الإحباط بالعربي والإنجليزي بدون API Call، ويحول لـ Micro-Task أقل من 15 دقيقة.

---

**[1:40 – 2:00] | الخاتمة**

LuminAgents مش مجرد Chatbot يجاوب أسئلة.
هو نظام وكلاء متكامل — يخطط، يتابع، يتدخل، ويتعلم من سلوكك.

مبني بـ FastAPI، Pydantic، SQLite، وKnowledge Base محلية بالكامل.
جاهز للتوسع. جاهز للنشر. جاهز لكم.

**شكراً.**

---

## ⏱️ Timing Guide

| القسم | المدة | الكلمات التقريبية |
|-------|-------|-------------------|
| المشكلة | 0:00–0:15 | 35 |
| الحل | 0:15–0:28 | 35 |
| Architecture + Workflow | 0:28–1:05 | 110 |
| نقاط القوة | 1:05–1:40 | 70 |
| الخاتمة | 1:40–2:00 | 30 |
| **المجموع** | **2:00** | **~280** |
