# LuminAgents — Master Protocol
> Version: 1.0 | Stack: FastAPI + SQLite + Gemini Flash | Bilingual: AR/EN

---

## 1. Agent Boundaries

| Agent | Owns | Cannot Do |
|-------|------|-----------|
| Onboarding | Profile extraction, language detection | Plan generation, Q&A |
| Planner | Milestone + daily task generation, Snapshot creation/update | User interaction |
| Researcher | KB lookup → Tavily fallback | Direct user replies |
| Coach | Daily task delivery, content Q&A, sentiment-aware pivots | Plan modification |
| Fixer | Streak/gap intervention, plan rebuild trigger | Normal coaching |

---

## 2. Routing Priority (Immutable)

```
out_of_scope > plan_change > content_question > daily_check
```

- Tier-1: regex in `message_router.py` — zero cost
- Tier-2: LLM fallback only for uncertain cases (`max_tokens=10`)
- Out-of-scope → `get_out_of_scope_reply()` — no researcher, no coach

---

## 3. Tone Contract

- **Default**: Encouraging but data-driven. Never generic praise ("Great job!").
- **On frustration/burnout**: See §4. Reduce scope, validate, pivot to Micro-Task.
- Zero hardcoded response strings — every reply via `call_llm()`.
- Bilingual: `detect_language()` determines AR/EN per message. Never mix in same reply.
- Language updates: if user switches language mid-session, `_update_language()` fires.

---

## 4. Tone-Switch Logic (Sentiment-Aware)

**Trigger signals** (injected into Coach prompt when detected):

| Language | Signals |
|----------|---------|
| AR | صعب، تعبان، مو قادر، محبط، ما فيه فايدة، استسلمت، تعبت، مش قادر، صعبة |
| EN | too hard, burned out, can't do this, frustrated, giving up, exhausted, overwhelmed, stuck, hopeless |

**Response protocol when frustrated:**
1. Validate the feeling — 1 sentence, no toxic positivity
2. Propose a Micro-Task (≤15 min, a subset of today's task)
3. Do NOT penalize streak on micro-task acceptance
4. Implementation: inject `FRUSTRATION_HINT` into Coach's `answer_question()` and `daily_task()` prompts

---

## 5. Memory / Snapshot Protocol

- **Trigger**: Planner saves 1 snapshot per plan build (milestone index 0 = initial plan)
- **Format** (pipe-separated, machine-readable):
  ```
  GOAL|TOTAL_WEEKS|M1>M2>M3|Xh*Yd
  ```
  Example: `Python|12|Foundations>Core>Practice>Project|1.5h*5d`
- **Max tokens**: ~20 tokens (enforced in `_make_snapshot()`)
- **Coach reads**: `_get_snapshot()` → injects as compressed context, not full milestone history
- **User display**: snapshot is rendered via LLM into natural language when shown to user

---

## 6. Token Budget (Per Agent Call)

| Call | `max_tokens` |
|------|-------------|
| Router LLM fallback | 10 |
| FSM extraction (pipe format) | 50 |
| Relevance check | 10 |
| Coach Q&A | 300 |
| Planner batch descriptions | 600 |
| Planner milestone titles | 200 |
| Planner rebuild/revise | 150 |
| Fixer message | 100 |

---

## 7. Fixer Rules (Non-Negotiable)

- Trigger ONLY at `failure_streak >= 3` OR `date_gap >= 2`
- Reset `failure_streak` to 0 in SQLite **immediately** after intervention
- Fixer does NOT coach — it resets state and delegates rebuild to Planner
- Fixer is separate from Coach — never merge their logic

---

## 8. KB-Only Mode

- Env var: `KB_ONLY_MODE=true` → disables Tavily fallback in `researcher.py`
- When KB returns empty → reply "لا معلومات كافية" / "Not enough info" — do NOT improvise
- Tag match alone is insufficient — require semantic relevance to user's actual question

---

## 9. Database Rules

- `PRAGMA journal_mode=WAL` on every connection — no exceptions
- Test DB: separate file in `%TEMP%`, never touch `luminagents.db`
- Before every commit: `python test_scenarios.py` → must be 15/15
