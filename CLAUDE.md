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
- `SIGNUP_PAGE_URL` — CloudFront HTTPS URL of the signup page; embedded in the broadcast footer as an invite link and used as the back-link in confirm error pages. Set automatically by `template.yaml` — do not add to `.env`.

## Model

The curate stage uses **`claude-haiku-4-5-20251001`** (hardcoded in `summarize_section`). Update that string to switch models.

## Logging

In local mode: logs go to both stdout and `agent.log` (rotating: 5 MB per file, 3 backups, ~15 MB total cap). In AWS mode: stdout only — CloudWatch captures it automatically (`force=True` in `logging.basicConfig` overrides Lambda's pre-configured root logger). Check `agent.log` (local) or CloudWatch log group `/aws/lambda/ai-news-agent` (AWS) after a run.

## AWS Deployment

```bat
deploy.bat [stack-name] [region]
```

Defaults to stack `ai-news-agent` in `us-east-1`. Auto-loads `.env` at startup, then runs `sam build && sam deploy --capabilities CAPABILITY_NAMED_IAM --resolve-s3`. Passes `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `EMAIL_FROM`, `RESEND_API_KEY`, and `RESEND_AUDIENCE_ID` as SAM parameter overrides. After deploy, automatically injects `SignupApiUrl` into `signup/subscribe.html` and `UnsubscribeApiUrl` into `signup/unsubscribe.html`, then uploads both to `SignupBucket`. Requires AWS SAM CLI and configured AWS credentials (`aws configure`).

**Important:** Run `deploy.bat` from an existing cmd window (`cd C:\MyProjects\ai-news-agent && deploy.bat`), not by double-clicking. SAM CLI calls `exit` (not `exit /b`) internally — `deploy.bat` wraps both `sam build` and `sam deploy` with `cmd /c` to prevent this from killing the parent shell.

After first deploy, subsequent runs reuse the saved config in `samconfig.toml`.

## Lambda Configuration

Defined in `template.yaml`: 300s timeout, 256MB memory, Python 3.12. S3 reports expire after 90 days (lifecycle rule on `ReportsBucket`). Entry point is `agent.lambda_handler`, which calls `main()`.

A second Lambda (`ai-news-agent-signup`, 10s timeout, 128MB) handles self-service newsletter signups and unsubscribes — see **Newsletter Signup & Unsubscribe** section below.

## Newsletter Signup & Unsubscribe

Self-service subscribe/unsubscribe flow backed by Resend Audiences:

- **`signup/handler.py`** — Lambda handler (stdlib only, no extra deps). Implements a **double opt-in** flow. Dispatches on `event["rawPath"]`:
  - `/confirm` (GET) → `_handle_confirm()`: verifies HMAC token from query params, then calls `_call_resend()` to activate the contact.
  - `/unsubscribe` (POST) → `_handle_unsubscribe()`: marks the contact `unsubscribed=True` via Resend Contacts API.
  - all other paths (POST) → `_handle_subscribe()`: validates email, generates a signed token, sends a confirmation email via Resend, and returns 200 without yet adding the contact.

  Shared helper `_call_resend(email, unsubscribed, headers)` makes the Resend Contacts API call. Returns 200 on success; 400 for invalid input; 502 on upstream errors. CORS origin is restricted to the CloudFront distribution via `SIGNUP_ALLOWED_ORIGIN` env var, which `template.yaml` sets automatically — do not add it to `.env`.

- **`signup/subscribe.html`** — Static HTML signup page (no framework, no CDN). Contains a `SIGNUP_API_URL` placeholder that `deploy.bat` replaces with the live API Gateway URL at deploy time before uploading to S3.

- **`signup/unsubscribe.html`** — Static HTML unsubscribe page. Same style as subscribe page. Pre-fills email from `?email=` query parameter. Contains a `UNSUBSCRIBE_API_URL` placeholder that `deploy.bat` replaces at deploy time.

- **Unsubscribe link in broadcasts** — `generate_html()` embeds `{{{RESEND_UNSUBSCRIBE_URL}}}` in the email footer (stored in `resend_unsub_url` variable to avoid f-string parse errors). Resend expands it to a per-recipient signed URL at send time.

- **SignupApiUrl** — `https://<id>.execute-api.<region>.amazonaws.com/subscribe`
- **UnsubscribeApiUrl** — `https://<id>.execute-api.<region>.amazonaws.com/unsubscribe`
- **SignupPageCloudFrontUrl** — `https://<id>.cloudfront.net` (HTTPS via CloudFront; `SignupBucket` blocks all direct public access)

All three are emitted as CloudFormation Outputs and printed in the deploy summary.

## Analytics

Open rates and click tracking are handled by **Resend's built-in broadcast analytics** — no custom code required.

When a broadcast is sent via the Resend Broadcasts API, Resend automatically:
- Injects a tracking pixel for open tracking
- Wraps all links for click tracking
- Aggregates per-broadcast stats (opens, clicks, unsubscribes)

View stats in the [Resend dashboard](https://resend.com/broadcasts) after each send. No additional instrumentation needed in `agent.py` or `template.yaml`.

## Scheduler

`setup.bat` registers a Windows Task Scheduler job (`AI-News-Agent-Weekly`) by invoking `setup_scheduler.ps1` (PowerShell). The job runs `run_agent.bat` on Tuesdays and Fridays at 03:00 UTC and is configured to run on next startup if the machine was off at trigger time.

## Security

### XSS prevention (`agent.py`)
All external-sourced values (from Claude JSON and Tavily) are escaped before HTML insertion:
- `html.escape()` applied to `text`, `time_estimate`, `why_learn_this`, `name`, `cotd_title`, `cotd_explanation`
- `_safe_url()` validates URLs before use as `href` attributes — returns `#` if: scheme is not `http`/`https`; hostname is empty; hostname is a raw IPv4 or IPv6 address; hostname is a known search engine domain (`google.com`, `bing.com`, `duckduckgo.com`) with a redirector path (`/url`, `/search`, `/redir`, `/redirect`)
- `rtype` and `difficulty` are allowlisted to known values before use as CSS class names
- `_sanitize_external_text()` strips prompt-injection markers (`###`, role prefixes, HTML tags) from Tavily `title` and `content` fields before they are interpolated into the Claude prompt

### Double opt-in tokens (`signup/handler.py`)
Confirmation links are signed with HMAC-SHA256 using `RESEND_API_KEY` as the secret (`_make_token` / `_verify_token`). Tokens expire after 24 hours. Verification uses `hmac.compare_digest` to prevent timing attacks. The token is `ts` (Unix timestamp) + `sig` (hex digest of `email:ts`), passed as query parameters on the `/confirm` URL.

### Resend API key (`template.yaml`)
`RESEND_API_KEY` is passed as a Lambda env var via the `ResendApiKey` SAM parameter (marked `NoEcho`). Email uses the Resend HTTP API in both local and AWS modes — no SES IAM permissions required.
