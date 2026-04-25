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
| `RESEND_API_KEY` | Your Resend API key — used to send the digest as a Broadcast to your audience | `re_...` |
| `RESEND_AUDIENCE_ID` | Your Resend Audience ID — every contact in this audience receives each broadcast | `aud_xxxxxxxx` |
| `EMAIL_FROM` | The sender address shown in the "From" field of the email | `digest@yourdomain.com` |

> **Important:** `EMAIL_FROM` must be an address on a domain you have verified in your [Resend](https://resend.com) account. `RESEND_AUDIENCE_ID` is found in the Resend dashboard under **Audiences** — it looks like `aud_xxxxxxxx`.

> **Who receives the digest?** Every contact in your Resend Audience. New subscribers added via the signup page are automatically included in all future broadcasts. To add yourself manually: Resend dashboard → Audiences → your audience → Add Contact.

> **Changing `EMAIL_FROM`:** Resend does not require IAM policy updates when changing addresses. Update `EMAIL_FROM` in your `.env` file and run `deploy.bat` to push the new value to Lambda, or update it directly in the Lambda console (Configuration → Environment variables).

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

Check the inbox for any contact in your Resend Audience. The subject line will be:

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
| `Report emailed via Resend to you@example.com` | Email sent successfully |
| `Report for YYYY-MM-DD already exists in S3. Skipping.` | Agent skipped — already ran today (normal behavior) |
| `WARNING ... query '...' failed` | One Tavily search failed — not fatal, run continues |
| `ERROR Resend broadcast failed` | Broadcast failed — report is still in S3; check `RESEND_API_KEY`, `RESEND_AUDIENCE_ID`, and `EMAIL_FROM` domain |
| `ERROR Missing API keys` | API keys not set or incorrect |

### Filtering logs

Use the CloudWatch log filter bar to search for specific text, for example:
- Filter by `ERROR` to see only errors
- Filter by `emailed` to confirm email delivery
- Filter by `Skipping` to confirm the duplicate guard worked

---

## 6. Daily Schedule

The agent runs automatically every **Tuesday and Friday at 03:00 UTC** (no action needed from you).

| UTC Time | Example in other timezones |
|---|---|
| 03:00 UTC Tuesday/Friday | 10:00 PM EST (Monday/Thursday) |
| 03:00 UTC Tuesday/Friday | 05:00 AM CET (Tuesday/Friday) |
| 03:00 UTC Tuesday/Friday | 11:00 AM SGT (Tuesday/Friday) |

You should receive your email digest within a few minutes of 03:00 UTC on Tuesdays and Fridays.

If the Lambda does not run at the expected time, check:

1. AWS Console → **EventBridge** → **Rules** → `ai-news-agent-weekly` → confirm status is **Enabled**.
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

## 8. Resend Email Setup

The agent sends email via [Resend](https://resend.com) — a developer-friendly email API that works for both local and AWS modes without any IAM configuration. Email is sent as a **Broadcast** to all contacts in a Resend Audience.

### One-time setup

1. Sign up at [resend.com](https://resend.com) and create an API key in the Resend dashboard.
2. Add the key to your `.env` file as `RESEND_API_KEY=re_...`.
3. In the Resend dashboard, go to **Audiences** → **Create Audience**. Copy the Audience ID (format: `aud_xxxxxxxx`) and add it to your `.env` as `RESEND_AUDIENCE_ID=aud_...`.
4. Set `EMAIL_FROM` to a sender address on a domain you own and have verified in Resend (see below).
5. Add yourself as a contact: Resend → Audiences → your audience → **Add Contact**.

### How to verify a sending domain in Resend

1. In the Resend dashboard, go to **Domains** → **Add Domain**.
2. Enter your domain (e.g. `yourdomain.com`) and click **Add**.
3. Resend shows you DNS records (MX, TXT, DKIM) to add to your domain registrar.
4. Add the records, then click **Verify** in Resend. Verification typically completes within a few minutes.
5. Once verified, you can send from any address on that domain (e.g. `digest@yourdomain.com`).

> **Testing without a custom domain:** Resend provides a shared `onboarding@resend.dev` sender on free accounts. Set `EMAIL_FROM=onboarding@resend.dev` to test delivery before setting up your own domain. Note: the shared sender can only deliver to the email address registered on your Resend account.

### Changing the sender address after deployment

1. Verify the new domain in Resend (steps above).
2. Update `EMAIL_FROM` in your `.env` file.
3. Run `deploy.bat` — this pushes the new value to the Lambda environment variable.

> You can also update `EMAIL_FROM` directly in the Lambda console (Configuration → Environment variables) without redeploying.

---

## 9. Newsletter Signup & Unsubscribe

A public signup page lets anyone subscribe to the digest without any manual steps on your end.

**Signup page URL:** `http://ai-news-agent-signup-<AccountId>.s3-website-<region>.amazonaws.com`
(printed at the end of every `deploy.bat` run)

When someone submits their email:
1. The page calls `POST /subscribe` on the API Gateway endpoint.
2. The backend Lambda adds the contact to your Resend Audience.
3. The next broadcast automatically includes them.

**Managing subscribers:** Resend dashboard → Audiences → your audience. You can view, add, or remove contacts here.

### How subscribers unsubscribe

There are two ways a subscriber can opt out:

**1. Unsubscribe link in every email (primary)**
Every broadcast contains an **Unsubscribe** link in the footer. Clicking it takes the subscriber to a Resend-hosted page that opts them out instantly — no email address entry required.

**2. Manual unsubscribe page (fallback)**
A static page at `/unsubscribe.html` on the same S3 site lets anyone enter their email to unsubscribe manually — useful when email links are blocked by their client.

`http://ai-news-agent-signup-<AccountId>.s3-website-<region>.amazonaws.com/unsubscribe.html`

The page also accepts a `?email=` query parameter for pre-filling (e.g. from a link in an email).

In both cases the contact record is preserved in Resend — only the `unsubscribed` flag is set to `true`. If they later re-subscribe via the signup page, the flag is cleared and they receive future broadcasts again.

---

## 10. Troubleshooting

| Problem | What to check |
|---|---|
| **Email not received** | Check your spam/junk folder. Confirm you are a contact in the Resend Audience (`RESEND_AUDIENCE_ID`). Verify `RESEND_API_KEY` is set in Lambda environment variables. |
| **`Resend broadcast failed` in CloudWatch** | Check that `RESEND_API_KEY` is valid, `RESEND_AUDIENCE_ID` is correct, and `EMAIL_FROM` is on a verified Resend domain. Open Resend dashboard → Broadcasts to see delivery details. |
| **Email arrives but "From" shows wrong address** | Update `EMAIL_FROM` in `.env` and redeploy with `deploy.bat`, or update it directly in Lambda → Configuration → Environment variables. |
| **Lambda timed out** | Check CloudWatch logs for which stage it was in. Most likely cause: invalid API key preventing Tavily or Claude from responding. Verify `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` are correct. |
| **No report in S3 after Lambda ran** | Open CloudWatch logs for that run and look for `ERROR` lines. Common causes: API keys missing or expired, Tavily quota exceeded. |
| **Agent skipped (no new report)** | Check CloudWatch logs for `already exists in S3. Skipping.` — this is normal. Delete today's S3 file and re-run to force a fresh report. |
| **EventBridge not triggering** | Console → EventBridge → Rules → `ai-news-agent-weekly` → confirm it is **Enabled**. |
| **Report renders with broken layout in email** | Your email client may not support full HTML/CSS. Download the file from S3 and open it in a browser for the full experience. |
