# LuminAgents — AI Skill Coaching System

> **Agenticthon 2026 — Prince Sattam Bin Abdulaziz University**
> Team: Ahmed, Khyri, Abdulrahman

A bilingual (Arabic/English) multi-agent system that acts as a personal skill coach via Telegram. It builds a personalized learning plan, tracks daily progress, and adapts coaching based on user behavior — all powered by Gemini Flash with a FastAPI backend and Streamlit dashboard.

---

## Architecture

```
User (Telegram)
      │
      ▼
 Orchestrator  ──→  Router (5 routes)
      │
      ├──→  Onboarding Agent   — extracts goal, level, schedule via NLP
      ├──→  Planner Agent      — generates milestone-based weekly plan
      ├──→  Researcher Agent   — fetches content (Tavily + KB)
      ├──→  Coach Agent        — daily check-ins, explanations, feedback
      └──→  Fixer Agent        — activates at failure_streak ≥ 3
```

**Tech Stack:** Python 3.11 · FastAPI · python-telegram-bot · Gemini Flash (primary) · Claude Sonnet via LiteLLM (fallback) · SQLite WAL · Streamlit · Tavily

---

## Prerequisites

- Python 3.11.x
- A Telegram Bot token (from [@BotFather](https://t.me/BotFather))
- A Gemini API key (from [Google AI Studio](https://aistudio.google.com))
- A Tavily API key (from [tavily.com](https://tavily.com)) — optional, for web search
- An Anthropic API key — optional, used as LLM fallback

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/LuminAgents.git
cd LuminAgents

python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

```env
GEMINI_API_KEY=your-gemini-key-here
TELEGRAM_BOT_TOKEN=your-telegram-bot-token-here
TAVILY_API_KEY=your-tavily-key-here        # optional
ANTHROPIC_API_KEY=your-anthropic-key-here  # optional fallback
DEMO_MODE=false
```

### 3. Run

Open **3 terminals** and run each command in a separate one:

```bash
# Terminal 1 — API server
python -m uvicorn api.main:app --reload --port 8000

# Terminal 2 — Telegram bot
python telegram_bot.py

# Terminal 3 — Dashboard (optional)
streamlit run dashboard/streamlit_app.py
```

Or use the provided batch files on Windows:

```
run_api.bat
run_bot.bat
run_dashboard.bat
```

---

## Quick Start (Demo Mode)

To test without any API keys:

```bash
# In .env, set:
DEMO_MODE=true
```

Then run `python test_scenarios.py` — all 18 scenarios should pass.

---

## Testing

```bash
python test_scenarios.py
```

Expected: **18/18 passed** — uses `DEMO_MODE=true` internally, no API credits consumed.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System status + DB check |
| POST | `/start` | Onboard a new user |
| POST | `/message` | Send a message to the orchestrator |

Full interactive docs: `http://localhost:8000/docs`

---

## Key Features

- **Natural language onboarding** — no `/setup` commands, LLM extracts goal/schedule from free text
- **5-agent architecture** — strict explicit routing, no autonomous agent selection
- **Bilingual** — detects Arabic/English per message, responds accordingly
- **Stage-Gate** — sequential content lock until current week's tasks are complete
- **Behavioral Pulse** — detects inactivity/repeated failures, triggers recovery menu
- **Milestone Consensus** — Coach + Fixer verify milestone completion before advancing
- **Security Audit Log** — every LLM call is hashed and logged with token counts
- **Streamlit Dashboard** — live agent activity, dependency graph, security stats

---

## Project Structure

```
LuminAgents/
├── agents/          # 5 agents: onboarding, planner, researcher, coach, fixer
├── api/             # FastAPI routes
├── dashboard/       # Streamlit monitoring dashboard
├── db/              # SQLite + WAL database layer
├── llm/             # LiteLLM client with audit logging
├── models/          # Pydantic schemas
├── prompts/         # Prompt templates
├── tools/           # Router, consensus, semantic tools
├── knowledge_base/  # Tag-based Markdown KB (academic, professional, personal)
├── orchestrator.py  # Central routing + behavioral logic
├── telegram_bot.py  # Bot entry point
└── test_scenarios.py
```

---

## License

MIT
