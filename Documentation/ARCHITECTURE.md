# Technical Architecture: AI Learning Digest Agent

## 1. Overview

The AI Learning Digest Agent is a Python application that runs daily to produce a curated HTML report of the best AI learning resources published in the last 7 days. It operates in two modes: **local mode** (runs on Windows via Task Scheduler, saves HTML to disk, sends email via SMTP) and **AWS mode** (runs as an AWS Lambda function triggered by EventBridge, stores the report in S3, and sends email via SES). The entire application lives in a single file, `agent.py`, and follows a four-stage sequential pipeline: Search → Curate → Generate → Email.

---

## 2. Tech Stack

| Component | Technology | Version / Notes |
|---|---|---|
| Runtime | Python | 3.12 (Lambda runtime: `python3.12`) |
| AI Curation | Claude Haiku | `claude-haiku-4-5-20251001` via Anthropic SDK |
| Web Search | Tavily API | `tavily-python` client |
| AWS Functions | boto3 | S3 storage, SES email |
| Infrastructure as Code | AWS SAM | `template.yaml` |
| Scheduler (local) | Windows Task Scheduler | Tuesdays and Fridays at 03:00 UTC via `setup_scheduler.ps1` |
| Scheduler (AWS) | Amazon EventBridge | `cron(0 3 ? * TUE,FRI *)` |
| Report Storage (local) | Local filesystem | `reports/YYYY-MM-DD-ai-learning.html` |
| Report Storage (AWS) | Amazon S3 | Bucket: `ai-news-agent-reports-<AccountId>` |
| Email (local) | `smtplib.SMTP_SSL` | Port 465, Gmail App Password |
| Email (AWS) | Amazon SES | `ses.send_raw_email()` |
| Logging (local) | Python `logging` | stdout + `agent.log` |
| Logging (AWS) | Amazon CloudWatch Logs | `/aws/lambda/ai-news-agent` (stdout capture) |
| Config | `python-dotenv` | `.env` file in project root |

---

## 3. Repository Structure

```
ai-news-agent/
├── agent.py               # Entire application: search → curate → HTML → email + Lambda handler
├── template.yaml          # AWS SAM template (Lambda + EventBridge + S3 + IAM role)
├── samconfig.toml         # SAM deploy config (auto-generated; not committed to git)
├── requirements.txt       # Python deps: anthropic, tavily-python, python-dotenv, boto3
├── setup.bat              # One-time local setup: creates venv + registers Windows scheduler
├── run_agent.bat          # Local run shortcut: activates venv, calls agent.py
├── deploy.bat             # Windows helper: loads .env vars, runs sam build && sam deploy
├── setup_scheduler.ps1    # PowerShell script called by setup.bat to register the scheduled task
├── CLAUDE.md              # Architecture notes for Claude Code AI assistant
├── .env                   # API keys and email config (never committed to git)
├── agent.log              # Append-only run log (local mode only)
├── Documentation/
│   ├── ARCHITECTURE.md    # This file
│   └── USER_GUIDE.md      # End-user guide: env vars, AWS Console steps, testing
└── reports/
    └── YYYY-MM-DD-ai-learning.html   # Daily output (local mode only)
```

---

## 4. Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         TRIGGER                                 │
│  Local: Windows Task Scheduler (Tue/Fri 03:00 UTC, run_agent.bat) │
│  AWS:   EventBridge cron(0 3 ? * TUE,FRI *) → lambda_handler()   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1 — SEARCH  [search_topic()]                             │
│                                                                 │
│  For each of 10 topics:                                         │
│    Query 1: general web search (recent articles & tutorials)    │
│    Query 2: site:youtube.com (recent video content)             │
│  Parameters: topic=general, days=7, search_depth=basic,         │
│              max_results=5                                       │
│  Deduplication: by URL within each topic                        │
│  Cap: 5 results per topic after dedup                           │
│  Total: 20 Tavily API calls                                     │
└─────────────────────────────┬───────────────────────────────────┘
                              │  dict[topic_name → list[result]]
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2 — CURATE  [summarize_section()]                        │
│                                                                 │
│  Call 1 — Developer Track (5 topics):                           │
│    audience: "software developers who want hands-on tutorials"  │
│    include_cotd: True  →  produces concept_of_the_day           │
│                                                                 │
│  Call 2 — Architect Track (5 topics):                           │
│    audience: "solution architects, system design patterns"      │
│    include_cotd: False →  concept_of_the_day set to empty       │
│                                                                 │
│  Each call: selects 2-4 best resources per topic, assigns       │
│  type/difficulty/time_estimate/why_learn_this, returns JSON.    │
│  Model: claude-haiku-4-5-20251001, max_tokens: 4000             │
└─────────────────────────────┬───────────────────────────────────┘
                              │  merged summary dict (JSON)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3 — GENERATE HTML  [generate_html()]                     │
│                                                                 │
│  Merges developer + architect JSON into one summary structure.  │
│  Renders self-contained HTML:                                   │
│    - Inline CSS (no external dependencies)                      │
│    - Dark mode via @media (prefers-color-scheme: dark)          │
│    - Concept of the Day section                                 │
│    - Developer Track: 5 topic cards with resource items         │
│    - Architect Track: 5 topic cards with resource items         │
│    - Badges: type (video/article), difficulty, time estimate    │
└─────────────────────────────┬───────────────────────────────────┘
                              │  HTML string
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 4 — DELIVER                                              │
│                                                                 │
│  Local mode:                                                    │
│    - Write to reports/YYYY-MM-DD-ai-learning.html               │
│    - Send via smtplib.SMTP_SSL (port 465) if EMAIL_* set        │
│                                                                 │
│  AWS mode:                                                      │
│    - Upload to S3: s3://<bucket>/YYYY-MM-DD-ai-learning.html    │
│    - Send via ses.send_raw_email() if EMAIL_TO + EMAIL_FROM set │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Dual-Mode Architecture

| Axis | Local Mode | AWS Mode |
|---|---|---|
| **Gate** | `S3_BUCKET` env var absent | `S3_BUCKET` env var set (by SAM template) |
| **Trigger** | Windows Task Scheduler → `run_agent.bat` | EventBridge `cron(0 3 * * ? *)` → `lambda_handler()` |
| **Entry point** | `if __name__ == "__main__": main()` | `lambda_handler(event, context)` calls `main()` |
| **Idempotency check** | `Path.exists()` on local report file | `s3.head_object()` — 404 = not yet run, anything else = skip |
| **Report storage** | `reports/YYYY-MM-DD-ai-learning.html` | `s3://<bucket>/YYYY-MM-DD-ai-learning.html` |
| **Email function** | `send_email()` via `smtplib.SMTP_SSL` | `aws_send_email()` via `boto3` SES |
| **Email auth** | `SMTP_USER` + `SMTP_PASSWORD` (Gmail App Password) | IAM role permission: `ses:SendRawEmail` |
| **Logging** | stdout + `agent.log` (FileHandler appended) | stdout only (CloudWatch captures automatically) |
| **FileHandler** | Added when `S3_BUCKET` is empty | Skipped (Lambda's read-only FS — FileHandler would fail) |
| **Dependencies** | All in local `venv/` | Packaged by `sam build` into Lambda deployment ZIP |
| **Infrastructure** | Developer's Windows machine | Lambda 256 MB, 300s timeout, Python 3.12 |

---

## 6. AWS Infrastructure

All resources are defined in `template.yaml` and deployed via SAM.

| Resource | Type | Details |
|---|---|---|
| `AgentFunction` | `AWS::Serverless::Function` | Name: `ai-news-agent`, handler: `agent.lambda_handler`, runtime: `python3.12`, memory: 256 MB, timeout: 300s |
| `WeeklySchedule` | EventBridge Schedule (SAM `Events`) | `cron(0 3 ? * TUE,FRI *)` — fires Tuesdays and Fridays at 03:00 UTC |
| `ReportsBucket` | `AWS::S3::Bucket` | Name: `ai-news-agent-reports-<AccountId>`, lifecycle: delete objects after 90 days |
| `AgentExecutionRole` | `AWS::IAM::Role` | Name: `ai-news-agent-lambda-role` |

### IAM Permissions

| Permission | Resource | Why |
|---|---|---|
| `AWSLambdaBasicExecutionRole` (managed) | CloudWatch Logs | Write function logs to CloudWatch |
| `s3:PutObject`, `s3:GetObject` | `arn:aws:s3:::ai-news-agent-reports-<AccountId>/*` | Upload HTML report, read existing reports |
| `s3:ListBucket` | `arn:aws:s3:::ai-news-agent-reports-<AccountId>` | Required for `head_object` to return 404 (not 403) on missing keys — enables idempotency check |
| `ses:SendRawEmail` | `arn:aws:ses:us-east-1:<AccountId>:identity/<EmailFrom>` and `arn:aws:ses:us-east-1:<AccountId>:identity/<EmailTo>` | Send the HTML digest via SES — scoped to both the sender and recipient identities. SES checks IAM authorization against both when the recipient is a verified identity in the same account. |

> **Note:** `s3:ListBucket` must be on the bucket ARN (not `/*`) to allow `head_object` to distinguish "file not found" (404) from "access denied" (403). Without it, the idempotency check would raise an exception on the first run of each day.

> **SES IAM scope:** The `ses:SendRawEmail` permission is scoped to both the `EmailFrom` and `EmailTo` identities configured at deploy time. SES checks IAM authorization against both sender and recipient when the recipient address is a verified identity in the same AWS account. If you change either `EMAIL_FROM` or `EMAIL_TO`, you **must** redeploy (`deploy.bat` or `sam build && sam deploy`) so the IAM policy ARNs are updated. Updating only the Lambda environment variables without redeploying will cause SES to reject the send with an `AccessDenied` error.

---

## 7. Topics & Sections

| Topic | Section | Accent Color | Web Query | YouTube Query |
|---|---|---|---|---|
| Generative AI Fundamentals | developer | `#c85c38` | `generative AI LLM how it works deep dive tutorial 2025` | `site:youtube.com generative AI LLM explained how it works tutorial` |
| Agentic AI | developer | `#10a37f` | `AI agents ReAct tool use memory planning tutorial explained 2025` | `site:youtube.com AI agents how they work tool use memory tutorial` |
| Agentic Coding | developer | `#4285f4` | `agentic coding Claude Code Cursor Devin AI developer tools tutorial 2025` | `site:youtube.com agentic coding AI software development agents tutorial` |
| Prompt Engineering | developer | `#7c3aed` | `prompt engineering structured output chain-of-thought few-shot tutorial 2025` | `site:youtube.com prompt engineering intermediate advanced techniques tutorial` |
| AI Orchestration & Frameworks | developer | `#0866ff` | `LangChain LangGraph CrewAI Anthropic agent SDK tutorial how it works 2025` | `site:youtube.com LangGraph CrewAI AI orchestration multi-agent framework tutorial` |
| AI System Design | architect | `#d97706` | `AI system design scalable LLM architecture patterns tutorial 2025` | `site:youtube.com AI system design architecture LLM production scalable` |
| RAG Architecture | architect | `#059669` | `RAG retrieval augmented generation architecture vector database design 2025` | `site:youtube.com RAG architecture retrieval augmented generation tutorial deep dive` |
| Multi-Agent System Design | architect | `#0891b2` | `multi-agent system design patterns orchestration architecture 2025` | `site:youtube.com multi-agent architecture design patterns AI systems tutorial` |
| LLMOps & AI in Production | architect | `#dc2626` | `LLMOps AI production deployment monitoring observability cost optimization 2025` | `site:youtube.com LLMOps AI production MLOps best practices tutorial` |
| AI Security & Guardrails | architect | `#7c3aed` | `AI security prompt injection guardrails enterprise trust boundaries architecture 2025` | `site:youtube.com AI security LLM guardrails prompt injection enterprise tutorial` |

Derived lookup dicts used in HTML generation:

```python
TOPIC_COLORS   = {t["name"]: t["color"]   for t in TOPICS}
TOPIC_SECTIONS = {t["name"]: t["section"] for t in TOPICS}
```

---

## 8. Data Schemas

### Tavily Result (per item)

```json
{
  "title": "Article or video title",
  "url": "https://...",
  "content": "First ~300 chars of page content (truncated in prompt)"
}
```

Tavily may return additional fields; only `title`, `url`, and `content` are used.

### Claude JSON Output Schema

Both section calls return the same structure. Only the developer call populates `concept_of_the_day`.

```json
{
  "concept_of_the_day": {
    "title": "Concept Name",
    "explanation": "Sentence one. Sentence two. Sentence three."
  },
  "topics": [
    {
      "name": "Topic Name",
      "resources": [
        {
          "text": "One sentence describing what the reader/viewer will learn.",
          "url": "https://exact-url-from-search-results.com",
          "type": "video",
          "difficulty": "intermediate",
          "time_estimate": "14 min",
          "why_learn_this": "One sentence on why this is valuable right now."
        }
      ]
    }
  ]
}
```

Valid values:
- `type`: `"video"` | `"article"`
- `difficulty`: `"beginner"` | `"intermediate"` | `"advanced"`

### HTML Output Characteristics

- Fully self-contained: no external CSS, JS, or font references
- Inline styles only — renders correctly in email clients
- Dark mode via `@media (prefers-color-scheme: dark)` — automatic based on OS preference
- Viewport meta tag for mobile rendering
- All links open in `target="_blank" rel="noopener noreferrer"`
- All external-sourced values (from Claude JSON and Tavily results) are HTML-escaped via `html.escape()` before insertion to prevent XSS
- URLs are validated to `http`/`https` scheme only — `javascript:` and other schemes are replaced with `#`
- `type` and `difficulty` values are allowlisted to known CSS class names before use as badge class names

---

## 9. Environment Variables

| Variable | Default | Required | Mode | Purpose |
|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | — | Yes | Both | Anthropic API key for Claude Haiku |
| `TAVILY_API_KEY` | — | Yes | Both | Tavily search API key |
| `EMAIL_TO` | `""` | No | Both | Recipient email address |
| `EMAIL_FROM` | `""` | No | Both | Sender email address (must be SES-verified in AWS mode) |
| `SMTP_HOST` | `smtp.gmail.com` | No | Local only | SMTP server hostname |
| `SMTP_PORT` | `465` | No | Local only | SMTP port (SSL) |
| `SMTP_USER` | `""` | No | Local only | Gmail address for SMTP auth (must be Gmail even if EMAIL_FROM is a custom domain) |
| `SMTP_PASSWORD` | `""` | No | Local only | Gmail App Password (16-character) |
| `S3_BUCKET` | `""` | AWS mode | AWS only | S3 bucket name — presence of this var gates AWS mode. Set automatically by SAM template. |
| `SES_REGION` | `us-east-1` | No | AWS only | AWS region for SES client. Do NOT use `AWS_REGION` — Lambda reserves that name. |

> `S3_BUCKET` and `SES_REGION` are injected by `template.yaml` into the Lambda environment automatically. Do not add them to your local `.env`.

---

## 10. Hardcoded Constants

| Constant | Value | Location | Notes |
|---|---|---|---|
| AI model | `claude-haiku-4-5-20251001` | `summarize_section()` | Update this string to switch models |
| Lambda timeout | 300 seconds | `template.yaml` Globals | Typical run: 60–90 seconds |
| Lambda memory | 256 MB | `template.yaml` Globals | |
| Tavily `search_depth` | `"basic"` | `search_topic()` | |
| Tavily `days` | `7` | `search_topic()` | Rolling 7-day window |
| Tavily `max_results` | `5` | `search_topic()` | Per query; total cap also 5 after dedup |
| Claude `max_tokens` | `4000` | `summarize_section()` | Per section call |
| S3 key format | `YYYY-MM-DD-ai-learning.html` | `main()` | Matches local filename |
| S3 lifecycle | 90 days | `template.yaml` | Objects auto-deleted after 90 days |
| Log format | `%(asctime)s %(levelname)s %(message)s` | module level | |

---

## 11. Idempotency

The agent checks whether today's report already exists before making any API calls.

**Local mode:**

```python
if report_path.exists():
    log.info("Report for %s already exists. Skipping.", date_str)
    sys.exit(0)
```

**AWS mode:**

```python
try:
    s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
    log.info("Report for %s already exists in S3. Skipping.", date_str)
    return
except ClientError as e:
    if e.response["Error"]["Code"] != "404":
        raise  # Re-raise unexpected errors; 404 means not yet run
```

Both checks happen before any Tavily or Claude API calls — a duplicate trigger (e.g. EventBridge firing twice, or a manual test run after an automatic run) is zero-cost.

To force a re-run: delete today's report from `reports/` (local) or from S3 (AWS).

---

## 12. Error Handling & Logging

### Per-component behavior

| Component | Error behavior |
|---|---|
| Tavily search (per query) | `try/except` — logs warning, continues with remaining queries |
| Claude Haiku call | Propagates exception — fatal; run aborts |
| S3 upload | Propagates exception — fatal; run aborts |
| SES send | Logs error, does not re-raise — report is still stored in S3 |
| Local SMTP send | Logs error, does not re-raise — report is still saved to disk |
| Missing API keys | `sys.exit(1)` with error log |
| Missing dependencies | `sys.exit(1)` with error log |

### Log format

```
2026-03-10 03:01:42,123 INFO  Starting AI learning digest for 2026-03-10
2026-03-10 03:01:45,456 INFO    Generative AI Fundamentals -> 5 results
2026-03-10 03:02:31,789 INFO  Curating Developer Track with Claude Haiku...
2026-03-10 03:02:45,012 INFO  Curating Architect Track with Claude Haiku...
2026-03-10 03:02:58,345 INFO  Report uploaded to s3://ai-news-agent-reports-613261654297/2026-03-10-ai-learning.html
2026-03-10 03:02:59,678 INFO  Report emailed via SES to user@example.com
```

### CloudWatch vs file logging

- **Local mode:** `logging.basicConfig()` adds both a `StreamHandler` (stdout) and a `FileHandler` for `agent.log`.
- **AWS mode:** Only `StreamHandler` is added. Lambda captures stdout to CloudWatch automatically. `force=True` is passed to `basicConfig()` to override the root logger Lambda pre-configures.

---

## 13. Cost Estimate

Costs assume daily operation in AWS mode with default settings.

| Service | Usage per run | Cost per run (approx.) | Cost per month |
|---|---|---|---|
| Tavily API | 20 searches | ~$0.01–0.04 (depends on plan) | ~$0.30–$1.20 |
| Claude Haiku | 2 calls, ~3k tokens input + ~1k output each | ~$0.002 | ~$0.06 |
| Lambda | 1 invocation, ~90s, 256 MB | ~$0.000003 | ~$0.0001 |
| S3 storage | 1 HTML file ~50–100 KB, deleted after 90 days | ~$0.000001 | Negligible |
| SES | 1 email | $0.0001 | ~$0.003 |
| **Total** | | **~$0.01–0.05** | **~$0.36–$1.50** |

> Tavily costs dominate. Check your Tavily plan limits — the free tier includes 1,000 searches/month, which covers ~50 daily runs.

---

## 14. Local Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/marwantareks/ai-news-agent.git
cd ai-news-agent

# 2. Run one-time setup (creates venv, installs deps, registers Task Scheduler)
setup.bat

# 3. Create .env with your API keys
# (see Environment Variables section above)

# 4. Run manually
run_agent.bat
# or with an active venv:
python agent.py
```

Check `agent.log` after a run to verify search results, curation, and email delivery.

To update a scheduled AWS deployment, edit `agent.py` then run `deploy.bat` (Windows) or `sam build && sam deploy`.
