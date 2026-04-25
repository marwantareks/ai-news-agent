# Plan: Fix Resend API Implementation + Unsubscribe Feature

**Date:** 2026-04-25
**Trigger:** Review of Resend docs at https://resend.com/docs/llms-full.txt against current implementation

---

## Phase 1: Fix Existing Resend API Issues ✅ COMPLETE

### change file name
change subscribe page index.html name to subscribe.html and check for dependencies on the file and fix them 

### `signup/handler.py` — 4 issues

---

#### Issue 1: Wrong API endpoint (CRITICAL)

**Current:**
```python
url = f"https://api.resend.com/audiences/{RESEND_AUDIENCE_ID}/contacts"
```

**Problem:** `/audiences/{id}/contacts` is the **legacy** endpoint. According to current Resend docs, the correct endpoint is `POST /contacts` with a `segments` array in the request body. The legacy path may be deprecated or removed in future.

**Fix:**
```python
url = "https://api.resend.com/contacts"
payload = json.dumps({
    "email": email,
    "unsubscribed": False,
    "segments": [{"id": RESEND_AUDIENCE_ID}],
}).encode()
```

---

#### Issue 2: Missing `unsubscribed: false` (HIGH)

**Current:** Payload is just `{"email": email}` — no `unsubscribed` field.

**Problem:** The `unsubscribed` field controls the contact's "global subscription status". If someone previously unsubscribed and then signs up again via the signup page, the POST will add/update the contact record but **will not re-subscribe them** unless `unsubscribed: false` is explicitly set. They silently remain opted out of all future broadcasts.

**Fix:** Always include `"unsubscribed": False` in the payload.

---

#### Issue 3: Incorrect 409 special-case (MEDIUM)

**Current:**
```python
except urllib.error.HTTPError as e:
    if e.code == 409:  # already subscribed
        return {"statusCode": 200, ...}
```

**Problem:** Resend does **not document a 409 response** for duplicate contacts on the contacts endpoint. The 409 assumption was likely carried over from a different API or the legacy audiences endpoint. On the new `/contacts` endpoint, a duplicate email is an idempotent upsert returning 200. If a 409 is ever returned, it signals a different conflict condition and should not be silently treated as success.

**Fix:** Remove the 409 special-case. Add handling for documented error codes:
- `401` / `403` → 502 "Authentication error" (bad API key)
- `422` → 400 "Invalid email" (Resend validation failure)
- Any other non-2xx → 502 "Upstream error"

---

#### Issue 4: Missing `urllib.error.URLError` handling (MEDIUM)

**Current:**
```python
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        ...
except urllib.error.HTTPError as e:
    ...
```

**Problem:** `urllib.error.URLError` (network timeout, DNS failure, connection refused) is the **parent class** of `HTTPError` but is not caught here. A network failure raises `URLError`, propagating uncaught and causing Lambda to return a 500 with a Python traceback instead of a clean JSON response.

**Fix:** Add a separate `except urllib.error.URLError` clause after the `HTTPError` clause:
```python
except urllib.error.URLError:
    return {"statusCode": 502, "headers": headers,
            "body": json.dumps({"error": "Network error reaching email service"})}
```

---

### `agent.py` `send_email()` — 2 issues

---

#### Issue 5: `audience_id` should be `segment_id` (MEDIUM)

**Current:**
```python
broadcast = resend.Broadcasts.create({
    "audience_id": RESEND_AUDIENCE_ID,
    ...
})
```

**Problem:** The Broadcasts API **requires `segment_id`**, not `audience_id`. The docs note "Audiences are now called Segments — legacy field names still supported for compatibility", but relying on legacy behaviour is a risk. If the SDK or Resend's backend drops legacy support, broadcasts will silently fail or return a validation error.

**Fix:** Change `"audience_id"` → `"segment_id"`:
```python
broadcast = resend.Broadcasts.create({
    "segment_id": RESEND_AUDIENCE_ID,
    ...
})
```

---

#### Issue 6: Two API calls where one suffices (LOW)

**Current:**
```python
broadcast = resend.Broadcasts.create({...})
resend.Broadcasts.send(broadcast["id"])
```

**Problem:** Two round-trips where one is possible. If create succeeds but send fails, an orphaned draft broadcast is left in Resend that will never be sent. The Broadcasts API supports `"send": True` in the create body to send immediately in a single call.

**Fix:**
```python
resend.Broadcasts.create({
    "segment_id": RESEND_AUDIENCE_ID,
    "from":       EMAIL_FROM,
    "subject":    f"AI Learning Digest · {date_str}",
    "html":       html_content,
    "send":       True,
})
```

---
### Phase 1 update documentation
1. update documentation readme, architecture and user_guide md files with changes in phase 1
---

### Phase 1 Summary

| File | Issue | Severity | Change |
|---|---|---|---|
| `signup/handler.py` | Wrong endpoint | CRITICAL | `POST /contacts` + `segments` array |
| `signup/handler.py` | Missing `unsubscribed: false` | HIGH | Add to payload |
| `signup/handler.py` | Wrong 409 assumption | MEDIUM | Remove 409 case; handle 401/422 |
| `signup/handler.py` | URLError not caught | MEDIUM | Add `URLError` except clause |
| `agent.py` | `audience_id` → `segment_id` | MEDIUM | Rename field |
| `agent.py` | Two-call create+send | LOW | Use `"send": True` in create |

### Phase 1 Files to Change

- `signup/handler.py`
- `agent.py` (only the `send_email()` function)

---
don't move to phase 2 till confirm that phase 1 is complete
---

## Phase 2: Unsubscribe Feature ✅ COMPLETE

### Overview

Two-layer unsubscribe approach:

1. **Resend native unsubscribe** — add `{{{RESEND_UNSUBSCRIBE_URL}}}` to every broadcast. Resend generates a signed, one-click unsubscribe URL per recipient and handles the flagging automatically. Required for CAN-SPAM / GDPR compliance.

2. **Custom unsubscribe page** — a hosted page at the S3 website where users can manually enter their email to unsubscribe. Useful for users whose email client strips links, or who want to unsubscribe without opening an email.

The two approaches are independent — both call the same underlying Resend contact state (`unsubscribed: true`), but via different paths.

---

### Resend Unsubscribe API

The Contacts API is an upsert. To unsubscribe a contact, `POST /contacts` with `"unsubscribed": true`:

```http
POST https://api.resend.com/contacts
Authorization: Bearer {RESEND_API_KEY}
Content-Type: application/json

{
  "email": "user@example.com",
  "unsubscribed": true,
  "segments": [{"id": "{RESEND_AUDIENCE_ID}"}]
}
```

The contact remains in the segment but is flagged globally and excluded from all future broadcasts. They are **not deleted** — their record is preserved.

Resend also provides a built-in template variable for use in broadcast HTML:
```html
<a href="{{{RESEND_UNSUBSCRIBE_URL}}}">Unsubscribe</a>
```
Resend expands this to a per-recipient signed URL. Clicking it marks the contact as unsubscribed directly in Resend without any code on our side.

---

### Changes Required

#### 2a. `agent.py` — Add unsubscribe link to broadcast HTML

In `generate_html()`, add an unsubscribe footer to the HTML output using Resend's native template variable. This is the primary unsubscribe path.

Add inside the `<body>` near the bottom:
```html
<div style="text-align:center; padding: 1.5rem 1rem; font-size:.78rem; color:#aaa;">
  Don't want these? <a href="{{{RESEND_UNSUBSCRIBE_URL}}}" style="color:#aaa;">Unsubscribe</a>
</div>
```

**Important:** `{{{RESEND_UNSUBSCRIBE_URL}}}` uses triple braces (Resend's template syntax — not a Jinja/Mustache pattern used elsewhere). It must appear literally in the HTML string sent to Resend — do not escape or interpolate it in Python.

---

#### 2b. `signup/unsubscribe.html` — New static page

New file alongside `signup/index.html`. Same visual style as the subscribe page.

**Behaviour:**
- URL: `http://ai-news-agent-signup-<AccountId>.s3-website-<region>.amazonaws.com/unsubscribe.html`
- Contains an email input field pre-filled from the `?email=` query parameter (for links in emails)
- On submit: calls `POST {UNSUBSCRIBE_API_URL}` with `{"email": "..."}`
- Shows success or error message inline

**Placeholder:** Contains the literal string `UNSUBSCRIBE_API_URL` (same pattern as `SIGNUP_API_URL` in `index.html`), replaced by `deploy.bat` at deploy time.

---

#### 2c. `signup/handler.py` — Add `/unsubscribe` route

Extend the existing Lambda (no new function needed — keeps infra simple) to handle a second path.

**Route detection:** inspect `event["rawPath"]` to distinguish `/subscribe` from `/unsubscribe`.

**Unsubscribe logic:**
```python
def _handle_unsubscribe(event, headers):
    try:
        body  = json.loads(event.get("body") or "{}")
        email = body.get("email", "").strip().lower()
    except (json.JSONDecodeError, AttributeError):
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "Invalid request body"})}

    if not email or "@" not in email:
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "Invalid email address"})}

    payload = json.dumps({
        "email": email,
        "unsubscribed": True,
        "segments": [{"id": RESEND_AUDIENCE_ID}],
    }).encode()

    url = "https://api.resend.com/contacts"
    req = urllib.request.Request(
        url, data=payload,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status in (200, 201):
                return {"statusCode": 200, "headers": headers,
                        "body": json.dumps({"message": "Unsubscribed successfully"})}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return {"statusCode": 502, "headers": headers,
                    "body": json.dumps({"error": "Authentication error"})}
        return {"statusCode": 502, "headers": headers,
                "body": json.dumps({"error": "Upstream error"})}
    except urllib.error.URLError:
        return {"statusCode": 502, "headers": headers,
                "body": json.dumps({"error": "Network error reaching email service"})}

    return {"statusCode": 502, "headers": headers,
            "body": json.dumps({"error": "Unexpected response"})}
```

**Updated `handler()` dispatch:**
```python
def handler(event, context):
    headers = { ... }  # CORS headers unchanged

    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 204, "headers": headers, "body": ""}

    path = event.get("rawPath", "")
    if path.endswith("/unsubscribe"):
        return _handle_unsubscribe(event, headers)
    return _handle_subscribe(event, headers)
```

The existing subscribe logic moves into `_handle_subscribe()` unchanged.

---

#### 2d. `template.yaml` — Add unsubscribe API routes

Add two new events to `SignupFunction` (POST and OPTIONS for CORS preflight):

```yaml
UnsubscribePost:
  Type: HttpApi
  Properties:
    Path: /unsubscribe
    Method: POST
UnsubscribeOptions:
  Type: HttpApi
  Properties:
    Path: /unsubscribe
    Method: OPTIONS
```

No new Lambda, no new IAM role — the existing `SignupFunction` handles both routes.

Also add a new CloudFormation Output:
```yaml
UnsubscribeApiUrl:
  Description: Unsubscribe endpoint URL
  Value: !Sub "https://${ServerlessHttpApi}.execute-api.${AWS::Region}.amazonaws.com/unsubscribe"
```

---

#### 2e. `deploy.bat` — Inject UNSUBSCRIBE_API_URL and upload page

After the existing signup page upload, add:

```bat
rem Retrieve UnsubscribeApiUrl from stack outputs
for /f "tokens=*" %%i in ('aws cloudformation describe-stacks --stack-name %STACK% --query "Stacks[0].Outputs[?OutputKey=='UnsubscribeApiUrl'].OutputValue" --output text') do set UNSUBSCRIBE_API_URL=%%i

rem Inject URL into unsubscribe.html and upload to S3
powershell -Command "(Get-Content signup\unsubscribe.html) -replace 'UNSUBSCRIBE_API_URL', '%UNSUBSCRIBE_API_URL%' | Set-Content signup\unsubscribe.html.tmp"
aws s3 cp signup\unsubscribe.html.tmp s3://ai-news-agent-signup-%AWS_ACCOUNT_ID%/unsubscribe.html --content-type text/html
del signup\unsubscribe.html.tmp
```

---
### Phase 2 update documentation
1. update documentation readme, architecture and user_guide md files with changes in phase 1
---

### Phase 2 Summary

| File | Change |
|---|---|
| `agent.py` | Add `{{{RESEND_UNSUBSCRIBE_URL}}}` footer to broadcast HTML in `generate_html()` |
| `signup/unsubscribe.html` | New file — static unsubscribe page with `UNSUBSCRIBE_API_URL` placeholder |
| `signup/handler.py` | Add `/unsubscribe` route; refactor into `_handle_subscribe` / `_handle_unsubscribe` helpers |
| `template.yaml` | Add `UnsubscribePost` + `UnsubscribeOptions` events to `SignupFunction`; add `UnsubscribeApiUrl` output |
| `deploy.bat` | Inject `UNSUBSCRIBE_API_URL` into `unsubscribe.html` and upload to S3 |

### Phase 2 Files to Change

- `agent.py`
- `signup/handler.py`
- `signup/unsubscribe.html` (new)
- `template.yaml`
- `deploy.bat`

---

## Full Implementation Order

### Phase 1 (fix existing issues first)
1. `signup/handler.py` — fix endpoint, add `unsubscribed: false`, fix error handling
2. `agent.py` — fix `segment_id`, collapse to single `send` call
3. Deploy and verify subscribe flow end-to-end

### Phase 2 (unsubscribe feature)
4. `agent.py` — add `{{{RESEND_UNSUBSCRIBE_URL}}}` footer to `generate_html()`
5. `signup/handler.py` — add `/unsubscribe` route and refactor into helper functions
6. `signup/unsubscribe.html` — create new page
7. `template.yaml` — add unsubscribe API routes and output
8. `deploy.bat` — add unsubscribe page injection and upload
9. Deploy and verify: click unsubscribe link in a test broadcast, confirm contact is flagged in Resend dashboard
