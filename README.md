# AI Learning Digest Agent

A lightweight daily agent that curates the best articles and YouTube videos published in the last 7 days — organized into a **Developer Track** and an **Architect Track** — and delivered as a clean, self-contained HTML report.

---

## Documentation

| Document | Audience | Description |
|---|---|---|
| [Architecture Guide](Documentation/ARCHITECTURE.md) | Developers & Architects | Full pipeline, tech stack, data schemas, AWS infrastructure, environment variables, cost estimates |
| [User Guide](Documentation/USER_GUIDE.md) | End Users | What env vars do, step-by-step AWS Console instructions, how to test, how to monitor, troubleshooting |

---

## Objective

Keep up with the fast-moving AI landscape without spending hours searching. Each morning the agent:

1. Searches the web **and YouTube** for fresh educational content across 10 AI topics.
2. Uses Claude Haiku to curate the best resources per track and explain why each one is worth your time.
3. Produces a **"Concept of the Day"** — a plain-English explanation of one key AI concept.
4. Saves a dated HTML report to the `reports/` folder, ready to open in any browser.

---

## Covered Topics

### ⌨ Developer Track
Hands-on tutorials, code examples, and implementation guides.

| Topic | What you will learn |
|---|---|
| **Generative AI Fundamentals** | Core concepts, how LLMs work, deep-dive tutorials |
| **Agentic AI** | How AI agents work, tool use, memory and planning patterns |
| **Agentic Coding** | AI-powered development tools (Claude Code, Cursor, Devin), coding agent workflows |
| **Prompt Engineering** | Structured output, chain-of-thought, few-shot and advanced techniques |
| **AI Orchestration & Frameworks** | LangChain, LangGraph, CrewAI, Anthropic Agent SDK, multi-agent frameworks |

### 🏛 Architect Track
System design patterns, trade-offs, production concerns, and decision frameworks.

| Topic | What you will learn |
|---|---|
| **AI System Design** | Scalable LLM architecture patterns for production |
| **RAG Architecture** | Retrieval-augmented generation, vector databases, design trade-offs |
| **Multi-Agent System Design** | Orchestration patterns, coordination strategies, architecture blueprints |
| **LLMOps & AI in Production** | Deployment, monitoring, observability, and cost optimization |
| **AI Security & Guardrails** | Prompt injection, enterprise trust boundaries, guardrail architectures |

---

## How It Works

The agent runs in two modes — local (your Windows machine) or AWS (fully serverless). Both modes execute the same four-stage pipeline.

```
LOCAL MODE                            AWS MODE
──────────────────────────            ────────────────────────────────────
Windows Task Scheduler                EventBridge cron(0 3 * * ? *)
(daily at 03:00 UTC)                  (daily at 03:00 UTC)
        │                                      │
        ▼                                      ▼
  run_agent.bat                     Lambda: agent.lambda_handler()
  (activates venv)                           │
        │                                    │
        └──────────────┬────────────────────-┘
                       ▼
                   agent.py
        ┌────────────┴────────────────────────────┐
        │  1. Search (Tavily API)                  │
        │     2 queries × 10 topics = 20 searches  │
        │     - web articles & tutorials           │
        │     - YouTube videos (site:youtube.com) │
        │     topic=general, days=7               │
        └────────────┬────────────────────────────┘
                     │ raw results (deduplicated)
                     ▼
        ┌─────────────────────────────────────────┐
        │  2. Curate (Claude Haiku) — 2 calls      │
        │     Call 1: Developer Track (5 topics)   │
        │     Call 2: Architect Track (5 topics)   │
        │     Each call returns:                   │
        │     - 2-4 best resources per topic       │
        │     - type, difficulty, time estimate    │
        │     - "why learn this" per resource      │
        │     - Concept of the Day (call 1 only)   │
        └────────────┬────────────────────────────┘
                     │ structured JSON (merged)
                     ▼
        ┌─────────────────────────────────────────┐
        │  3. Generate HTML report                 │
        │     - Concept of the Day section         │
        │     - Developer Track section + cards    │
        │     - Architect Track section + cards    │
        │     - Article / Video badges             │
        │     - Difficulty & time estimate tags    │
        │     - Dark mode support                  │
        └─────────────────────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────────────────────┐
        │  4. Deliver                              │
        │  LOCAL: Save to reports/ + SMTP email   │
        │  AWS:   Upload to S3 + SES email        │
        └─────────────────────────────────────────┘
```

### Key design decisions

- **Two tracks** — Developer and Architect content is curated separately, each with its own Claude call and audience-specific instructions, so the results are relevant to each role.
- **7-day window** — A great tutorial from 5 days ago is more valuable than a shallow post from this morning.
- **YouTube included** — Each topic runs a second query with `site:youtube.com` so both articles and videos are surfaced.
- **Two Claude Haiku calls** — One per track keeps each prompt within token limits and lets Claude tailor curation to each audience.
- **Deduplication** — URLs are deduplicated across queries per topic before sending to Claude.
- **Skip-if-exists guard** — If today's report already exists the agent exits without any API calls.

---

## Report Layout

```
┌──────────────────────────────────────────────┐
│  AI Learning Digest · 2026-03-09             │
│  20 resources · 12 developer · 8 architect   │
├──────────────────────────────────────────────┤
│  CONCEPT OF THE DAY                          │
│  "Tool Use in AI Agents"                     │
│  Plain-English 3-sentence explanation...     │
├──────────────────────────────────────────────┤
│  ⌨ Developer Track                           │
│  Hands-on tutorials, code examples...        │
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
│  🏛 Architect Track                          │
│  System design patterns, trade-offs...       │
├──────────────────────────────────────────────┤
│  RAG Architecture              2 resources   │
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

### 1. Clone the repository

```bash
git clone https://github.com/marwantareks/ai-news-agent.git
cd ai-news-agent
```

### 2. Create your `.env` file

Create a file named `.env` in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...

# Email delivery (optional — leave blank to disable)
EMAIL_TO=you@example.com
EMAIL_FROM=you@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-16-char-app-password
```

> **Gmail App Password:** Go to myaccount.google.com → Security → 2-Step Verification → App passwords. Generate a password for "Mail" and paste it as `SMTP_PASSWORD`. Never use your main Google account password here.
>
> `SMTP_USER` must always be your **Gmail address** (e.g. `you@gmail.com`), even if `EMAIL_FROM` is a custom domain routed through Gmail.
>
> If any `EMAIL_*` variable is left blank the agent skips email silently and just saves the HTML file as normal.

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
└── YYYY-MM-DD-ai-learning.html
```

Open any `.html` file in your browser. Each report:
- Shows a **Concept of the Day** at the top
- Lists curated resources separated into Developer and Architect tracks
- Includes article/video badges, difficulty level, and estimated time per resource
- Links directly to the source (article or YouTube video)
- Supports light and dark mode automatically
- Is fully self-contained (no external dependencies)

If `EMAIL_*` vars are configured, the same report is also **emailed to you automatically** as a rich HTML email immediately after it is saved.

---

## Project Structure

```
ai-news-agent/
├── agent.py               # Main agent logic (search → curate → HTML → email + Lambda handler)
├── template.yaml          # AWS SAM template (Lambda + EventBridge + S3 + IAM)
├── samconfig.toml         # SAM deploy config (generated; not committed to git)
├── requirements.txt       # Python dependencies
├── setup.bat              # One-time local setup (venv + Windows scheduler)
├── run_agent.bat          # Manual local run shortcut
├── deploy.bat             # SAM build + deploy to AWS (Windows helper)
├── setup_scheduler.ps1    # Registers the Windows Task Scheduler job
├── CLAUDE.md              # Architecture guide for Claude Code
├── .env                   # API keys and email config (not committed to git)
├── agent.log              # Append-only run log — local mode only
├── Documentation/
│   ├── ARCHITECTURE.md    # Full technical architecture, pipeline, schemas, AWS infra
│   └── USER_GUIDE.md      # End-user guide: env vars, AWS Console steps, monitoring
└── reports/
    └── YYYY-MM-DD-ai-learning.html   # Local mode output only
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic` | Claude Haiku API client for curation and summarisation |
| `tavily-python` | Web + YouTube search API client |
| `python-dotenv` | Loads `.env` file into environment variables |
| `boto3` | AWS SDK — used for S3 and SES in cloud deployment mode |

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude Haiku |
| `TAVILY_API_KEY` | Yes | Tavily search API key |
| `EMAIL_TO` | No | Recipient email address |
| `EMAIL_FROM` | No | Sender email address |
| `SMTP_HOST` | No | SMTP server (local mode only, default: smtp.gmail.com) |
| `SMTP_PORT` | No | SMTP port (local mode only, default: 465) |
| `SMTP_USER` | No | Gmail address for SMTP auth (local mode only) |
| `SMTP_PASSWORD` | No | Gmail App Password (local mode only) |
| `S3_BUCKET` | AWS mode | S3 bucket name. When set, enables AWS mode: S3 storage + SES email. Set automatically by `template.yaml`. |
| `SES_REGION` | AWS mode | AWS region for SES client (default: us-east-1). Do NOT use `AWS_REGION` — reserved by Lambda. |

> `S3_BUCKET` and `SES_REGION` are set automatically by `template.yaml` when deployed to Lambda. Do not add them to your local `.env`.

---

## AWS Deployment

The agent can run as an AWS Lambda function triggered daily by EventBridge, storing reports in S3 and delivering email via SES — no server required.

### Prerequisites

| Tool | Install | Verify |
|---|---|---|
| AWS CLI v2 | Download `AWSCLIV2.msi` from AWS | `aws --version` |
| AWS SAM CLI | Download `AWS_SAM_CLI_64_PY3.msi` from GitHub releases | `sam --version` |

### One-time AWS setup

1. **Create IAM user** with `AdministratorAccess` in the AWS Console. Generate an access key, then run `aws configure` (region: `us-east-1`, output: `json`).
2. **Verify sender email** in Amazon SES (us-east-1): Console → SES → Verified identities → Create identity → Email address. Click the link in the verification email AWS sends.
3. **Verify recipient email** the same way (required in SES sandbox mode).

> Do NOT manually create the S3 bucket, Lambda function, or EventBridge rule — SAM creates everything automatically.

### Deploy

**Windows helper (reads API keys from your `.env` automatically):**

```bat
deploy.bat
```

Or run SAM directly — first time (interactive prompts):

```bash
sam build && sam deploy --guided
```

All subsequent updates:

```bash
sam build && sam deploy
```

### How it runs on AWS

```
EventBridge cron(0 3 * * ? *)   →   Lambda (agent.lambda_handler)
                                         │
                              ┌──────────┴──────────────────┐
                              │  1. Tavily search (20 calls) │
                              │  2. Claude Haiku (2 calls)   │
                              │  3. Generate HTML            │
                              │  4. Upload to S3             │
                              │  5. Send via SES             │
                              └─────────────────────────────┘
```

> **Dual-mode design:** `S3_BUCKET` env var gates AWS mode — set automatically by `template.yaml` in Lambda, absent in local mode. The local workflow (`run_agent.bat`, Task Scheduler) is completely unchanged.

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
| `Failed to send email` in log | Check `SMTP_USER` is your Gmail address (not custom domain); verify App Password is correct |
| SES email not delivered | `EMAIL_FROM` must NOT be a `@gmail.com` address in AWS/SES mode — use a custom domain address that is SES-verified (e.g. `digest@yourdomain.com`) |
| Email arrives but looks broken | Ensure your email client renders HTML; try a different client |
| Email not arriving at all | Check spam folder; verify `EMAIL_TO` is correct in `.env` |
| `sam build` fails — Python version error | Install Python 3.12 and add to PATH, or use `sam build --use-container` (requires Docker) |
| `sam deploy` fails — `CAPABILITY_NAMED_IAM` | Ensure `capabilities = "CAPABILITY_IAM CAPABILITY_NAMED_IAM"` is in `samconfig.toml` |
| Lambda `PermissionError` on log file | `S3_BUCKET` env var not set in Lambda — FileHandler is trying to write to the read-only package directory |
| SES `MessageRejected` | Recipient not verified in SES sandbox. Verify in Console → SES → Verified identities |
| SES `InvalidClientTokenId` | AWS credentials wrong or expired. Re-run `aws configure` |
| Report not in S3 after Lambda invoke | Check CloudWatch logs `/aws/lambda/ai-news-agent` for API key errors or Tavily failures |
| Lambda timeout | Typical run is 60–90 s. If timing out at 300 s, check for network issues in CloudWatch log |
| `AWS_REGION` conflict in template | Do not set `AWS_REGION` in `template.yaml` — Lambda reserves it. Use `SES_REGION` (already handled in the provided template) |
| EventBridge not triggering | Console → EventBridge → Rules → `ai-news-agent-daily` → confirm Enabled |
