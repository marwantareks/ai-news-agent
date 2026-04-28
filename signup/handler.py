import json
import os
import re
import hmac
import hashlib
import time
import urllib.parse
import urllib.request
import urllib.error

RESEND_API_KEY     = os.environ.get("RESEND_API_KEY", "")
RESEND_AUDIENCE_ID = os.environ.get("RESEND_AUDIENCE_ID", "")
ALLOWED_ORIGIN     = os.environ.get("SIGNUP_ALLOWED_ORIGIN", "")
EMAIL_FROM      = os.environ.get("EMAIL_FROM", "")
SIGNUP_PAGE_URL = os.environ.get("SIGNUP_PAGE_URL", "#")

_TOKEN_MAX_AGE = 86400  # 24 hours in seconds


def _make_token(email):
    ts = str(int(time.time()))
    sig = hmac.new(
        RESEND_API_KEY.encode(),
        f"{email}:{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return ts, sig


def _verify_token(email, ts_str, sig):
    try:
        ts = int(ts_str)
    except (ValueError, TypeError):
        return False
    if int(time.time()) - ts > _TOKEN_MAX_AGE:
        return False
    expected = hmac.new(
        RESEND_API_KEY.encode(),
        f"{email}:{ts_str}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


def _call_resend(email, unsubscribed, headers):
    payload = json.dumps({
        "email": email,
        "unsubscribed": unsubscribed,
        "segments": [{"id": RESEND_AUDIENCE_ID}],
    }).encode()
    url = "https://api.resend.com/contacts"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                 "Content-Type":  "application/json",
                 "User-Agent":    "ai-news-agent/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status in (200, 201):
                return None  # success
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Resend HTTP {e.code}: {body}")
        if e.code in (401, 403):
            return {"statusCode": 502, "headers": headers,
                    "body": json.dumps({"error": "Authentication error"})}
        if e.code == 422:
            return {"statusCode": 400, "headers": headers,
                    "body": json.dumps({"error": "Invalid email"})}
        return {"statusCode": 502, "headers": headers,
                "body": json.dumps({"error": "Upstream error"})}
    except urllib.error.URLError:
        return {"statusCode": 502, "headers": headers,
                "body": json.dumps({"error": "Network error reaching email service"})}
    return {"statusCode": 502, "headers": headers,
            "body": json.dumps({"error": "Unexpected response from Resend"})}


def _send_confirmation_email(email, ts, sig, confirm_base_url, headers):
    confirm_url = (
        f"{confirm_base_url}/confirm"
        f"?email={urllib.parse.quote(email)}"
        f"&ts={ts}"
        f"&sig={sig}"
    )
    html_body = (
        '<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:600px;'
        'margin:0 auto;padding:2rem;">'
        '<h2 style="color:#111;">Confirm your subscription</h2>'
        '<p style="color:#555;line-height:1.6;">Click the button below to confirm your '
        'subscription to the <strong>AI Learning Digest</strong>.</p>'
        '<table border="0" cellpadding="0" cellspacing="0" style="margin:2rem 0;">'
        '<tr>'
        '<td bgcolor="#667eea" style="background-color:#667eea;border-radius:8px;">'
        f'<a href="{confirm_url}" style="display:inline-block;padding:14px 28px;'
        'color:#ffffff;text-decoration:none;font-weight:600;font-size:16px;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;'
        'border-radius:8px;">Confirm my subscription</a>'
        '</td>'
        '</tr>'
        '</table>'
        '<p style="color:#888;font-size:.85rem;margin-top:2rem;">'
        "If the button above doesn't work, copy and paste this link into your browser:</p>"
        f'<p style="font-size:.8rem;word-break:break-all;"><a href="{confirm_url}" '
        'style="color:#667eea;text-decoration:underline;">'
        f'{confirm_url}</a></p>'
        '<p style="color:#aaa;font-size:.8rem;margin-top:1.5rem;border-top:1px solid #eee;padding-top:1rem;">'
        "This link expires in 24 hours. "
        "If you didn't request this, you can safely ignore this email.</p>"
        '</body></html>'
    )
    payload = json.dumps({
        "from": EMAIL_FROM,
        "to": [email],
        "subject": "Confirm your AI Learning Digest subscription",
        "html": html_body,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type":  "application/json",
            "User-Agent":    "ai-news-agent/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 201):
                return None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Resend confirmation email HTTP {e.code}: {body}")
        return {"statusCode": 502, "headers": headers,
                "body": json.dumps({"error": "Failed to send confirmation email"})}
    except urllib.error.URLError:
        return {"statusCode": 502, "headers": headers,
                "body": json.dumps({"error": "Network error sending confirmation email"})}
    return {"statusCode": 502, "headers": headers,
            "body": json.dumps({"error": "Unexpected response from email service"})}


def _handle_subscribe(event, headers):
    try:
        body  = json.loads(event.get("body") or "{}")
        email = body.get("email", "").strip().lower()
    except (json.JSONDecodeError, AttributeError):
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "Invalid request body"})}

    if not email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "Invalid email address"})}

    if not RESEND_API_KEY or not RESEND_AUDIENCE_ID:
        return {"statusCode": 500, "headers": headers,
                "body": json.dumps({"error": "Server misconfiguration"})}

    domain = event.get("requestContext", {}).get("domainName", "")
    confirm_base_url = f"https://{domain}" if domain else ""
    if not EMAIL_FROM or not confirm_base_url:
        return {"statusCode": 500, "headers": headers,
                "body": json.dumps({"error": "Server misconfiguration"})}

    ts, sig = _make_token(email)
    err = _send_confirmation_email(email, ts, sig, confirm_base_url, headers)
    if err:
        return err
    return {"statusCode": 200, "headers": headers,
            "body": json.dumps({"message": "Check your email to confirm your subscription"})}


def _html_confirm_success():
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Subscribed \u2014 AI Learning Digest</title>'
        '<style>'
        'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;'
        'background:#f0f2f5;display:flex;align-items:center;justify-content:center;'
        'min-height:100vh;margin:0;padding:1rem;}'
        '.card{background:#fff;border-radius:12px;padding:2.5rem 2rem;max-width:460px;'
        'width:100%;box-shadow:0 2px 12px rgba(0,0,0,.1);text-align:center;}'
        'h1{color:#111;font-size:1.5rem;margin-bottom:.75rem;}'
        'p{color:#555;line-height:1.6;}'
        '.icon{font-size:3rem;margin-bottom:1rem;}'
        '@media(prefers-color-scheme:dark){'
        'body{background:#18191a;}.card{background:#242526;box-shadow:none;}'
        'h1{color:#e4e6eb;}p{color:#aaa;}}'
        '</style></head><body>'
        '<div class="card"><div class="icon">\u2705</div>'
        "<h1>You're subscribed!</h1>"
        "<p>You'll receive the AI Learning Digest every Tuesday and Friday.</p>"
        '</div></body></html>'
    )


def _html_confirm_error(signup_url):
    safe_url = signup_url if signup_url.startswith(("http://", "https://")) else "#"
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Link Expired \u2014 AI Learning Digest</title>'
        '<style>'
        'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;'
        'background:#f0f2f5;display:flex;align-items:center;justify-content:center;'
        'min-height:100vh;margin:0;padding:1rem;}'
        '.card{background:#fff;border-radius:12px;padding:2.5rem 2rem;max-width:460px;'
        'width:100%;box-shadow:0 2px 12px rgba(0,0,0,.1);text-align:center;}'
        'h1{color:#111;font-size:1.5rem;margin-bottom:.75rem;}'
        'p{color:#555;line-height:1.6;}'
        'a{color:#667eea;}'
        '.icon{font-size:3rem;margin-bottom:1rem;}'
        '@media(prefers-color-scheme:dark){'
        'body{background:#18191a;}.card{background:#242526;box-shadow:none;}'
        'h1{color:#e4e6eb;}p{color:#aaa;}}'
        '</style></head><body>'
        '<div class="card"><div class="icon">\u26a0\ufe0f</div>'
        '<h1>Link expired or invalid</h1>'
        f'<p>This confirmation link has expired or is invalid. Please '
        f'<a href="{safe_url}">subscribe again</a>.</p>'
        '</div></body></html>'
    )


def _handle_confirm(event, headers):
    params = event.get("queryStringParameters") or {}
    email  = urllib.parse.unquote(params.get("email", "")).strip().lower()
    ts     = params.get("ts", "")
    sig    = params.get("sig", "")

    html_headers = {**headers, "Content-Type": "text/html; charset=utf-8"}

    if not email or not ts or not sig:
        return {"statusCode": 400, "headers": html_headers,
                "body": _html_confirm_error(SIGNUP_PAGE_URL)}

    if not _verify_token(email, ts, sig):
        return {"statusCode": 400, "headers": html_headers,
                "body": _html_confirm_error(SIGNUP_PAGE_URL)}

    err = _call_resend(email, False, headers)
    if err:
        return {"statusCode": 502, "headers": html_headers,
                "body": _html_confirm_error(SIGNUP_PAGE_URL)}

    return {"statusCode": 200, "headers": html_headers, "body": _html_confirm_success()}


def _handle_unsubscribe(event, headers):
    try:
        body  = json.loads(event.get("body") or "{}")
        email = body.get("email", "").strip().lower()
    except (json.JSONDecodeError, AttributeError):
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "Invalid request body"})}

    if not email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        return {"statusCode": 400, "headers": headers,
                "body": json.dumps({"error": "Invalid email address"})}

    if not RESEND_API_KEY or not RESEND_AUDIENCE_ID:
        return {"statusCode": 500, "headers": headers,
                "body": json.dumps({"error": "Server misconfiguration"})}

    err = _call_resend(email, True, headers)
    if err:
        return err
    return {"statusCode": 200, "headers": headers,
            "body": json.dumps({"message": "Unsubscribed successfully"})}


def handler(event, context):
    headers = {
        "Access-Control-Allow-Origin":  ALLOWED_ORIGIN,
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    method = event.get("requestContext", {}).get("http", {}).get("method", "POST")
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": headers, "body": ""}

    path = event.get("rawPath", "")
    if path.endswith("/confirm"):
        return _handle_confirm(event, headers)
    if path.endswith("/unsubscribe"):
        return _handle_unsubscribe(event, headers)
    return _handle_subscribe(event, headers)
