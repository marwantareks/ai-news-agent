import json
import os
import urllib.request
import urllib.error

RESEND_API_KEY     = os.environ.get("RESEND_API_KEY", "")
RESEND_AUDIENCE_ID = os.environ.get("RESEND_AUDIENCE_ID", "")
ALLOWED_ORIGIN     = os.environ.get("SIGNUP_ALLOWED_ORIGIN", "*")


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


def _handle_subscribe(event, headers):
    try:
        body  = json.loads(event.get("body") or "{}")
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

    err = _call_resend(email, False, headers)
    if err:
        return err
    return {"statusCode": 200, "headers": headers,
            "body": json.dumps({"message": "Subscribed successfully"})}


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
        "Access-Control-Allow-Methods": "POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 204, "headers": headers, "body": ""}

    path = event.get("rawPath", "")
    if path.endswith("/unsubscribe"):
        return _handle_unsubscribe(event, headers)
    return _handle_subscribe(event, headers)
