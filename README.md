# AI Learning Digest Agent

A lightweight twice-weekly agent that curates the best articles and YouTube videos published in the last 7 days — organized into a **Developer Track** and an **Architect Track** — and delivered as a clean, self-contained HTML report.

---

## Documentation

| Document | Audience | Description |
|---|---|---|
| [Architecture Guide](Documentation/ARCHITECTURE.md) | Developers & Architects | Full pipeline, tech stack, data schemas, AWS infrastructure, environment variables, cost estimates |
| [User Guide](Documentation/USER_GUIDE.md) | End Users | What env vars do, step-by-step AWS Console instructions, how to test, how to monitor, troubleshooting |

---

## Objective

Keep up with the fast-moving AI landscape without spending hours searching. Every Tuesday and Friday morning the agent:

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
Windows Task Scheduler                EventBridge cron(0 3 ? * TUE,FRI *)
(Tue/Fri at 03:00 UTC)                (Tue/Fri at 03:00 UTC)
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
        │  LOCAL: Save to reports/ + Resend Broadcast │
        │  AWS:   Upload to S3  + Resend Broadcast │
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

## Newsletter Signup & Unsubscribe

A public self-service signup page lets anyone subscribe to the digest without manual audience management.

- **Signup page** — static HTML served over HTTPS via CloudFront: `https://<id>.cloudfront.net` (exact URL printed at the end of `deploy.bat`)
- **API endpoint** — `POST /subscribe` with `{"email": "..."}` sends a confirmation email with a signed link (valid 24 hours). The contact is only added to the Resend Audience after the subscriber clicks **Confirm my subscription** in that email (`GET /confirm`).
- Deployed automatically as part of `deploy.bat` — the live API URL is injected into `signup/subscribe.html` before upload.

Once someone confirms their subscription they receive every future broadcast automatically, since `send_email()` broadcasts to the entire audience.

### Unsubscribe

Every broadcast email includes an **Unsubscribe** link in the footer. Resend expands the `{{{RESEND_UNSUBSCRIBE_URL}}}` template variable into a per-recipient signed URL — clicking it opts the contact out directly in Resend with no code on our side.

A fallback **unsubscribe page** is also served via CloudFront (`/unsubscribe.html`). Users can enter their email manually to opt out — useful when email links are stripped by a client. The page pre-fills the email from a `?email=` query parameter. It calls `POST /unsubscribe` on the same Lambda as the signup function, which flags the contact as `unsubscribed: true` in Resend. Unsubscribed contacts are preserved in the audience but excluded from all future broadcasts.

---

## Analytics

Open rates and click tracking are handled automatically by **Resend's built-in broadcast analytics** — no extra code or infrastructure needed.

| Metric | How it works |
|---|---|
| **Opens** | Resend injects a tracking pixel into each broadcast. |
| **Clicks** | Resend wraps all links with redirect URLs and records each click. |
| **Unsubscribes** | Tracked natively via the signed unsubscribe link in each email footer. |

View stats in the [Resend dashboard](https://resend.com/broadcasts) → select a broadcast → **Analytics** tab.

> For per-link click data (e.g. which article was clicked most), add UTM parameters to outbound URLs in `build_cards()`. Destination sites that use Google Analytics will report on them.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Windows 10/11 | Scheduler setup uses Windows Task Scheduler |
| Python 3.10+ | Must be on your `PATH` |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| Tavily API key | [app.tavily.com](https://app.tavily.com) |
| Resend account | [resend.com](https://resend.com) — required for email delivery. Create an API key, verify your sending domain, and create an Audience. |

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

# Email delivery via Resend Broadcasts (optional — leave blank to disable)
RESEND_API_KEY=re_...
RESEND_AUDIENCE_ID=aud_...
EMAIL_FROM=digest@your-verified-domain.com
```

> **Resend setup:** Sign up at [resend.com](https://resend.com), create an API key, verify your sending domain, and create an Audience. `EMAIL_FROM` must be on a domain verified in your Resend account. `RESEND_AUDIENCE_ID` is the ID of the Audience whose contacts will receive each broadcast (format: `aud_xxxxxxxx`, found in Resend → Audiences).
>
> If any of `RESEND_AUDIENCE_ID`, `EMAIL_FROM`, or `RESEND_API_KEY` is blank the agent skips email silently and just saves the HTML file as normal.

### 3. Run the one-time setup

Double-click **`setup.bat`** or run from a terminal:

```bat
setup.bat
```

This will:
- Create a Python virtual environment (`venv/`)
- Install all dependencies from `requirements.txt`
- Register a **Windows Task Scheduler** job (`AI-News-Agent-Weekly`) that runs every Tuesday and Friday at **03:00 UTC**
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
├── template.yaml          # AWS SAM template (Lambda + EventBridge + S3 + IAM + signup infra)
├── samconfig.toml         # SAM deploy config (generated; not committed to git)
├── requirements.txt       # Python dependencies
├── setup.bat              # One-time local setup (venv + Windows scheduler)
├── run_agent.bat          # Manual local run shortcut
├── deploy.bat             # SAM build + deploy to AWS, then uploads signup page to S3
├── setup_scheduler.ps1    # Registers the Windows Task Scheduler job
├── CLAUDE.md              # Architecture guide for Claude Code
├── .env                   # API keys and email config (not committed to git)
├── agent.log              # Rotating run log — local mode only (5 MB × 3 files)
├── signup/
│   ├── handler.py         # Lambda handler for POST /subscribe and POST /unsubscribe (stdlib only, no pip deps)
│   ├── subscribe.html     # Static signup page (SIGNUP_API_URL placeholder replaced at deploy)
│   └── unsubscribe.html   # Static unsubscribe page (UNSUBSCRIBE_API_URL placeholder replaced at deploy)
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
| `boto3` | AWS SDK — used for S3 in cloud deployment mode |
| `resend` | Resend SDK — creates and sends Broadcasts to all audience contacts (local and AWS modes) |

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude Haiku |
| `TAVILY_API_KEY` | Yes | Tavily search API key |
| `RESEND_API_KEY` | No | Resend API key — required for email delivery |
| `RESEND_AUDIENCE_ID` | No | Resend Audience ID (e.g. `aud_xxxxxxxx`) — all contacts in the audience receive each broadcast |
| `EMAIL_FROM` | No | Sender address — must be on a Resend-verified domain |
| `S3_BUCKET` | AWS mode | S3 bucket name. When set, enables AWS mode: S3 storage. Set automatically by `template.yaml`. |

> `S3_BUCKET` is set automatically by `template.yaml` when deployed to Lambda. Do not add it to your local `.env`.

---

## AWS Deployment

The agent can run as an AWS Lambda function triggered by EventBridge, storing reports in S3 and delivering email via the Resend Broadcasts API — no server required.

### Prerequisites

| Tool | Install | Verify |
|---|---|---|
| AWS CLI v2 | Download `AWSCLIV2.msi` from AWS | `aws --version` |
| AWS SAM CLI | Download `AWS_SAM_CLI_64_PY3.msi` from GitHub releases | `sam --version` |

### One-time AWS setup

**1. Configure AWS credentials**

Create an IAM user with `AdministratorAccess` in the AWS Console. Generate an access key (Access Key ID + Secret Access Key), then run:

```bash
aws configure
```

Enter your Access Key ID, Secret Access Key, default region (`us-east-1`), and output format (`json`). This stores credentials in `~/.aws/credentials` and is used by both the AWS CLI and SAM during deployment.

**2. Set up Resend**

1. Sign up at [resend.com](https://resend.com) and create an **API key**. Add it to `.env` as `RESEND_API_KEY=re_...`.
2. Go to **Domains** → **Add Domain** and verify your sending domain. Set `EMAIL_FROM` in `.env` to an address on that domain (e.g. `digest@yourdomain.com`).
3. Go to **Audiences** → **Create Audience**. Copy the Audience ID (format: `aud_xxxxxxxx`) and add it to `.env` as `RESEND_AUDIENCE_ID=aud_...`.
4. Add yourself as a contact: Audiences → your audience → **Add Contact** — otherwise you won't receive the first broadcast.

> Do NOT manually create the S3 bucket, Lambda function, or EventBridge rule — SAM creates everything automatically.

### Deploy

**Windows helper — run from an existing cmd window (not by double-clicking):**

```bat
cd C:\MyProjects\ai-news-agent
deploy.bat
```

`deploy.bat` performs four steps automatically:
1. **`sam build`** — packages `agent.py` and dependencies into a Lambda deployment ZIP
2. **`sam deploy`** — creates/updates all AWS resources and injects your `.env` values as Lambda env vars
3. **Signup page upload** — retrieves `SignupApiUrl` from CloudFormation outputs, injects it into `signup/subscribe.html`, and uploads to `SignupBucket`
4. **Unsubscribe page upload** — retrieves `UnsubscribeApiUrl`, injects it into `signup/unsubscribe.html`, and uploads to `SignupBucket`

After deploy, URLs are printed in the summary:
- **Signup page** — the HTTPS CloudFront URL for the newsletter signup page (`SignupPageCloudFrontUrl` output)
- **Signup API** — the subscribe API endpoint (for reference)
- **Unsubscribe API** — the unsubscribe API endpoint (for reference)

> CloudFront propagation takes ~5–15 minutes after the first deploy.

Or run SAM directly — first time (interactive prompts):

```bash
sam build && sam deploy --guided
```

All subsequent updates:

```bash
sam build && sam deploy
```

> **Note:** Running SAM directly skips the signup page upload. Use `deploy.bat` to keep the signup page in sync.

### How it runs on AWS

```
EventBridge cron(0 3 ? * TUE,FRI *)   →   Lambda (agent.lambda_handler)
                                         │
                              ┌──────────┴──────────────────┐
                              │  1. Tavily search (20 calls) │
                              │  2. Claude Haiku (2 calls)   │
                              │  3. Generate HTML            │
                              │  4. Upload to S3             │
                              │  5. Send via Resend API      │
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
| Scheduled task not running | Open Task Scheduler, find `AI-News-Agent-Weekly`, run it manually to test |
| UAC / permission error during setup | Right-click `setup.bat` → **Run as administrator** |
| No YouTube results | Tavily indexes YouTube — results depend on availability for that query and week |
| `Resend broadcast failed` in log | Check `RESEND_API_KEY` is valid, `RESEND_AUDIENCE_ID` is correct, and `EMAIL_FROM` is on a Resend-verified domain. Check Resend dashboard → Broadcasts for delivery details. |
| Email not delivered | Check spam folder. Confirm you are a contact in the Resend Audience. Verify `RESEND_API_KEY` and `RESEND_AUDIENCE_ID` are set in Lambda env vars. |
| Email arrives but looks broken | Ensure your email client renders HTML; try a different client |
| `sam build` fails — Python version error | Install Python 3.12 and add to PATH, or use `sam build --use-container` (requires Docker) |
| `sam deploy` fails — `CAPABILITY_NAMED_IAM` | Ensure `capabilities = "CAPABILITY_IAM CAPABILITY_NAMED_IAM"` is in `samconfig.toml` |
| `deploy.bat` stops after build with no error | Run from an existing cmd window (`cd C:\MyProjects\ai-news-agent && deploy.bat`), not by double-clicking |
| Lambda `PermissionError` on log file | `S3_BUCKET` env var not set in Lambda — FileHandler is trying to write to the read-only package directory |
| AWS credentials expired | Re-run `aws configure` with fresh Access Key ID and Secret Access Key from the IAM Console |
| Report not in S3 after Lambda invoke | Check CloudWatch logs `/aws/lambda/ai-news-agent` for API key errors or Tavily failures |
| Lambda timeout | Typical run is 60–90 s. If timing out at 300 s, check for network issues in CloudWatch log |
| EventBridge not triggering | Console → EventBridge → Rules → `ai-news-agent-weekly` → confirm Enabled |
