# User Guide: AI Learning Digest Agent

## 1. What This Agent Does

Every morning at 3:00 AM UTC, the AI Learning Digest Agent automatically:

1. Searches the web and YouTube for the best new AI content published in the last 7 days.
2. Covers 10 AI topics split into two tracks — **Developer** (hands-on tutorials and coding guides) and **Architect** (system design, production patterns, and strategy).
3. Uses Claude AI to select the 2–4 best resources per topic and explain why each one is worth your time.
4. Produces a "Concept of the Day" — a 3-sentence plain-English explanation of one key AI idea.
5. **Emails the digest to you** as a formatted HTML email.
6. Saves the report to S3 as a backup (you can also download and open it in any browser).

You do not need to do anything each day — it runs automatically.

---

## 2. Environment Variables You Can Change

These are the settings that control how the agent works. They are stored in AWS Lambda's configuration.

| Variable | What it does | Example value |
|---|---|---|
| `ANTHROPIC_API_KEY` | Your Claude API key — the agent uses Claude to curate and rank resources | `sk-ant-api03-...` |
| `TAVILY_API_KEY` | Your Tavily search API key — the agent uses this to search the web and YouTube | `tvly-...` |
| `EMAIL_TO` | The email address where your daily digest is sent | `you@example.com` |
| `EMAIL_FROM` | The sender address shown in the "From" field of the email | `digest@yourdomain.com` |
| `SES_REGION` | The AWS region used to send email (default: `us-east-1`) | `us-east-1` |

> **Important:** `EMAIL_FROM` must be a verified identity in Amazon SES. Do **not** use a `@gmail.com` address for `EMAIL_FROM` — Gmail addresses are not supported as SES senders. Use a custom domain address that you have verified in SES (see [Section 8](#8-ses-email-verification) for how to verify an address).

> **Changing `EMAIL_FROM`:** The Lambda IAM policy is scoped to the specific sender address set at deploy time. If you update `EMAIL_FROM` to a different address, you must also **redeploy the stack** (`deploy.bat` on Windows, or `sam build && sam deploy`) so the IAM policy ARN is updated. Updating the Lambda environment variable alone is not enough — SES will reject the send with an `AuthorizationError` until the policy is redeployed.

---

## 3. How to Change Environment Variables in AWS Console

Changes to environment variables take effect on the next invocation — no redeployment needed.

**Step-by-step:**

1. Open the [AWS Console](https://console.aws.amazon.com) and sign in.
2. In the search bar at the top, type **Lambda** and click the Lambda service.
3. In the Functions list, click **`ai-news-agent`**.
4. Click the **Configuration** tab (below the function name).
5. In the left sidebar, click **Environment variables**.
6. Click the **Edit** button (top right of the environment variables panel).
7. Find the variable you want to change, click its value field, and update it.
8. Click **Save** at the bottom of the page.

> The change takes effect the next time the function runs (either automatically at 03:00 UTC or when you trigger it manually).

---

## 4. How to Test the Application

Follow these steps to trigger a manual run and verify everything is working.

### Step 1: Delete today's report from S3 (to bypass the duplicate-run guard)

The agent skips a run if it already ran today. To force a fresh run, delete today's report first:

1. In the AWS Console, search for **S3** and click the S3 service.
2. Find and click the bucket named **`ai-news-agent-reports-<AccountId>`** (e.g. `ai-news-agent-reports-613261654297`).
3. Find the file named `YYYY-MM-DD-ai-learning.html` (today's date).
4. Check the checkbox next to it and click **Delete**.
5. Type `permanently delete` in the confirmation box and click **Delete objects**.

> If no file with today's date exists, you can skip this step.

### Step 2: Run the Lambda manually

1. Navigate back to **Lambda** → **`ai-news-agent`**.
2. Click the **Test** tab.
3. Leave the event JSON as `{}` (the agent ignores the event payload).
4. Click the **Test** button.

### Step 3: Watch it run (~60–90 seconds)

The test tab shows "Executing function..." while it runs. Wait for it to complete. A green banner means success; a red banner means it encountered an error (see [Section 5](#5-how-to-monitor--check-logs) to diagnose).

### Step 4: Check your email inbox

Check the inbox for the `EMAIL_TO` address. The subject line will be:

```
AI Learning Digest · YYYY-MM-DD
```

If it's not in your inbox within a few minutes, check your spam/junk folder.

### Step 5: (Optional) Download the report from S3

1. Go to **S3** → `ai-news-agent-reports-<AccountId>`.
2. Click the HTML file for today.
3. Click **Download** to save it locally and open it in any browser.

---

## 5. How to Monitor / Check Logs

The agent logs every step of its run to AWS CloudWatch.

### How to find the logs

1. In the AWS Console, search for **CloudWatch** and click the CloudWatch service.
2. In the left sidebar, click **Log groups**.
3. Find and click **`/aws/lambda/ai-news-agent`**.
4. Click the most recent log stream (top of the list — sorted by last event).

### What to look for

| Log line | Meaning |
|---|---|
| `Starting AI learning digest for YYYY-MM-DD` | Run has started successfully |
| `Generative AI Fundamentals -> 5 results` | Tavily search completed for a topic |
| `Curating Developer Track with Claude Haiku...` | Claude curation starting |
| `Report uploaded to s3://...` | HTML report saved to S3 |
| `Report emailed via SES to you@example.com` | Email sent successfully |
| `Report for YYYY-MM-DD already exists in S3. Skipping.` | Agent skipped — already ran today (normal behavior) |
| `WARNING ... query '...' failed` | One Tavily search failed — not fatal, run continues |
| `ERROR SES send failed` | Email failed — report is still in S3; check SES configuration |
| `ERROR Missing API keys` | API keys not set or incorrect |

### Filtering logs

Use the CloudWatch log filter bar to search for specific text, for example:
- Filter by `ERROR` to see only errors
- Filter by `emailed` to confirm email delivery
- Filter by `Skipping` to confirm the duplicate guard worked

---

## 6. Daily Schedule

The agent runs automatically every day at **03:00 UTC** (no action needed from you).

| UTC Time | Example in other timezones |
|---|---|
| 03:00 UTC | 10:00 PM EST (previous day) |
| 03:00 UTC | 05:00 AM CET |
| 03:00 UTC | 11:00 AM SGT |

You should receive your email digest within a few minutes of 03:00 UTC each day.

If the Lambda does not run at the expected time, check:

1. AWS Console → **EventBridge** → **Rules** → `ai-news-agent-daily` → confirm status is **Enabled**.
2. Check CloudWatch logs for any error from the last scheduled run.

---

## 7. Idempotency Explained

**Idempotency** means the agent is safe to run multiple times — it will only generate and email one report per day.

Before making any API calls, the agent checks S3 for a file named `YYYY-MM-DD-ai-learning.html`. If it already exists, the agent exits immediately without calling Tavily or Claude.

This means:
- If EventBridge fires twice (rare but possible), the second run does nothing.
- If you click Test in the Lambda console after the automatic run, it will skip.
- No wasted API calls, no duplicate emails.

**To force a re-run:** Delete today's file from S3 (see [Section 4, Step 1](#step-1-delete-todays-report-from-s3-to-bypass-the-duplicate-run-guard)).

---

## 8. SES Email Verification

Amazon SES requires both the **sender** (`EMAIL_FROM`) and the **recipient** (`EMAIL_TO`) email addresses to be verified before it will deliver email. This is a one-time setup per address.

### How to verify an email address in SES

1. In the AWS Console, search for **SES** (or "Simple Email Service") and click it.
2. Make sure you are in the **US East (N. Virginia)** region (top-right corner of the console).
3. In the left sidebar, click **Verified identities**.
4. Click **Create identity**.
5. Select **Email address**, enter the address, and click **Create identity**.
6. AWS will send a verification email to that address. Open it and click the link.
7. The identity status changes to **Verified**. Done.

Repeat for both `EMAIL_FROM` and `EMAIL_TO` if they are different addresses.

> **Note:** If your account is still in SES Sandbox mode, both sender and recipient must be verified. To send to any unverified address, request SES production access via Console → SES → Account dashboard → Request production access.

### Changing the sender address after deployment

If you want to use a different `EMAIL_FROM` address in the future:

1. Verify the new address in SES (steps above).
2. Update `EMAIL_FROM` in your `.env` file (used by `deploy.bat` when reading parameters).
3. Run `deploy.bat` (or `sam build && sam deploy`) — this updates both the Lambda environment variable **and** the IAM policy ARN in one step.

> Do not update `EMAIL_FROM` only via the Lambda console — the IAM policy will still point to the old address and SES sends will fail.

---

## 9. Troubleshooting

| Problem | What to check |
|---|---|
| **Email not received** | Check your spam/junk folder. Verify `EMAIL_TO` is correct in Lambda environment variables. Confirm `EMAIL_TO` is a verified SES identity. |
| **Email arrives but "From" shows `@gmail.com`** | Change `EMAIL_FROM` to a custom domain address (e.g. `digest@yourdomain.com`), not a Gmail address. Gmail addresses cannot be used as SES senders reliably. |
| **Lambda timed out** | Check CloudWatch logs for which stage it was in. Most likely cause: invalid API key preventing Tavily or Claude from responding. Verify `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` are correct. |
| **No report in S3 after Lambda ran** | Open CloudWatch logs for that run and look for `ERROR` lines. Common causes: API keys missing or expired, Tavily quota exceeded. |
| **Agent skipped (no new report)** | Check CloudWatch logs for `already exists in S3. Skipping.` — this is normal. Delete today's S3 file and re-run to force a fresh report. |
| **SES `MessageRejected` error in logs** | The `EMAIL_TO` address is not verified in SES. Verify it (see Section 8). |
| **SES `InvalidClientTokenId` error** | AWS credentials for the Lambda role are wrong or expired. Check the IAM role `ai-news-agent-lambda-role` has `ses:SendRawEmail` permission. |
| **EventBridge not triggering** | Console → EventBridge → Rules → `ai-news-agent-daily` → confirm it is **Enabled**. |
| **Report renders with broken layout in email** | Your email client may not support full HTML/CSS. Download the file from S3 and open it in a browser for the full experience. |
