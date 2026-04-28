# Excalidraw Diagrams Plan

Diagrams for the AI News Agent codebase, each as a standalone task.
Output files go in `diagrams/` at the project root.

---

## Task 1: Pipeline Overview

**File:** `diagrams/pipeline-overview.excalidraw`
**Type:** Simple / Conceptual
**Pattern:** Assembly line (left → right transformation)

Create a diagram showing the 4-stage pipeline in `agent.py`:

1. **Search** — Tavily queries in, raw results out
2. **Curate** — Claude Haiku in, structured JSON out
3. **Generate** — JSON in, self-contained HTML out
4. **Email** — HTML in, broadcast sent via Resend

Each stage should use a distinct visual pattern. Show the data artifact that passes between stages (not just arrows). The diagram should answer: "What does this agent actually do?"

---

## Task 2: Search Stage Detail

**File:** `diagrams/search-stage.excalidraw`
**Type:** Technical / Comprehensive
**Pattern:** Fan-out (10 topics → 2 queries each), then convergence (dedup → 5 results per topic)

Show the full mechanics of `search_topic()`:

- 10 topics split into 2 tracks (developer / architect)
- Each topic fans out to 2 Tavily queries: general web + `site:youtube.com`
- 20 total API calls
- Results capped at 5 per topic
- URL deduplication step
- Output: two buckets of results feeding `summarize_section()` (one per section)

Include evidence artifacts: show what a Tavily result object looks like (real fields: `url`, `title`, `content`, `score`).

---

## Task 3: Curate Stage — Claude Haiku Call Structure

**File:** `diagrams/curate-stage.excalidraw`
**Type:** Technical / Comprehensive
**Pattern:** Two parallel assembly lines converging into one merge step

Show the two `summarize_section()` calls:

- **Developer call:** receives 5 topics of search results, returns structured JSON including `concept_of_the_day`
- **Architect call:** receives 5 topics of search results, returns structured JSON with `concept_of_the_day` set to empty
- **Merge step:** both JSON blobs combined before `generate_html()` is called

Include evidence artifacts:
- The JSON schema that Claude Haiku is asked to return (fields: `topics[].name`, `topics[].resources[].text`, `topics[].resources[].url`, `topics[].resources[].rtype`, `topics[].resources[].difficulty`, `concept_of_the_day.title`, `concept_of_the_day.explanation`)
- Model used: `claude-haiku-4-5-20251001`

---

## Task 4: AWS Architecture

**File:** `diagrams/aws-architecture.excalidraw`
**Type:** Technical / Comprehensive
**Pattern:** Top-down flow with labeled section boundaries per service group

Show the full cloud topology defined in `template.yaml`:

- **Trigger:** EventBridge scheduled rule (weekly)
- **Compute:** Lambda (`ai-news-agent`, 300s, 256MB, Python 3.12) + Lambda (`ai-news-agent-signup`, 10s, 128MB)
- **Storage:** `ReportsBucket` (S3, 90-day lifecycle) + `SignupBucket` (S3, no public access)
- **CDN:** CloudFront distribution with OAC → `SignupBucket`
- **Email:** Resend Broadcasts API (HTML report) + Resend Contacts API (signup/unsubscribe)
- **Logging:** CloudWatch log group `/aws/lambda/ai-news-agent`
- **API Gateway:** routes `/subscribe`, `/confirm`, `/unsubscribe` to signup Lambda

Show data flow: EventBridge fires → Lambda runs pipeline → report uploaded to S3 → Resend broadcast sent. Separate path: user visits CloudFront signup page → submits form → API Gateway → signup Lambda → Resend Contacts.

Include the idempotency check: Lambda calls `s3.head_object` before running; exits 0 if report already exists.

---

## Task 5: Newsletter Double Opt-In Flow

**File:** `diagrams/double-optin-flow.excalidraw`
**Type:** Technical / Comprehensive
**Pattern:** Timeline / sequence with decision diamonds at branch points

Show the full user journey through `signup/handler.py`:

**Subscribe path:**
1. User submits email on CloudFront signup page
2. POST to `/subscribe` → `_handle_subscribe()` validates email
3. HMAC-SHA256 token generated (`_make_token`): `ts` + `sig = HMAC(RESEND_API_KEY, "email:ts")`
4. Confirmation email sent via Resend (token embedded in `/confirm?email=...&ts=...&sig=...` URL)
5. User clicks link → GET `/confirm` → `_verify_token()`: checks expiry (24h), `hmac.compare_digest`
6. `_call_resend()` activates contact in Resend Audience

**Unsubscribe path:**
1. User clicks `{{{RESEND_UNSUBSCRIBE_URL}}}` in broadcast footer (Resend expands to per-recipient signed URL)
2. Lands on CloudFront unsubscribe page (email pre-filled from `?email=`)
3. POST to `/unsubscribe` → `_handle_unsubscribe()` → `_call_resend(unsubscribed=True)`

Include evidence artifacts: the HMAC token structure, the CORS origin restriction (`SIGNUP_ALLOWED_ORIGIN`), HTTP response codes (200 / 400 / 502).

---

## Task 6: HTML Report Anatomy

**File:** `diagrams/html-report-anatomy.excalidraw`
**Type:** Simple / Conceptual
**Pattern:** Nested rectangles (UI mockup showing actual layout regions)

Show the structure of the generated HTML email as a visual mockup:

- Header: title + stats line ("Generated DATE · N resources · N developer · N architect") + invite link
- Concept of the Day: gradient card (purple), `cotd_title`, `cotd_explanation`
- Developer section: section header with label/description/count, then resource cards
- Resource card breakdown: `rtype` badge, `difficulty` badge, `name`, `text`, `time_estimate`, `why_learn_this`, URL link
- Architect section: same structure as developer
- Footer: unsubscribe link

Annotate which fields come from Claude Haiku JSON vs. Tavily results vs. env vars. Show the `_safe_url()` and `html.escape()` security boundaries as annotations on the fields they protect.
