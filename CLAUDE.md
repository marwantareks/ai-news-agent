# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

The agent skips generation and exits 0 if today's report already exists in `reports/`.

## Architecture

Everything lives in a single file: **`agent.py`**. The pipeline has four sequential stages:

1. **Search** (`search_topic`) — For each of 10 topics, runs 2 Tavily queries (one general web, one `site:youtube.com`). Results are capped at 5 per topic and deduplicated by URL. Total: 20 API calls.

2. **Curate** (`summarize_section`) — Two separate Claude Haiku calls, one per section (developer / architect). Each call receives the raw search results for its 5 topics and returns structured JSON with ranked resources + metadata. The developer call also produces the `concept_of_the_day`; the architect call sets it to empty.

3. **Generate** (`generate_html`) — Merges the two JSON summaries and renders a fully self-contained HTML file (inline CSS + no external dependencies) into `reports/YYYY-MM-DD-ai-learning.html`.

4. **Email** (`send_email`) — Sends the HTML file as the email body via `smtplib.SMTP_SSL`. Skipped silently if any `EMAIL_*` env var is missing.

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

Optional (email delivery):
- `EMAIL_TO`, `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT` (default 465), `SMTP_USER`, `SMTP_PASSWORD`
- `SMTP_USER` must be the Gmail address, even when `EMAIL_FROM` is a custom domain.

## Model

The curate stage uses **`claude-haiku-4-5-20251001`** (hardcoded in `summarize_section`). Update that string to switch models.

## Logging

Logs go to both stdout and `agent.log` (appended, UTF-8). Check `agent.log` after a run to verify email delivery or diagnose search/Claude errors.

## Scheduler

`setup.bat` registers a Windows Task Scheduler job (`AI-News-Agent-Daily`) via `setup_scheduler.ps1` that runs `run_agent.bat` daily at 03:00 UTC. The task is configured to run on next startup if the machine was off at trigger time.

## Security

### XSS prevention (`agent.py`)
All external-sourced values (from Claude JSON and Tavily) are escaped before HTML insertion:
- `html.escape()` applied to `text`, `time_estimate`, `why_learn_this`, `name`, `cotd_title`, `cotd_explanation`
- `_safe_url()` validates URL scheme — only `http`/`https` pass through; others become `#`
- `rtype` and `difficulty` are allowlisted to known values before use as CSS class names

### SES IAM scope (`template.yaml`)
`ses:SendRawEmail` is granted on both `arn:aws:ses:us-east-1:${AWS::AccountId}:identity/${EmailFrom}` and `arn:aws:ses:us-east-1:${AWS::AccountId}:identity/${EmailTo}`. SES checks IAM authorization against both when the recipient is a verified identity in the same account.

**If you change `EMAIL_FROM` or `EMAIL_TO`:** update `.env` and run `deploy.bat` (or `sam build && sam deploy`). Updating only the Lambda env vars is not enough — the IAM policy ARNs must also be updated via a redeploy.
