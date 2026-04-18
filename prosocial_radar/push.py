"""
Email push module.

Supports two backends, tried in order:
  1. capymail  — HappyCapy environment (send_email.sh script)
  2. SMTP      — Gmail App Password (GMAIL_ADDRESS + GMAIL_APP_PASSWORD env vars)
                 Used automatically in GitHub Actions or any plain environment.
"""

import logging
import os
import smtplib
import subprocess
import tempfile
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List

log = logging.getLogger(__name__)

RECIPIENTS = [
    "planetbin2012@gmail.com",
    "duo12.li@connect.polyu.hk",
]

# ─── Method badge colours ─────────────────────────────────────────────────────
METHOD_COLORS = {
    "fmri":          "#6366f1",
    "eeg":           "#0ea5e9",
    "behavioral":    "#10b981",
    "computational": "#f59e0b",
    "review":        "#8b5cf6",
    "mixed":         "#ec4899",
    "other":         "#6b7280",
}

TAG_COLORS = {
    "altruism":        "#d97706",
    "empathy":         "#7c3aed",
    "cooperation":     "#059669",
    "economic_games":  "#dc2626",
    "development":     "#2563eb",
    "neuroscience":    "#0891b2",
    "decision_making": "#ea580c",
    "moral":           "#65a30d",
}


def _badge(text: str, color: str, bg_alpha: str = "18") -> str:
    return (
        f'<span style="display:inline-block;padding:2px 8px;margin:2px 2px 2px 0;'
        f'border-radius:4px;font-size:11px;font-weight:600;letter-spacing:.3px;'
        f'color:{color};background:{color}{bg_alpha};">{text.upper()}</span>'
    )


def _method_badge(method: str) -> str:
    color = METHOD_COLORS.get((method or "other").lower(), METHOD_COLORS["other"])
    return _badge(method or "other", color)


def _tag_badges(tags_str: str) -> str:
    tags = [t.strip() for t in (tags_str or "").split(";") if t.strip()]
    return "".join(
        _badge(t.replace("_", " "), TAG_COLORS.get(t, "#6b7280"))
        for t in tags
    )


def _paper_card(rank: int, p: Dict) -> str:
    title      = p.get("title", "")
    journal    = p.get("journal", "")
    year       = p.get("year", "")
    citations  = p.get("citation_count")
    score      = p.get("relevance_score", "")
    tags       = p.get("topic_tags", "")
    ai_summary = p.get("ai_summary", "")
    ai_finding = p.get("ai_finding", "")
    ai_method  = p.get("ai_method", "")

    cite_str  = f"{citations:,}" if citations and citations > 0 else "—"
    score_str = f"{score:.0f}" if isinstance(score, (int, float)) else "—"

    link      = p.get("doi_url") or p.get("url", "")
    link_html = (
        f'<a href="{link}" style="color:#6366f1;text-decoration:none;font-weight:600;">'
        f'Read paper &#8594;</a>'
    ) if link else ""

    ai_block = ""
    if ai_summary or ai_finding:
        summary_p = (
            f'<p style="margin:0 0 4px;font-size:13px;color:#334155;">{ai_summary}</p>'
            if ai_summary else ""
        )
        finding_p = (
            f'<p style="margin:0;font-size:12px;color:#64748b;font-style:italic;">'
            f'Finding: {ai_finding}</p>'
            if ai_finding else ""
        )
        ai_block = (
            f'<div style="margin:10px 0 0;padding:10px 12px;background:#f8fafc;'
            f'border-left:3px solid #6366f1;border-radius:0 6px 6px 0;">'
            f'{summary_p}{finding_p}</div>'
        )

    method_html = _method_badge(ai_method) if ai_method else ""

    return (
        f'<div style="margin:0 0 20px;padding:18px 20px;background:#fff;'
        f'border:1px solid #e2e8f0;border-radius:10px;'
        f'box-shadow:0 1px 3px rgba(0,0,0,.06);">'
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:flex-start;margin-bottom:8px;">'
        f'<span style="font-size:11px;font-weight:700;color:#94a3b8;">#{rank}</span>'
        f'<span style="font-size:11px;color:#94a3b8;">'
        f'Score: <strong style="color:#6366f1;">{score_str}</strong>'
        f'&nbsp;|&nbsp;Citations: <strong>{cite_str}</strong></span></div>'
        f'<h3 style="margin:0 0 6px;font-size:15px;line-height:1.4;color:#0f172a;">{title}</h3>'
        f'<p style="margin:0 0 8px;font-size:12px;color:#64748b;">{journal} &nbsp;·&nbsp; {year}</p>'
        f'<div style="margin-bottom:8px;">{method_html}{_tag_badges(tags)}</div>'
        f'{ai_block}'
        f'<div style="margin-top:12px;">{link_html}</div>'
        f'</div>'
    )


def render_email(papers: List[Dict], total_found: int) -> str:
    today      = date.today().strftime("%B %d, %Y")
    cards_html = "".join(_paper_card(i + 1, p) for i, p in enumerate(papers))

    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        '<title>Prosocial Research Radar</title></head>'
        '<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,'
        'BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;">'
        '<div style="max-width:640px;margin:32px auto;padding:0 16px 40px;">'

        # Header
        '<div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);'
        'border-radius:12px;padding:28px 28px 24px;margin-bottom:24px;color:#fff;">'
        f'<p style="margin:0 0 4px;font-size:12px;letter-spacing:1.5px;'
        f'text-transform:uppercase;opacity:.8;">Daily Digest &middot; {today}</p>'
        '<h1 style="margin:0 0 8px;font-size:22px;font-weight:700;">Prosocial Research Radar</h1>'
        f'<p style="margin:0;font-size:14px;opacity:.85;">'
        f'{len(papers)} new papers selected from {total_found} retrieved today</p>'
        '</div>'

        # Paper cards
        + cards_html +

        # Footer
        '<div style="margin-top:28px;padding:16px 20px;background:#e2e8f0;'
        'border-radius:8px;text-align:center;">'
        '<p style="margin:0;font-size:12px;color:#64748b;">'
        'Generated by Prosocial Research Radar &nbsp;&middot;&nbsp;'
        'Sources: PubMed + OpenAlex &nbsp;&middot;&nbsp;'
        'AI summaries by Claude Haiku</p></div>'
        '</div></body></html>'
    )


# ─── Backend 1: capymail (HappyCapy environment) ─────────────────────────────

def _send_capymail(subject: str, html: str) -> bool:
    script = "/home/node/.claude/skills/capymail/scripts/send_email.sh"
    if not os.path.exists(script):
        return False
    # Send to each recipient individually (capymail CLI takes one --to at a time)
    ok = True
    for recipient in RECIPIENTS:
        cmd = ["bash", script, "--to", recipient, "--subject", subject, "--html", html]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                log.info("capymail: sent OK → %s", recipient)
            else:
                log.warning("capymail rc=%d → %s: %s",
                            r.returncode, recipient, (r.stderr or r.stdout)[:150])
                ok = False
        except Exception as exc:
            log.warning("capymail exception → %s: %s", recipient, exc)
            ok = False
    return ok


# ─── Backend 2: SMTP / Gmail App Password ────────────────────────────────────

def _send_smtp(subject: str, html: str) -> bool:
    sender   = os.environ.get("GMAIL_ADDRESS", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

    if not sender or not password:
        log.warning("SMTP backend: GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = ", ".join(RECIPIENTS)   # display all recipients in header
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, RECIPIENTS, msg.as_bytes())
        log.info("SMTP: sent OK → %s", ", ".join(RECIPIENTS))
        return True
    except smtplib.SMTPAuthenticationError:
        log.error("SMTP auth failed — check GMAIL_ADDRESS and GMAIL_APP_PASSWORD.")
        return False
    except Exception as exc:
        log.error("SMTP send failed — %s", exc)
        return False


# ─── Public interface ─────────────────────────────────────────────────────────

def send_email(papers: List[Dict], total_found: int) -> bool:
    """
    Send the digest email. Tries capymail first, then falls back to SMTP.
    Returns True on success.
    """
    if not papers:
        log.info("No new papers — skipping email.")
        return False

    today   = date.today().strftime("%Y-%m-%d")
    subject = f"Prosocial Research Radar — {today} | {len(papers)} new papers"
    html    = render_email(papers, total_found)

    log.info("Sending digest to [%s] (%d papers) ...",
             ", ".join(RECIPIENTS), len(papers))

    if _send_capymail(subject, html):
        return True

    log.info("capymail unavailable — trying SMTP backend.")
    return _send_smtp(subject, html)
