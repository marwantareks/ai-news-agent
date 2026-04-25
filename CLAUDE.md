# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup (first time)

```bat
setup.bat
```

This creates the venv, installs `requirements.txt`, and registers the Windows Task Scheduler job. To do it manually:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` (if present) or create `.env` with at minimum `ANTHROPIC_API_KEY` and `TAVILY_API_KEY`.

## Running the Agent

```bash
# Activate the venv first (Windows)
venv\Scripts\activate

# Run the agent
python agent.py
```

Or use the wrapper script (activates venv automatically):
```bat
run_agent.bat
```

The agent skips generation and exits 0 if today's report already exists in `reports/` (local) or S3 (AWS mode). To force a re-run, delete `reports/YYYY-MM-DD-ai-learning.html` locally or the corresponding S3 key.

There are no automated tests or linting configuration in this project.

## Architecture

Everything lives in a single file: **`agent.py`**. The pipeline has four sequential stages:

1. **Search** (`search_topic`) — For each of 10 topics, runs 2 Tavily queries (one general web, one `site:youtube.com`). Results are capped at 5 per topic and deduplicated by URL. Total: 20 API calls.

2. **Curate** (`summarize_section`) — Two separate Claude Haiku calls, one per section (developer / architect). Each call receives the raw search results for its 5 topics and returns structured JSON with ranked resources + metadata. The developer call also produces the `concept_of_the_day`; the architect call sets it to empty.

3. **Generate** (`generate_html`) — Merges the two JSON summaries and renders a fully self-contained HTML file (inline CSS + no external dependencies) into `reports/YYYY-MM-DD-ai-learning.html`.

4. **Email** — `send_email()` uses the Resend Broadcasts API to send to all contacts in the Resend Audience in one call. Skipped silently if `RESEND_AUDIENCE_ID`, `EMAIL_FROM`, or `RESEND_API_KEY` are not set. The mode is determined by whether `S3_BUCKET` is set (controls S3 upload vs. local file write).

## Topics / Sections

Topics are defined in the `TOPICS` list at the top of `agent.py`. Each entry has:
- `name` — display name and key used throughout the pipeline
- `section` — `"developer"` or `"architect"` (controls which Haiku call handles it)
- `color` — hex accent colour for the HTML card
- `queries` — list of Tavily search strings (always 2: general + YouTube)

`TOPIC_COLORS` and `TOPIC_SECTIONS` are derived dicts used in `build_cards` and `generate_html`.

## Environment Variables

Required:
- `ANTHROPIC_API_KEY`
- `TAVILY_API_KEY`

Optional (email delivery — local and AWS):
- `RESEND_AUDIENCE_ID` — Resend Audience ID (e.g. `aud_xxxxxxxx`). All contacts in the audience receive each broadcast. Passed as `ResendAudienceId` SAM parameter.
- `EMAIL_FROM` — must be an address on a domain verified in your Resend account
- `RESEND_API_KEY` — API key from resend.com. **Must have Full Access** (not "Send emails only") — the signup Lambda uses it to write contacts via the Resend Contacts API. Passed to Lambda as the `ResendApiKey` SAM parameter via `deploy.bat`.

Optional (AWS mode):
- `S3_BUCKET` — when set, switches to AWS mode: reports go to S3, no local file log. Set automatically by `template.yaml` in Lambda — do not add to `.env`.

## Model

The curate stage uses **`claude-haiku-4-5-20251001`** (hardcoded in `summarize_section`). Update that string to switch models.

## Logging

In local mode: logs go to both stdout and `agent.log` (appended, UTF-8). In AWS mode: stdout only — CloudWatch captures it automatically (`force=True` in `logging.basicConfig` overrides Lambda's pre-configured root logger). Check `agent.log` (local) or CloudWatch log group `/aws/lambda/ai-news-agent` (AWS) after a run.

## AWS Deployment

```bat
deploy.bat [stack-name] [region]
```

Defaults to stack `ai-news-agent` in `us-east-1`. Auto-loads `.env` at startup, then runs `sam build && sam deploy --capabilities CAPABILITY_NAMED_IAM --resolve-s3`. Passes `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `EMAIL_FROM`, `RESEND_API_KEY`, and `RESEND_AUDIENCE_ID` as SAM parameter overrides. After deploy, automatically injects the `SignupApiUrl` into `signup/subscribe.html` and uploads it to the `SignupBucket` S3 website. Requires AWS SAM CLI and configured AWS credentials (`aws configure`).

**Important:** Run `deploy.bat` from an existing cmd window (`cd C:\MyProjects\ai-news-agent && deploy.bat`), not by double-clicking. SAM CLI calls `exit` (not `exit /b`) internally — `deploy.bat` wraps both `sam build` and `sam deploy` with `cmd /c` to prevent this from killing the parent shell.

After first deploy, subsequent runs reuse the saved config in `samconfig.toml`.

## Lambda Configuration

Defined in `template.yaml`: 300s timeout, 256MB memory, Python 3.12. S3 reports expire after 90 days (lifecycle rule on `ReportsBucket`). Entry point is `agent.lambda_handler`, which calls `main()`.

A second Lambda (`ai-news-agent-signup`, 10s timeout, 128MB) handles self-service newsletter signups — see **Newsletter Signup** section below.

## Newsletter Signup

Self-service signup flow backed by Resend Audiences:

- **`signup/handler.py`** — Lambda handler (stdlib only, no extra deps). Accepts `POST /subscribe` with `{"email": "..."}`, writes the contact to the Resend Audience via the Resend REST API. Returns 200 for new subscribers and already-subscribed contacts alike; 400 for invalid input; 502 on upstream errors. CORS origin is restricted to the S3 website via the `SIGNUP_ALLOWED_ORIGIN` env var, which `template.yaml` sets automatically — do not add it to `.env`.

- **`signup/subscribe.html`** — Static HTML signup page (no framework, no CDN). Contains a `SIGNUP_API_URL` placeholder string that `deploy.bat` replaces with the live API Gateway URL at deploy time before uploading to S3.

- **SignupApiUrl** — HTTPS endpoint (API Gateway HTTP API, auto-created by SAM): `https://<id>.execute-api.<region>.amazonaws.com/subscribe`

- **SignupPageUrl** — Public S3 static website: `http://ai-news-agent-signup-<AccountId>.s3-website-<region>.amazonaws.com`

Both URLs are emitted as CloudFormation Outputs after `deploy.bat` runs and are printed in the deploy summary.

## Scheduler

`setup.bat` registers a Windows Task Scheduler job (`AI-News-Agent-Weekly`) by invoking `setup_scheduler.ps1` (PowerShell). The job runs `run_agent.bat` on Tuesdays and Fridays at 03:00 UTC and is configured to run on next startup if the machine was off at trigger time.

## Security

### XSS prevention (`agent.py`)
All external-sourced values (from Claude JSON and Tavily) are escaped before HTML insertion:
- `html.escape()` applied to `text`, `time_estimate`, `why_learn_this`, `name`, `cotd_title`, `cotd_explanation`
- `_safe_url()` validates URL scheme — only `http`/`https` pass through; others become `#`
- `rtype` and `difficulty` are allowlisted to known values before use as CSS class names

### Resend API key (`template.yaml`)
`RESEND_API_KEY` is passed as a Lambda env var via the `ResendApiKey` SAM parameter (marked `NoEcho`). Email uses the Resend HTTP API in both local and AWS modes — no SES IAM permissions required.
