# AI Learning Digest Agent

A lightweight daily agent that curates the best articles and YouTube videos published in the last 7 days to help you learn about Generative AI, Agentic AI, Agentic Coding, Prompt Engineering, and AI Research — delivered as a clean, self-contained HTML report.

---

## Objective

Keep up with the fast-moving AI learning landscape without spending hours searching. Each morning the agent:

1. Searches the web **and YouTube** for fresh educational content across 5 AI topics.
2. Uses Claude AI to curate the best resources and explain why each one is worth your time.
3. Produces a **"Concept of the Day"** — a plain-English explanation of one key AI concept.
4. Saves a dated HTML report to the `reports/` folder, ready to open in any browser.

---

## Covered Topics

| Topic | What you will learn |
|---|---|
| **Generative AI** | Core concepts, new capabilities, tutorials on LLMs and image/audio models |
| **Agentic AI** | How AI agents work, tool use, multi-agent systems, memory and planning patterns |
| **Agentic Coding** | AI-powered development tools (Claude Code, Cursor, Devin), coding agent workflows |
| **Prompt Engineering** | Techniques to get better results from LLMs |
| **AI Research Explained** | Recent papers broken down in plain English |

---

## How It Works

```
┌─────────────────────────────────────────────────┐
│  Windows Task Scheduler  (daily at 03:00 GMT)   │
└────────────────────┬────────────────────────────┘
                     │ runs
                     ▼
              run_agent.bat
                     │ activates venv, calls
                     ▼
               agent.py
        ┌────────────┴────────────────────────────┐
        │  1. Search (Tavily API)                  │
        │     2 queries × 5 topics = 10 searches  │
        │     - web articles & tutorials           │
        │     - YouTube videos (site:youtube.com) │
        │     topic=general, days=7               │
        └────────────┬────────────────────────────┘
                     │ raw results (deduplicated)
                     ▼
        ┌─────────────────────────────────────────┐
        │  2. Curate (Claude Haiku)                │
        │     Single API call that returns:        │
        │     - 2-4 best resources per topic       │
        │     - type, difficulty, time estimate    │
        │     - "why learn this" per resource      │
        │     - Concept of the Day                 │
        └────────────┬────────────────────────────┘
                     │ structured JSON
                     ▼
        ┌─────────────────────────────────────────┐
        │  3. Generate HTML report                 │
        │     - Concept of the Day section         │
        │     - Per-topic cards                    │
        │     - Article / Video badges             │
        │     - Difficulty & time estimate tags    │
        │     - Dark mode support                  │
        └─────────────────────────────────────────┘
                     │
                     ▼
        reports/YYYY-MM-DD-ai-learning.html
```

### Key design decisions

- **7-day window** — Learning content doesn't expire overnight. A great tutorial from 5 days ago is more valuable than a shallow post from this morning.
- **YouTube included** — Each topic runs a second query with `site:youtube.com` so both articles and videos are surfaced.
- **Single Claude call** — All topics are summarised in one Haiku request to minimise cost and latency.
- **Deduplication** — URLs are deduplicated across queries per topic before sending to Claude.
- **Skip-if-exists guard** — If today's report already exists the agent exits without any API calls.

---

## Report Layout

```
┌──────────────────────────────────────────────┐
│  AI Learning Digest · 2026-03-09             │
│  14 resources · Gen AI · Agentic AI · ...    │
├──────────────────────────────────────────────┤
│  CONCEPT OF THE DAY                          │
│  "Tool Use in AI Agents"                     │
│  Plain-English 3-sentence explanation...     │
├──────────────────────────────────────────────┤
│  Agentic AI                    3 resources   │
│  ▶ Video  | Intermediate | ⏱ 14 min         │
│  How ReAct agents plan and use tools →       │
│  Why learn this: ...                         │
│                                              │
│  📄 Article | Beginner | ⏱ 6 min read       │
│  Building your first AI agent with ...  →    │
│  Why learn this: ...                         │
├──────────────────────────────────────────────┤
│  Agentic Coding                2 resources   │
│  ...                                         │
└──────────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Windows 10/11 | Scheduler setup uses Windows Task Scheduler |
| Python 3.10+ | Must be on your `PATH` |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| Tavily API key | [app.tavily.com](https://app.tavily.com) |

---

## Installation

### 1. Clone or download the project

```
C:\MyProjects\ai-news-agent\
```

### 2. Create your `.env` file

Create a file named `.env` in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
```

### 3. Run the one-time setup

Double-click **`setup.bat`** or run from a terminal:

```bat
setup.bat
```

This will:
- Create a Python virtual environment (`venv/`)
- Install all dependencies from `requirements.txt`
- Register a **Windows Task Scheduler** job (`AI-News-Agent-Daily`) that runs every day at **03:00 GMT**
- If your PC was off at 03:00, the task runs automatically on next startup

> **Note:** The scheduler step may show a UAC prompt — click **Yes**.

---

## Running Manually

```bat
run_agent.bat
```

Or with Python directly (inside an activated venv):

```bash
python agent.py
```

---

## Output

Reports are saved to:

```
reports/
└── 2026-03-09-ai-learning.html
```

Open any `.html` file in your browser. Each report:
- Shows a **Concept of the Day** at the top
- Lists curated resources per topic with article/video badges
- Includes difficulty level (Beginner / Intermediate / Advanced) and estimated time
- Links directly to the source (article or YouTube video)
- Supports light and dark mode automatically
- Is fully self-contained (no external dependencies)

---

## Project Structure

```
ai-news-agent/
├── agent.py               # Main agent logic
├── requirements.txt       # Python dependencies
├── setup.bat              # One-time setup (venv + scheduler)
├── run_agent.bat          # Manual run shortcut
├── setup_scheduler.ps1    # Registers the Task Scheduler job
├── agent.log              # Runtime log (created on first run)
├── .env                   # Your API keys (not committed to git)
└── reports/
    └── YYYY-MM-DD-ai-learning.html
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic` | Claude Haiku API client for curation and summarisation |
| `tavily-python` | Web + YouTube search API client |
| `python-dotenv` | Loads `.env` file into environment variables |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Dependencies missing` error | Run `setup.bat` first |
| `Missing API keys` error | Check your `.env` file has both keys |
| Report not generated | Check `agent.log` for details |
| Scheduled task not running | Open Task Scheduler, find `AI-News-Agent-Daily`, run it manually to test |
| UAC / permission error during setup | Right-click `setup.bat` → **Run as administrator** |
| No YouTube results | Tavily indexes YouTube — results depend on availability for that query and week |
