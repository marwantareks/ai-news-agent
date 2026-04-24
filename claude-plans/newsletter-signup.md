# Plan: Newsletter Self-Service Signup (Resend Audiences + Lambda Signup Endpoint)

## Context

Currently `EMAIL_TO` is a static comma-separated env var maintained manually. This plan replaces it with a Resend Audience as the source of truth for subscribers, and adds a public signup form backed by a dedicated Lambda + API Gateway endpoint. Unsubscribes are handled automatically by Resend.

The plan has three phases:
1. Migrate the send path to use Resend Audiences / Broadcasts (replaces `EMAIL_TO`)
2. Add a signup Lambda + API Gateway endpoint (writes new contacts to the Audience)
3. Build and host a static HTML signup page (on S3 static website)

---

## Files to Modify / Create

- `agent.py` — Phase 1
- `template.yaml` — Phase 1 + 2 + 3
- `deploy.bat` — Phase 1 (new SAM parameter)
- `signup/handler.py` *(new)* — Phase 2
- `signup/index.html` *(new)* — Phase 3
- `CLAUDE.md` — Phase 3 (document the new endpoint and S3 website URL)

---

## Phase 1: Migrate Send Path to Resend Audiences

### 1a. Resend Dashboard — create an audience

1. Log in to resend.com → **Audiences** → **Create Audience**
2. Name it (e.g. `AI News Agent`)
3. Copy the **Audience ID** — it will be stored as `RESEND_AUDIENCE_ID`
4. Optionally migrate existing recipients: manually add them as contacts in the audience

### 1b. `.env` — add new var, deprecate `EMAIL_TO`

```
RESEND_AUDIENCE_ID=aud_xxxxxxxxxxxxxxxx   # add
# EMAIL_TO is no longer used after Phase 1
```

> `EMAIL_TO` can remain in `.env` temporarily as a fallback during transition but will be removed in Phase 1d.

### 1c. `agent.py` — env var block

Replace:
```python
EMAIL_TO = os.getenv("EMAIL_TO", "")
```
With:
```python
RESEND_AUDIENCE_ID = os.getenv("RESEND_AUDIENCE_ID", "")
```

### 1d. `agent.py` — replace `send_email()` body

Instead of sending to a static list, use the **Resend Broadcasts API** to send to the entire audience in one call:

```python
def send_email(html_content: str, date_str: str) -> None:
    """Send the HTML report as a Resend Broadcast to the audience. Skipped if config missing."""
    import resend

    if not all([RESEND_AUDIENCE_ID, EMAIL_FROM, RESEND_API_KEY]):
        log.warning("Email config incomplete — skipping. Set RESEND_AUDIENCE_ID, EMAIL_FROM, RESEND_API_KEY.")
        return

    resend.api_key = RESEND_API_KEY
    try:
        broadcast = resend.Broadcasts.create({
            "audience_id": RESEND_AUDIENCE_ID,
            "from": EMAIL_FROM,
            "subject": f"AI Learning Digest · {date_str}",
            "html": html_content,
        })
        resend.Broadcasts.send(broadcast["id"])
        log.info("Broadcast sent via Resend audience %s", RESEND_AUDIENCE_ID)
    except Exception as e:
        log.error("Resend broadcast failed: %s", e)
```

> Note: verify exact Resend Broadcasts SDK method names against the resend-python SDK docs before implementing — the API shape may differ slightly.

### 1e. `template.yaml` — parameters

Remove `EmailTo` parameter. Add:
```yaml
  ResendAudienceId:
    Type: String
    Description: Resend Audience ID for newsletter subscribers
```

Update Globals env vars:
```yaml
# Remove:
        EMAIL_TO: !Ref EmailTo
# Add:
        RESEND_AUDIENCE_ID: !Ref ResendAudienceId
```

### 1f. `deploy.bat` — parameter overrides

Remove `EmailTo` override. Add:
```bat
ParameterOverrides="... ResendAudienceId=%RESEND_AUDIENCE_ID%"
```

### Phase 1 Verification

1. Add a test contact to the Resend Audience manually
2. Delete today's report to force a run: `del reports\YYYY-MM-DD-ai-learning.html`
3. Run `python agent.py` locally
4. Confirm log shows: `Broadcast sent via Resend audience ...`
5. Confirm test contact receives the email
6. Test graceful skip: remove `RESEND_AUDIENCE_ID` from `.env`, re-run — confirm warning, no crash

---

## Phase 2: Signup Lambda + API Gateway

### 2a. `signup/handler.py` *(new file)*

A new Lambda handler that accepts `POST` with `{"email": "..."}` and adds the contact to the Resend Audience:

```python
import json
import os
import urllib.request

RESEND_API_KEY    = os.environ.get("RESEND_API_KEY", "")
RESEND_AUDIENCE_ID = os.environ.get("RESEND_AUDIENCE_ID", "")
ALLOWED_ORIGIN    = os.environ.get("SIGNUP_ALLOWED_ORIGIN", "*")


def handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
        "Access-Control-Allow-Methods": "POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 204, "headers": headers, "body": ""}

    try:
        body = json.loads(event.get("body") or "{}")
        email = body.get("email", "").strip().lower()
    except (json.JSONDecodeError, AttributeError):
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "Invalid request body"})}

    if not email or "@" not in email:
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "Invalid email address"})}

    if not RESEND_API_KEY or not RESEND_AUDIENCE_ID:
        return {"statusCode": 500, "headers": headers,
                "body": json.dumps({"error": "Server misconfiguration"})}

    payload = json.dumps({"email": email}).encode()
    url = f"https://api.resend.com/audiences/{RESEND_AUDIENCE_ID}/contacts"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status in (200, 201):
                return {"statusCode": 200, "headers": headers,
                        "body": json.dumps({"message": "Subscribed successfully"})}
    except urllib.error.HTTPError as e:
        if e.code == 409:  # already subscribed
            return {"statusCode": 200, "headers": headers,
                    "body": json.dumps({"message": "Already subscribed"})}
        return {"statusCode": 502, "headers": headers,
                "body": json.dumps({"error": "Upstream error"})}

    return {"statusCode": 502, "headers": headers,
            "body": json.dumps({"error": "Unexpected response from Resend"})}
```

> Uses only stdlib (`urllib`, `json`, `os`) — no new dependencies.

### 2b. `template.yaml` — new Lambda + HTTP API Gateway

Add a second Lambda resource and an HTTP API:

```yaml
  SignupFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: ai-news-agent-signup
      Handler: signup/handler.handler
      Runtime: python3.12
      Timeout: 10
      MemorySize: 128
      Environment:
        Variables:
          RESEND_API_KEY: !Ref ResendApiKey
          RESEND_AUDIENCE_ID: !Ref ResendAudienceId
          SIGNUP_ALLOWED_ORIGIN: !Sub "https://${SignupBucket}.s3-website-${AWS::Region}.amazonaws.com"
      Events:
        SignupPost:
          Type: HttpApi
          Properties:
            Path: /subscribe
            Method: POST
        SignupOptions:
          Type: HttpApi
          Properties:
            Path: /subscribe
            Method: OPTIONS

Outputs:
  SignupApiUrl:
    Description: Signup endpoint URL
    Value: !Sub "https://${ServerlessHttpApi}.execute-api.${AWS::Region}.amazonaws.com/subscribe"
```

### Phase 2 Verification

1. Deploy: `deploy.bat`
2. Note the `SignupApiUrl` from SAM outputs
3. Test with curl:
   ```bash
   curl -X POST <SignupApiUrl> -H "Content-Type: application/json" -d '{"email":"test@example.com"}'
   ```
4. Confirm contact appears in the Resend Audience dashboard
5. Test duplicate: re-send same email — confirm 200 "Already subscribed"
6. Test invalid input: `{}` body — confirm 400

---

## Phase 3: Static HTML Signup Page (S3 Website)

### 3a. `signup/index.html` *(new file)*

A self-contained, no-framework HTML page with a single email input form. JavaScript submits to the `SignupApiUrl` via `fetch` and shows inline success/error feedback. Style should match the existing report's dark-mode aesthetic (reuse its CSS variables). The email input form should validate the user input as an email format. The page should include text welcoming the user the explaining the purpose of the AI learning digest and what they will expect to get in the email and when the emails are sent.

Key elements:
- Email `<input>` + Submit `<button>`
- Inline status message (success / already subscribed / error)
- No external dependencies (no CDN fonts, no JS libraries)
- `SIGNUP_API_URL` placeholder that gets replaced at deploy time (see 3b)

### 3b. `template.yaml` — S3 static website bucket

Add a public S3 bucket configured for static website hosting:

```yaml
  SignupBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub "ai-news-agent-signup-${AWS::AccountId}"
      WebsiteConfiguration:
        IndexDocument: index.html
      PublicAccessBlockConfiguration:
        BlockPublicAcls: false
        BlockPublicPolicy: false
        IgnorePublicAcls: false
        RestrictPublicBuckets: false

  SignupBucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref SignupBucket
      PolicyDocument:
        Statement:
          - Effect: Allow
            Principal: "*"
            Action: s3:GetObject
            Resource: !Sub "arn:aws:s3:::${SignupBucket}/*"

Outputs:
  SignupPageUrl:
    Description: Public signup page URL
    Value: !Sub "http://${SignupBucket}.s3-website-${AWS::Region}.amazonaws.com"
```

### 3c. `deploy.bat` — upload signup page after SAM deploy

After `sam deploy`, add a step to inject the API URL and upload `index.html`:

```bat
rem Retrieve SignupApiUrl from stack outputs
for /f "tokens=*" %%i in ('aws cloudformation describe-stacks --stack-name ai-news-agent --query "Stacks[0].Outputs[?OutputKey=='SignupApiUrl'].OutputValue" --output text') do set SIGNUP_API_URL=%%i

rem Inject API URL into index.html and upload to S3
powershell -Command "(Get-Content signup\index.html) -replace 'SIGNUP_API_URL', '%SIGNUP_API_URL%' | Set-Content signup\index.html.tmp"
aws s3 cp signup\index.html.tmp s3://ai-news-agent-signup-%AWS_ACCOUNT_ID%/index.html --content-type text/html
del signup\index.html.tmp
```

### Phase 3 Verification

1. Run `deploy.bat`
2. Open `SignupPageUrl` in a browser
3. Submit a new email — confirm success message and contact appears in Resend Audience
4. Share `SignupPageUrl` as the public subscription link

---

## CLAUDE.md Updates (end of Phase 3)

- **Environment Variables**: replace `EMAIL_TO` with `RESEND_AUDIENCE_ID`
- **Architecture**: note email stage now uses Resend Broadcasts; add signup endpoint description
- **New section — Newsletter Signup**: document `SignupApiUrl`, `SignupPageUrl`, and `signup/` directory
