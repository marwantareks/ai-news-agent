# Plan: Migrate Email Delivery from SES/SMTP to Resend

## Context
The project currently has two separate email code paths: `send_email()` (local, uses `smtplib.SMTP_SSL`) and `aws_send_email()` (Lambda, uses `boto3` SES). SES requires both sender and recipient to be verified in sandbox mode, and any change to `EMAIL_FROM`/`EMAIL_TO` requires a CloudFormation redeploy to update IAM policy ARNs. Migrating to Resend eliminates both friction points, collapses two code paths into one, and removes the SES IAM policy entirely from `template.yaml`.

Migration is done in two phases: local first (verify it works), then AWS.

---

## Files to Modify

- `agent.py`
- `requirements.txt`
- `template.yaml` (Phase 2 only)
- `CLAUDE.md` (Phase 2 only)

---

## Phase 1: Migrate Local Email Path ✅ COMPLETE

### 1a. `requirements.txt`

Add:
```
resend>=2.0.0
```

### 1b. `agent.py` — env var block (lines 18–27)

Add `RESEND_API_KEY` alongside existing vars (keep SMTP and SES vars in place for now):
```python
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
```

### 1c. `agent.py` — replace `send_email()` only (lines 540–564)

The local `send_email(report_path, date_str)` currently reads HTML from disk and sends via SMTP.
Replace it with a Resend-based version that takes `html_content` directly (HTML is already in memory at call site):

```python
def send_email(html_content: str, date_str: str) -> None:
    """Send the HTML report via Resend. Skipped if config is missing."""
    import resend

    if not all([EMAIL_TO, EMAIL_FROM, RESEND_API_KEY]):
        log.warning("Email config incomplete — skipping email. Set EMAIL_TO, EMAIL_FROM, RESEND_API_KEY in .env to enable.")
        return

    resend.api_key = RESEND_API_KEY
    try:
        resend.Emails.send({
            "from": EMAIL_FROM,
            "to": [EMAIL_TO],
            "subject": f"AI Learning Digest · {date_str}",
            "html": html_content,
        })
        log.info("Report emailed via Resend to %s", EMAIL_TO)
    except Exception as e:
        log.error("Resend send failed: %s", e)
```

Keep `aws_send_email()` unchanged for now.

### 1d. `agent.py` — update local call site in `main()` (line 679)

The local branch currently passes `report_path` (a Path object). Update to pass `html` (the string already in memory):

```python
# Before
send_email(report_path, date_str)
# After
send_email(html, date_str)
```

The AWS branch (`aws_send_email(html, date_str)` on line 674) is untouched in this phase.

### Phase 1 Verification

1. Add `RESEND_API_KEY` to `.env`
2. Run `python agent.py` locally (delete today's report first to force a run)
3. Confirm log shows: `Report emailed via Resend to ...`
4. Confirm email arrives in inbox
5. Test graceful skip: temporarily remove `RESEND_API_KEY` from `.env`, re-run — confirm warning logged, no crash

---

## Phase 2: Migrate AWS Email Path (after Phase 1 confirmed working)

### 2a. `agent.py` — remove `aws_send_email()` (lines 567–593)

Delete the function entirely.

### 2b. `agent.py` — update AWS call site in `main()` (line 674)

```python
# Before
aws_send_email(html, date_str)
# After
send_email(html, date_str)
```

### 2c. `agent.py` — remove now-unused env vars (lines 20–23, 27)

Remove:
```python
SMTP_HOST      = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT      = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER      = os.getenv("SMTP_USER", "")
SMTP_PASSWORD  = os.getenv("SMTP_PASSWORD", "")
SES_REGION     = os.getenv("SES_REGION", "us-east-1")
```

### 2d. `template.yaml` — parameters

- Update `EmailTo` description: remove "must be SES-verified in sandbox mode"
- Update `EmailFrom` description: remove "must be SES-verified identity"
- Add new parameter:
```yaml
  ResendApiKey:
    Type: String
    NoEcho: true
    Description: Resend API key for email delivery
```

### 2e. `template.yaml` — Globals env vars (line 38)

Remove:
```yaml
        SES_REGION: us-east-1
```

Add:
```yaml
        RESEND_API_KEY: !Ref ResendApiKey
```

### 2f. `template.yaml` — IAM policy (lines 68–86)

- Rename policy: `AgentS3SesAccess` → `AgentS3Access`
- Remove the `ses:SendRawEmail` statement block entirely (lines 81–86)

### 2g. `deploy.bat`

Add `ResendApiKey` to the SAM parameter overrides (inspect `deploy.bat` to match its exact syntax before editing).

### 2h. `CLAUDE.md`

- **Environment Variables**: remove `SMTP_*` vars, add `RESEND_API_KEY`
- **Architecture**: update email stage description to "sends via Resend HTTP API"
- **Security / SES IAM scope**: remove the SES section; add a note that `RESEND_API_KEY` is a Lambda env var set via `deploy.bat`

### Phase 2 Verification

1. Run `deploy.bat` with `ResendApiKey` added to parameter overrides
2. Confirm SAM deploy succeeds and the SES IAM statement is absent from the deployed role
3. Trigger the Lambda manually in the AWS console
4. Confirm CloudWatch shows `Report emailed via Resend to ...` and email arrives
