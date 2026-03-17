#!/usr/bin/env python3
"""AI Learning Digest Agent - Curates daily learning resources across Developer and Architect tracks."""

import os
import json
import sys
import html
import logging
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TAVILY_API_KEY    = os.getenv("TAVILY_API_KEY")

EMAIL_TO       = os.getenv("EMAIL_TO", "")
EMAIL_FROM     = os.getenv("EMAIL_FROM", "")
SMTP_HOST      = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT      = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER      = os.getenv("SMTP_USER", "")
SMTP_PASSWORD  = os.getenv("SMTP_PASSWORD", "")

# AWS mode — set by template.yaml; absent in local mode
S3_BUCKET  = os.getenv("S3_BUCKET", "")
SES_REGION = os.getenv("SES_REGION", "us-east-1")

REPORTS_DIR = Path(__file__).parent / "reports"
LOG_FILE    = Path(__file__).parent / "agent.log"

# ── Topics ────────────────────────────────────────────────────────────────────
# Each topic belongs to a section: "developer" or "architect"
# Ordered within each section by recommended learning progression.
TOPICS = [
    # ── Developer Track ───────────────────────────────────────────────────────
    {
        "name":    "Generative AI Fundamentals",
        "section": "developer",
        "color":   "#c85c38",
        "queries": [
            "generative AI LLM how it works deep dive tutorial 2025",
            "site:youtube.com generative AI LLM explained how it works tutorial",
        ],
    },
    {
        "name":    "Agentic AI",
        "section": "developer",
        "color":   "#10a37f",
        "queries": [
            "AI agents autonomous tool use memory planning tutorial explained 2025",
            "site:youtube.com AI agents how they work tool use memory tutorial",
        ],
    },
    {
        "name":    "Agentic Coding",
        "section": "developer",
        "color":   "#4285f4",
        "queries": [
            "agentic coding Claude Code Cursor Devin AI developer tools tutorial 2025",
            "site:youtube.com agentic coding AI software development agents tutorial",
        ],
    },
    {
        "name":    "Prompt Engineering",
        "section": "developer",
        "color":   "#7c3aed",
        "queries": [
            "prompt engineering structured output chain-of-thought few-shot tutorial 2025",
            "site:youtube.com prompt engineering intermediate advanced techniques tutorial",
        ],
    },
    {
        "name":    "AI Orchestration & Frameworks",
        "section": "developer",
        "color":   "#0866ff",
        "queries": [
            "LangChain LangGraph CrewAI Anthropic agent SDK tutorial how it works 2025",
            "site:youtube.com LangGraph CrewAI AI orchestration multi-agent framework tutorial",
        ],
    },
    # ── Architect Track ───────────────────────────────────────────────────────
    {
        "name":    "AI System Design",
        "section": "architect",
        "color":   "#d97706",
        "queries": [
            "AI system design scalable LLM architecture patterns tutorial 2025",
            "site:youtube.com AI system design architecture LLM production scalable",
        ],
    },
    {
        "name":    "RAG Architecture",
        "section": "architect",
        "color":   "#059669",
        "queries": [
            "RAG retrieval augmented generation architecture vector database design 2025",
            "site:youtube.com RAG architecture retrieval augmented generation tutorial deep dive",
        ],
    },
    {
        "name":    "Multi-Agent System Design",
        "section": "architect",
        "color":   "#0891b2",
        "queries": [
            "multi-agent system design patterns orchestration architecture 2025",
            "site:youtube.com multi-agent architecture design patterns AI systems tutorial",
        ],
    },
    {
        "name":    "LLMOps & AI in Production",
        "section": "architect",
        "color":   "#dc2626",
        "queries": [
            "LLMOps AI production deployment monitoring observability cost optimization 2025",
            "site:youtube.com LLMOps AI production MLOps best practices tutorial",
        ],
    },
    {
        "name":    "AI Security & Guardrails",
        "section": "architect",
        "color":   "#7c3aed",
        "queries": [
            "AI security prompt injection guardrails enterprise trust boundaries architecture 2025",
            "site:youtube.com AI security LLM guardrails prompt injection enterprise tutorial",
        ],
    },
]

TOPIC_COLORS   = {t["name"]: t["color"]   for t in TOPICS}
TOPIC_SECTIONS = {t["name"]: t["section"] for t in TOPICS}

_handlers: list = [logging.StreamHandler(sys.stdout)]
if not S3_BUCKET:
    # Local mode only — Lambda captures stdout to CloudWatch automatically
    _handlers.append(logging.FileHandler(LOG_FILE, encoding="utf-8"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=_handlers,
    force=True,  # Override Lambda's pre-configured root logger
)
log = logging.getLogger(__name__)


# ── Search ────────────────────────────────────────────────────────────────────

def search_topic(tavily, topic: dict) -> list:
    """Run all queries for a topic (web + YouTube) and return merged, deduplicated results."""
    seen_urls   = set()
    all_results = []

    for query in topic["queries"]:
        try:
            resp = tavily.search(
                query=query,
                topic="general",
                days=7,
                search_depth="basic",
                max_results=5,
            )
            for r in resp.get("results", []):
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
        except Exception as e:
            log.warning("  %s | query '%s...' failed: %s", topic["name"], query[:40], e)

    all_results = all_results[:5]
    log.info("  %s -> %d results", topic["name"], len(all_results))
    return all_results


# ── Summarise ─────────────────────────────────────────────────────────────────

def summarize_section(client, all_results: dict, topic_names: list,
                      audience: str, include_cotd: bool) -> dict:
    """One Claude Haiku call for a single section (developer or architect)."""
    lines = []
    for name in topic_names:
        results = all_results.get(name, [])
        lines.append(f"\n### {name}")
        if not results:
            lines.append("  (no results found)")
        for r in results:
            content = (r.get("content") or "")[:300].replace("\n", " ")
            lines.append(f"  - TITLE: {r.get('title', '')}")
            lines.append(f"    URL:   {r.get('url', '')}")
            lines.append(f"    BODY:  {content}")

    search_text = "\n".join(lines)

    cotd_instruction = (
        '- Produce a "concept_of_the_day": pick ONE important concept from the search results '
        "that best represents the most interesting or emerging idea this week. "
        "Vary the topic — do NOT default to the same concept every time (e.g. avoid always picking the ReAct loop). "
        "Explain it in exactly 3 plain-English sentences a developer or architect new to AI can understand.\n"
        if include_cotd else
        '- Set "concept_of_the_day" to {"title": "", "explanation": ""}.\n'
    )

    prompt = f"""You are an expert AI learning curator for {audience}.

Rules:
- For each topic below, select 2-4 of the best learning resources.
- Detect whether each resource is a VIDEO (url contains youtube.com or youtu.be) or an ARTICLE/TUTORIAL.
- For each resource provide:
  - text: one sentence describing what the reader/viewer will learn
  - url: exact URL from the search results — NEVER invent URLs
  - type: "video" or "article"
  - difficulty: "beginner", "intermediate", or "advanced"
  - time_estimate: estimated watch/read time e.g. "12 min", "8 min read"
  - why_learn_this: one sentence on why this is valuable right now
{cotd_instruction}- Prioritise depth and educational value over recency.
- If a topic has no suitable resources, return an empty resources list for it.

Return ONLY valid JSON — no markdown, no extra text:
{{
  "concept_of_the_day": {{
    "title": "Concept name",
    "explanation": "Sentence one. Sentence two. Sentence three."
  }},
  "topics": [
    {{
      "name": "Topic Name",
      "resources": [
        {{
          "text": "What you will learn.",
          "url": "https://...",
          "type": "article",
          "difficulty": "intermediate",
          "time_estimate": "10 min read",
          "why_learn_this": "Why this matters right now."
        }}
      ]
    }}
  ]
}}

Search results:
{search_text}
"""

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


# ── HTML report ───────────────────────────────────────────────────────────────

TYPE_ICONS = {"video": "▶", "article": "📄"}

SECTION_META = {
    "developer": {
        "label":       "Developer Track",
        "description": "Hands-on tutorials, code examples, and implementation guides.",
        "accent":      "#1d4ed8",
        "bg":          "#eff6ff",
        "dark_bg":     "#172554",
        "dark_accent": "#93c5fd",
        "icon":        "⌨",
    },
    "architect": {
        "label":       "Architect Track",
        "description": "System design patterns, trade-offs, production concerns, and decision frameworks.",
        "accent":      "#b45309",
        "bg":          "#fffbeb",
        "dark_bg":     "#292017",
        "dark_accent": "#fcd34d",
        "icon":        "🏛",
    },
}


def _safe_url(url: str) -> str:
    """Return url if http/https, else '#'. Escapes for use in an HTML attribute."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "#"
    return html.escape(url, quote=True)


def build_cards(topics_data: list, section: str) -> tuple[str, int]:
    """Return (cards_html, resource_count) for all topics in the given section."""
    cards = ""
    total = 0

    for topic in topics_data:
        name = topic.get("name", "Unknown")
        if TOPIC_SECTIONS.get(name) != section:
            continue

        color     = TOPIC_COLORS.get(name, "#555")
        resources = topic.get("resources", [])
        if not resources:
            continue

        total += len(resources)
        items_html = ""

        for r in resources:
            rtype      = r.get("type", "article").lower()
            difficulty = r.get("difficulty", "intermediate").lower()
            # Allowlist to known CSS class names — prevents class injection
            if rtype not in ("video", "article"):
                rtype = "article"
            if difficulty not in ("beginner", "intermediate", "advanced"):
                difficulty = "intermediate"

            url      = _safe_url(r.get("url", ""))
            text     = html.escape(r.get("text", ""))
            time_est = html.escape(r.get("time_estimate", ""))
            why      = html.escape(r.get("why_learn_this", ""))

            icon       = TYPE_ICONS.get(rtype, "📄")
            time_badge = f'<span class="time-est">⏱ {time_est}</span>' if time_est else ""

            items_html += f"""
            <div class="resource">
              <div class="resource-meta">
                <span class="badge type-{rtype}">{icon} {rtype.capitalize()}</span>
                <span class="badge diff-{difficulty}">{difficulty.capitalize()}</span>
                {time_badge}
              </div>
              <div class="resource-text">
                <a href="{url}" target="_blank" rel="noopener noreferrer">{text}</a>
              </div>
              <div class="resource-why">{why}</div>
            </div>"""

        cards += f"""
        <div class="card" style="border-left:4px solid {color}">
          <div class="card-header">
            <h3 style="color:{color}">{html.escape(name)}</h3>
            <span class="resource-count">{len(resources)} resource{"s" if len(resources) != 1 else ""}</span>
          </div>
          {items_html}
        </div>"""

    return cards, total


def generate_html(summary: dict, date_str: str) -> str:
    cotd             = summary.get("concept_of_the_day", {})
    cotd_title       = html.escape(cotd.get("title", ""))
    cotd_explanation = html.escape(cotd.get("explanation", ""))
    topics_data      = summary.get("topics", [])

    dev_cards,  dev_count  = build_cards(topics_data, "developer")
    arch_cards, arch_count = build_cards(topics_data, "architect")
    total_resources        = dev_count + arch_count

    def section_html(section_key: str, cards: str, count: int) -> str:
        m = SECTION_META[section_key]
        if not cards:
            return ""
        return f"""
    <div class="section-header section-{section_key}">
      <div class="section-icon">{m["icon"]}</div>
      <div>
        <div class="section-label">{m["label"]}</div>
        <div class="section-desc">{m["description"]}</div>
      </div>
      <span class="section-count">{count} resources</span>
    </div>
    {cards}"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AI Learning Digest · {date_str}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f0f2f5;
      color: #222;
      padding: 2rem 1rem;
    }}
    .wrapper  {{ max-width: 900px; margin: 0 auto; }}
    header    {{ margin-bottom: 1.5rem; }}
    header h1 {{ font-size: 1.8rem; color: #111; }}
    header p  {{ color: #666; margin-top: .25rem; font-size: .9rem; }}

    /* Concept of the Day */
    .cotd {{
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: #fff;
      border-radius: 10px;
      padding: 1.4rem 1.6rem;
      margin-bottom: 2rem;
    }}
    .cotd-label {{
      font-size: .68rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: .1em; opacity: .75; margin-bottom: .4rem;
    }}
    .cotd h2 {{ font-size: 1.1rem; margin-bottom: .55rem; }}
    .cotd p  {{ font-size: .91rem; line-height: 1.7; opacity: .93; }}

    /* Section headers */
    .section-header {{
      display: flex; align-items: center; gap: 1rem;
      border-radius: 10px; padding: 1rem 1.4rem;
      margin-bottom: 1rem; margin-top: .5rem;
    }}
    .section-developer {{
      background: #eff6ff; border: 1px solid #bfdbfe;
    }}
    .section-architect {{
      background: #fffbeb; border: 1px solid #fde68a;
      margin-top: 2rem;
    }}
    .section-icon {{
      font-size: 1.6rem; line-height: 1; flex-shrink: 0;
    }}
    .section-label {{
      font-size: 1rem; font-weight: 700; color: #111;
    }}
    .section-developer .section-label {{ color: #1d4ed8; }}
    .section-architect .section-label {{ color: #b45309; }}
    .section-desc {{
      font-size: .8rem; color: #666; margin-top: .15rem;
    }}
    .section-count {{
      margin-left: auto; font-size: .75rem;
      color: #999; white-space: nowrap; flex-shrink: 0;
    }}

    /* Cards */
    .card {{
      background: #fff;
      border-radius: 8px;
      padding: 1.4rem 1.6rem;
      margin-bottom: 1rem;
      box-shadow: 0 1px 4px rgba(0,0,0,.08);
    }}
    .card-header {{
      display: flex; justify-content: space-between;
      align-items: center; margin-bottom: .9rem;
    }}
    .card-header h3  {{ font-size: 1rem; font-weight: 700; }}
    .resource-count  {{ font-size: .75rem; color: #aaa; }}

    /* Resources */
    .resource {{ padding: .8rem 0; border-top: 1px solid #f0f0f0; }}
    .resource:first-of-type {{ border-top: none; padding-top: 0; }}
    .resource-meta {{
      display: flex; align-items: center; gap: .4rem;
      margin-bottom: .4rem; flex-wrap: wrap;
    }}
    .resource-text {{ margin-bottom: .3rem; }}
    .resource-text a {{
      color: #1a73e8; text-decoration: none;
      font-size: .93rem; font-weight: 500; line-height: 1.5;
    }}
    .resource-text a:hover {{ text-decoration: underline; }}
    .resource-why {{ font-size: .8rem; color: #777; font-style: italic; line-height: 1.45; }}

    /* Badges */
    .badge {{
      font-size: .67rem; font-weight: 700; padding: .2rem .45rem;
      border-radius: 4px; text-transform: uppercase; letter-spacing: .05em;
    }}
    .type-video        {{ background: #fff0f0; color: #c0392b; }}
    .type-article      {{ background: #f0f4ff; color: #2c5282; }}
    .diff-beginner     {{ background: #d1fae5; color: #065f46; }}
    .diff-intermediate {{ background: #fef3c7; color: #92400e; }}
    .diff-advanced     {{ background: #fee2e2; color: #991b1b; }}
    .time-est          {{ font-size: .75rem; color: #bbb; }}

    footer {{ text-align: center; color: #aaa; font-size: .78rem; margin-top: 2rem; }}

    /* Dark mode */
    @media (prefers-color-scheme: dark) {{
      body      {{ background: #18191a; color: #e4e6eb; }}
      header h1 {{ color: #e4e6eb; }}
      header p  {{ color: #aaa; }}
      .card     {{ background: #242526; box-shadow: none; }}
      .resource {{ border-top-color: #3a3b3c; }}
      .resource-text a  {{ color: #6aabff; }}
      .resource-why     {{ color: #999; }}
      .section-developer {{
        background: #172554; border-color: #1e3a8a;
      }}
      .section-architect {{
        background: #292017; border-color: #92400e;
      }}
      .section-developer .section-label {{ color: #93c5fd; }}
      .section-architect .section-label {{ color: #fcd34d; }}
      .section-desc  {{ color: #999; }}
      .section-count {{ color: #666; }}
      .card-header h3    {{ color: inherit; }}
      .type-video        {{ background: #3d1212; color: #ff8080; }}
      .type-article      {{ background: #12213d; color: #90b8ff; }}
      .diff-beginner     {{ background: #052e16; color: #6ee7b7; }}
      .diff-intermediate {{ background: #2d1b00; color: #fcd34d; }}
      .diff-advanced     {{ background: #2d0a0a; color: #fca5a5; }}
      .time-est          {{ color: #555; }}
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <header>
      <h1>AI Learning Digest</h1>
      <p>Generated {date_str} &nbsp;·&nbsp; {total_resources} resources &nbsp;·&nbsp; {dev_count} developer &nbsp;·&nbsp; {arch_count} architect</p>
    </header>

    <div class="cotd" style="background:#667eea;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;border-radius:10px;padding:1.4rem 1.6rem;margin-bottom:2rem;">
      <div class="cotd-label" style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;opacity:.75;margin-bottom:.4rem;">Concept of the Day</div>
      <h2 style="font-size:1.1rem;margin-bottom:.55rem;color:#fff;">{cotd_title}</h2>
      <p style="font-size:.91rem;line-height:1.7;opacity:.93;color:#fff;">{cotd_explanation}</p>
    </div>

    {section_html("developer", dev_cards, dev_count)}
    {section_html("architect", arch_cards, arch_count)}

    <footer>Generated by AI Learning Agent</footer>
  </div>
</body>
</html>"""


# ── Email delivery ────────────────────────────────────────────────────────────

def send_email(report_path: Path, date_str: str) -> None:
    """Send the HTML report as an email. Logs a warning and returns if config is missing."""
    import smtplib
    from email.message import EmailMessage

    if not all([EMAIL_TO, EMAIL_FROM, SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        log.warning("Email config incomplete — skipping email. Set EMAIL_* vars in .env to enable.")
        return

    html_content = report_path.read_text(encoding="utf-8")

    msg = EmailMessage()
    msg["Subject"] = f"AI Learning Digest · {date_str}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.set_content("Open this email in an HTML-capable client to view the digest.")
    msg.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        log.info("Report emailed to %s", EMAIL_TO)
    except Exception as e:
        log.error("Failed to send email: %s", e)


def aws_send_email(html_content: str, date_str: str) -> None:
    """Send the HTML report via Amazon SES. Skipped silently if EMAIL_TO or EMAIL_FROM is not set."""
    import boto3
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if not all([EMAIL_TO, EMAIL_FROM]):
        log.warning("EMAIL_TO or EMAIL_FROM not set — skipping SES email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI Learning Digest · {date_str}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText("Open this email in an HTML-capable client to view the digest.", "plain"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    ses = boto3.client("ses", region_name=SES_REGION)
    try:
        ses.send_raw_email(
            Source=EMAIL_FROM,
            Destinations=[EMAIL_TO],
            RawMessage={"Data": msg.as_bytes()},
        )
        log.info("Report emailed via SES to %s", EMAIL_TO)
    except Exception as e:
        log.error("SES send failed: %s", e)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    try:
        from tavily import TavilyClient
        import anthropic
    except ImportError:
        log.error("Dependencies missing. Run setup.bat first.")
        sys.exit(1)

    if not ANTHROPIC_API_KEY or not TAVILY_API_KEY:
        log.error("Missing API keys in .env file.")
        sys.exit(1)

    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    date_str    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / f"{date_str}-ai-learning.html"
    s3_key      = f"{date_str}-ai-learning.html"

    if S3_BUCKET:
        import boto3
        from botocore.exceptions import ClientError
        s3 = boto3.client("s3")
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
            log.info("Report for %s already exists in S3. Skipping.", date_str)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "404":
                raise
    else:
        if report_path.exists():
            log.info("Report for %s already exists. Skipping.", date_str)
            sys.exit(0)

    log.info("Starting AI learning digest for %s", date_str)

    # 20 Tavily searches (2 queries × 10 topics) + 2 Claude Haiku calls (1 per section)
    all_results = {}
    for topic in TOPICS:
        all_results[topic["name"]] = search_topic(tavily, topic)

    dev_names  = [t["name"] for t in TOPICS if t["section"] == "developer"]
    arch_names = [t["name"] for t in TOPICS if t["section"] == "architect"]

    # Two separate Haiku calls — one per section — to stay within token limits
    log.info("Curating Developer Track with Claude Haiku...")
    dev_summary = summarize_section(
        claude, all_results, dev_names,
        audience="software developers who want hands-on tutorials and implementation guides",
        include_cotd=True,
    )

    log.info("Curating Architect Track with Claude Haiku...")
    arch_summary = summarize_section(
        claude, all_results, arch_names,
        audience="solution architects who want system design patterns, trade-offs, and production concerns",
        include_cotd=False,
    )

    # Merge into a single summary structure for the HTML generator
    summary = {
        "concept_of_the_day": dev_summary.get("concept_of_the_day", {}),
        "topics": dev_summary.get("topics", []) + arch_summary.get("topics", []),
    }

    html = generate_html(summary, date_str)

    if S3_BUCKET:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=html.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
        log.info("Report uploaded to s3://%s/%s", S3_BUCKET, s3_key)
        aws_send_email(html, date_str)
    else:
        REPORTS_DIR.mkdir(exist_ok=True)
        report_path.write_text(html, encoding="utf-8")
        log.info("Report saved: %s", report_path)
        send_email(report_path, date_str)


if __name__ == "__main__":
    main()


def lambda_handler(event, context):
    """AWS Lambda entry point. EventBridge passes a scheduled event; we ignore its payload."""
    main()
