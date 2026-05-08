"""
Email push module.

Supports two backends, tried in order:
  1. capymail - HappyCapy environment
  2. SMTP - Gmail App Password
"""

import html
import logging
import os
import smtplib
import subprocess
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Iterable, List

from . import config

log = logging.getLogger(__name__)

RECIPIENTS = config.EMAIL_RECIPIENTS

METHOD_COLORS = {
    "fmri": "#6366f1",
    "eeg": "#0ea5e9",
    "behavioral": "#10b981",
    "computational": "#f59e0b",
    "review": "#8b5cf6",
    "mixed": "#ec4899",
    "other": "#6b7280",
}

TAG_COLORS = {
    "altruism": "#d97706",
    "empathy": "#7c3aed",
    "cooperation": "#059669",
    "economic_games": "#dc2626",
    "development": "#2563eb",
    "neuroscience": "#0891b2",
    "decision_making": "#ea580c",
    "moral": "#65a30d",
}

RESEARCH_TAG_COLORS = {
    "aging_prosociality": "#0f766e",
    "age_comparison": "#0d9488",
    "helping_decision": "#2563eb",
    "sharing": "#16a34a",
    "comforting": "#db2777",
    "cost_mechanism": "#ea580c",
    "familiarity_mechanism": "#7c3aed",
    "ses_resource_mechanism": "#a16207",
    "value_based_decision": "#dc2626",
    "attentional_mechanism": "#0891b2",
    "neural_mechanism": "#4f46e5",
    "measurement_validation": "#475569",
    "picture_vignette_method": "#64748b",
    "psychometrics": "#334155",
    "meta_analysis": "#9333ea",
    "computational_modeling_bridge": "#f59e0b",
    "psychology_priority": "#0369a1",
}

SECTION_INFO = {
    "top": ("Today's must-read", "Highest-ranked papers after topic relevance and profile-fit reranking."),
    "aging_lifespan": ("Aging and lifespan prosociality", "Older-adult, age-comparison, and lifespan papers closest to the core research line."),
    "neural_attention": ("Neural and attentional mechanisms", "Brain, gaze, attention, and perception-to-helping decision leads."),
    "measurement_methods": ("Measurement and methods", "Scale, picture/vignette, psychometric, review, and meta-analysis material."),
    "computational_modeling": ("Computational modeling", "Model-based, utility, reinforcement-learning, and value-decision bridges."),
    "mechanism_leads": ("Mechanism leads", "Cost, familiarity, SES/resources, and value-based decision explanations."),
    "general_prosocial": ("General prosocial behavior", "Relevant but less specifically aligned papers."),
    "peripheral_watch": ("Peripheral watch", "Applied or policy-facing papers to keep only if strategically useful."),
}

SECTION_ORDER = [
    "aging_lifespan",
    "neural_attention",
    "measurement_methods",
    "computational_modeling",
    "mechanism_leads",
    "general_prosocial",
    "peripheral_watch",
]

FEEDBACK_BUTTONS = [
    ("must_read", "Must read", "#166534", "#dcfce7"),
    ("useful", "Useful", "#1d4ed8", "#dbeafe"),
    ("maybe", "Maybe", "#92400e", "#fef3c7"),
    ("ignore", "Ignore", "#991b1b", "#fee2e2"),
]

FEEDBACK_LABELS = {
    "must_read": "Must read",
    "useful": "Useful",
    "maybe": "Maybe",
    "ignore": "Ignore",
}


def _badge(text: str, color: str, bg_alpha: str = "18") -> str:
    safe_text = html.escape(text or "other")
    return (
        f'<span style="display:inline-block;padding:2px 8px;margin:2px 2px 2px 0;'
        f'border-radius:4px;font-size:11px;font-weight:600;letter-spacing:.3px;'
        f'color:{color};background:{color}{bg_alpha};">{safe_text.upper()}</span>'
    )


def _method_badge(method: str) -> str:
    key = (method or "other").lower()
    color = METHOD_COLORS.get(key, METHOD_COLORS["other"])
    return _badge(method or "other", color)


def _split_values(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def _tag_badges(tags_str: str) -> str:
    tags = _split_values(tags_str)
    return "".join(
        _badge(t.replace("_", " "), TAG_COLORS.get(t, "#6b7280"))
        for t in tags
    )


def _research_tag_badges(tags_str: str) -> str:
    tags = _split_values(tags_str)
    return "".join(
        _badge(t.replace("_", " "), RESEARCH_TAG_COLORS.get(t, "#475569"), "20")
        for t in tags
    )


def _detail(label: str, value: str) -> str:
    if not value:
        return ""
    return (
        '<p style="margin:4px 0;font-size:12px;line-height:1.45;color:#475569;">'
        f'<strong style="color:#0f172a;">{html.escape(label)}:</strong> '
        f'{html.escape(str(value))}</p>'
    )


def _shorten(value: str, limit: int = 260) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + "..."


def _compact_values(values: Iterable[str], limit: int = 4) -> str:
    seen: List[str] = []
    for value in values:
        for item in _split_values(value):
            if item and item not in seen:
                seen.append(item)
    if not seen:
        return ""
    shown = seen[:limit]
    suffix = f" +{len(seen) - limit} more" if len(seen) > limit else ""
    return "; ".join(shown) + suffix


def _score_line(p: Dict) -> str:
    score = p.get("relevance_score")
    topic = p.get("score_topic")
    recency = p.get("score_recency")
    citations = p.get("score_citation")
    research = p.get("score_research_alignment")
    penalty = p.get("score_penalty")

    def fmt(value: object, signed: bool = False) -> str:
        if isinstance(value, (int, float)):
            return f"{value:+.1f}" if signed else f"{value:.1f}"
        return "-"

    return (
        f"score {fmt(score)} | topic {fmt(topic)}/55 | recency {fmt(recency)}/18 | "
        f"citations {fmt(citations)}/12 | research fit {fmt(research, signed=True)} | penalty -{fmt(penalty)}"
    )


def _why_row(label: str, value: str) -> str:
    if not value:
        return ""
    return (
        '<tr>'
        f'<td style="width:88px;padding:3px 8px 3px 0;vertical-align:top;font-size:12px;color:#64748b;font-weight:700;">{html.escape(label)}</td>'
        f'<td style="padding:3px 0;vertical-align:top;font-size:12px;line-height:1.45;color:#334155;">{html.escape(value)}</td>'
        '</tr>'
    )


def _why_selected_block(p: Dict) -> str:
    core = _compact_values([
        p.get("matched_title_anchor_terms", ""),
        p.get("matched_core_terms", ""),
    ], limit=4)
    mechanism = _compact_values([
        p.get("matched_paradigm_terms", ""),
        p.get("matched_mechanism_terms", ""),
    ], limit=4)
    context = _compact_values([p.get("matched_context_terms", "")], limit=3)
    research_tags = _compact_values([p.get("research_use_tags", "")], limit=4)
    takeaway = _shorten(p.get("research_takeaway", ""), 210)

    cautions = []
    if p.get("matched_soft_exclude_terms"):
        cautions.append("soft caution: " + _compact_values([p.get("matched_soft_exclude_terms", "")], limit=3))
    if p.get("matched_hard_exclude_terms"):
        cautions.append("hard caution: " + _compact_values([p.get("matched_hard_exclude_terms", "")], limit=3))
    penalty = p.get("research_alignment_penalty")
    if isinstance(penalty, (int, float)) and penalty > 0:
        cautions.append(f"profile penalty -{penalty:.1f}")
    if p.get("email_section") == "peripheral_watch":
        cautions.append("peripheral watch")
    caution = "; ".join(c for c in cautions if c)

    rows = "".join([
        _why_row("Core", core or str(p.get("topic_tier") or "")),
        _why_row("Mechanism", mechanism),
        _why_row("Context", context),
        _why_row("Profile", research_tags),
        _why_row("Worth seeing", takeaway),
        _why_row("Caution", caution),
        _why_row("Score", _score_line(p)),
    ])
    if not rows:
        return ""

    full_trace = _shorten(p.get("selection_reason") or p.get("filter_reason", ""), 900)
    trace_html = ""
    if full_trace:
        trace_html = (
            '<details style="margin-top:8px;">'
            '<summary style="font-size:11px;color:#64748b;cursor:pointer;font-weight:700;">Full selection trace</summary>'
            f'<p style="margin:6px 0 0;font-size:11px;line-height:1.45;color:#64748b;">{html.escape(full_trace)}</p>'
            '</details>'
        )

    return (
        '<div style="margin:10px 0 0;padding:10px 12px;background:#fefce8;'
        'border-left:3px solid #ca8a04;border-radius:0 6px 6px 0;">'
        '<p style="margin:0 0 6px;font-size:12px;color:#854d0e;font-weight:800;">Why selected</p>'
        f'<table role="presentation" style="width:100%;border-collapse:collapse;">{rows}</table>'
        f'{trace_html}'
        '</div>'
    )


def _feedback_buttons(p: Dict) -> str:
    links = p.get("feedback_links") or {}
    buttons = []
    for rating, label, color, background in FEEDBACK_BUTTONS:
        url = links.get(rating) or p.get(f"feedback_{rating}_url")
        if not url:
            continue
        buttons.append(
            f'<a href="{html.escape(url, quote=True)}" '
            f'style="display:inline-block;margin:4px 6px 0 0;padding:6px 9px;'
            f'border-radius:5px;background:{background};color:{color};font-size:12px;'
            f'font-weight:700;text-decoration:none;">{html.escape(label)}</a>'
        )
    if not buttons:
        return ""
    return (
        '<div style="margin-top:12px;padding-top:10px;border-top:1px solid #e2e8f0;">'
        '<span style="font-size:12px;color:#64748b;font-weight:700;margin-right:4px;">Feedback:</span>'
        + "".join(buttons)
        + '</div>'
    )


def _paper_card(rank: int, p: Dict) -> str:
    title = html.escape(p.get("title", ""))
    journal = html.escape(p.get("journal", ""))
    year = html.escape(str(p.get("year", "")))
    citations = p.get("citation_count")
    score = p.get("relevance_score", "")
    tags = p.get("topic_tags", "")
    research_tags = p.get("research_use_tags", "")
    research_fit = p.get("research_alignment_score")
    ai_summary = p.get("ai_summary", "")
    ai_finding = p.get("ai_finding", "")
    ai_method = p.get("ai_method", "")
    authors = p.get("authors", "")
    institution = _shorten(p.get("first_author_affiliation") or p.get("affiliations") or "")

    cite_str = f"{citations:,}" if citations and citations > 0 else "-"
    score_str = f"{score:.0f}" if isinstance(score, (int, float)) else "-"
    fit_str = f"{research_fit:.0f}" if isinstance(research_fit, (int, float)) else "-"

    link = p.get("doi_url") or p.get("url", "")
    link_html = (
        f'<a href="{html.escape(link, quote=True)}" style="color:#2563eb;text-decoration:none;font-weight:600;">'
        f'Read paper &#8594;</a>'
    ) if link else ""

    primary_html = "".join([
        _detail("Result", p.get("ai_main_result", "") or ai_finding),
        _detail("Sample", p.get("ai_sample", "")),
        _detail("Design", p.get("ai_design", "")),
        _detail("Question", p.get("ai_research_question", "")),
        _detail("Why it matters", p.get("ai_why_it_matters", "")),
    ])
    secondary_html = "".join([
        _detail("Measures", p.get("ai_measures", "")),
        _detail("Limitations", p.get("ai_limitations", "")),
        _detail("Keywords", p.get("ai_bibtex_keywords", "")),
    ])
    if secondary_html:
        secondary_html = (
            '<details style="margin-top:6px;">'
            '<summary style="font-size:11px;color:#64748b;cursor:pointer;font-weight:700;">More structured details</summary>'
            f'{secondary_html}'
            '</details>'
        )
    structured_html = primary_html + secondary_html

    ai_block = ""
    if ai_summary or structured_html:
        summary_p = (
            f'<p style="margin:0 0 8px;font-size:13px;color:#334155;">{html.escape(ai_summary)}</p>'
            if ai_summary else ""
        )
        ai_block = (
            f'<div style="margin:10px 0 0;padding:10px 12px;background:#f8fafc;'
            f'border-left:3px solid #2563eb;border-radius:0 6px 6px 0;">'
            f'{summary_p}{structured_html}</div>'
        )

    method_html = _method_badge(ai_method) if ai_method else ""

    return (
        f'<div style="margin:0 0 20px;padding:18px 20px;background:#fff;'
        f'border:1px solid #e2e8f0;border-radius:8px;'
        f'box-shadow:0 1px 3px rgba(0,0,0,.06);">'
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:flex-start;margin-bottom:8px;">'
        f'<span style="font-size:11px;font-weight:700;color:#94a3b8;">#{rank}</span>'
        f'<span style="font-size:11px;color:#94a3b8;">'
        f'Score: <strong style="color:#2563eb;">{score_str}</strong>'
        f'&nbsp;|&nbsp;Citations: <strong>{cite_str}</strong>'
        f'&nbsp;|&nbsp;Fit: <strong>{fit_str}</strong></span></div>'
        f'<h3 style="margin:0 0 6px;font-size:15px;line-height:1.4;color:#0f172a;">{title}</h3>'
        f'<p style="margin:0 0 8px;font-size:12px;color:#64748b;">{journal} &nbsp;&middot;&nbsp; {year}</p>'
        f'{_detail("Authors", authors)}'
        f'{_detail("Institution", institution)}'
        f'<div style="margin-bottom:8px;">{method_html}{_tag_badges(tags)}{_research_tag_badges(research_tags)}</div>'
        f'{_why_selected_block(p)}'
        f'{_detail("Feedback signal", p.get("feedback_reason", ""))}'
        f'{ai_block}'
        f'<div style="margin-top:12px;">{link_html}</div>'
        f'{_feedback_buttons(p)}'
        f'</div>'
    )


def _section_anchor(section_key: str) -> str:
    return "section-" + "".join(ch if ch.isalnum() else "-" for ch in section_key.lower())


def _toc_html(section_entries: List[tuple[str, int]]) -> str:
    if not section_entries:
        return ""
    rows = []
    for idx, (section_key, count) in enumerate(section_entries, 1):
        title, desc = SECTION_INFO.get(section_key, SECTION_INFO["general_prosocial"])
        rows.append(
            '<tr>'
            f'<td style="padding:7px 8px 7px 0;width:24px;font-size:12px;color:#94a3b8;font-weight:700;">{idx}</td>'
            '<td style="padding:7px 8px 7px 0;">'
            f'<a href="#{_section_anchor(section_key)}" style="font-size:13px;color:#0f172a;text-decoration:none;font-weight:800;">{html.escape(title)}</a>'
            f'<p style="margin:2px 0 0;font-size:11px;line-height:1.35;color:#64748b;">{html.escape(desc)}</p>'
            '</td>'
            f'<td style="padding:7px 0;text-align:right;font-size:12px;color:#475569;font-weight:800;white-space:nowrap;">{count} papers</td>'
            '</tr>'
        )
    return (
        '<div style="margin:0 0 22px;padding:16px 18px;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;">'
        '<p style="margin:0 0 8px;font-size:12px;letter-spacing:.8px;text-transform:uppercase;color:#64748b;font-weight:800;">Today\'s Map</p>'
        f'<table role="presentation" style="width:100%;border-collapse:collapse;">{"".join(rows)}</table>'
        '</div>'
    )


def _feedback_status_html(feedback_status: Dict | None) -> str:
    if not feedback_status:
        return ""
    total = feedback_status.get("count")
    distribution = feedback_status.get("distribution") or {}
    if total in (None, "") and not distribution:
        return ""

    chips = []
    for rating, label, color, background in FEEDBACK_BUTTONS:
        count = int(distribution.get(rating) or 0)
        if count <= 0:
            continue
        chips.append(
            f'<span style="display:inline-block;margin:4px 6px 0 0;padding:5px 8px;'
            f'border-radius:5px;background:{background};color:{color};font-size:11px;'
            f'font-weight:800;">{html.escape(label)} {count}</span>'
        )

    synced = bool(feedback_status.get("synced"))
    enabled = bool(feedback_status.get("enabled"))
    title = "Feedback learning"
    if synced:
        status = "GitHub feedback synced for this run"
    elif enabled:
        status = "GitHub feedback sync attempted"
    else:
        status = "GitHub feedback sync not available in this run"

    pieces = [status]
    if total not in (None, ""):
        pieces.append(f"{int(total)} stored signal(s)")
    if feedback_status.get("issues_imported") not in (None, ""):
        pieces.append(f"{int(feedback_status.get('issues_imported') or 0)} issue(s) imported")
    reason = feedback_status.get("reason") or feedback_status.get("error")
    if reason:
        pieces.append(_shorten(str(reason), 120))

    return (
        '<div style="margin:0 0 18px;padding:12px 16px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;">'
        f'<p style="margin:0;font-size:12px;color:#0f172a;font-weight:800;">{html.escape(title)}</p>'
        f'<p style="margin:4px 0 0;font-size:12px;line-height:1.4;color:#64748b;">{html.escape("; ".join(pieces))}</p>'
        f'{"".join(chips)}'
        '</div>'
    )


def render_email(papers: List[Dict], total_found: int, feedback_status: Dict | None = None) -> str:
    def section_html(section_key: str, ranked: List[tuple[int, Dict]]) -> str:
        if not ranked:
            return ""
        title, desc = SECTION_INFO.get(section_key, SECTION_INFO["general_prosocial"])
        cards = "".join(_paper_card(rank, paper) for rank, paper in ranked)
        count = len(ranked)
        count_label = "1 paper" if count == 1 else f"{count} papers"
        return (
            f'<div id="{_section_anchor(section_key)}" style="margin:22px 0 10px;">'
            f'<h2 style="margin:0 0 4px;font-size:16px;color:#0f172a;">{html.escape(title)} '
            f'<span style="font-size:12px;color:#64748b;font-weight:600;">&middot; {count_label}</span></h2>'
            f'<p style="margin:0 0 12px;font-size:12px;color:#64748b;">{html.escape(desc)}</p>'
            f'{cards}</div>'
        )

    ranked = list(enumerate(papers, 1))
    top = ranked[:5]
    top_ids = {id(paper) for _, paper in top}
    grouped = {key: [] for key in SECTION_ORDER}
    for rank, paper in ranked[5:]:
        if id(paper) in top_ids:
            continue
        key = str(paper.get("email_section") or "general_prosocial")
        if key not in grouped:
            key = "general_prosocial"
        grouped[key].append((rank, paper))

    section_entries = []
    if top:
        section_entries.append(("top", len(top)))
    section_entries.extend((key, len(grouped[key])) for key in SECTION_ORDER if grouped[key])

    today = date.today().strftime("%B %d, %Y")
    feedback_html = _feedback_status_html(feedback_status)
    toc_html = _toc_html(section_entries)
    cards_html = section_html("top", top) + "".join(section_html(key, grouped[key]) for key in SECTION_ORDER)

    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        '<title>Prosocial Research Radar</title></head>'
        '<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,'
        'BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;">'
        '<div style="max-width:680px;margin:32px auto;padding:0 16px 40px;">'
        '<div style="background:#0f172a;border-radius:10px;padding:28px 28px 24px;margin-bottom:24px;color:#fff;">'
        f'<p style="margin:0 0 4px;font-size:12px;letter-spacing:1.5px;text-transform:uppercase;opacity:.8;">'
        f'Daily Digest &middot; {today}</p>'
        '<h1 style="margin:0 0 8px;font-size:22px;font-weight:700;">Research-Focused Prosocial Radar</h1>'
        f'<p style="margin:0;font-size:14px;opacity:.85;">'
        f'{len(papers)} new papers selected from {total_found} candidates</p>'
        '</div>'
        + feedback_html + toc_html + cards_html +
        '<div style="margin-top:28px;padding:16px 20px;background:#e2e8f0;border-radius:8px;text-align:center;">'
        '<p style="margin:0;font-size:12px;color:#64748b;">'
        'Generated by Prosocial Research Radar &nbsp;&middot;&nbsp; Sources: PubMed + OpenAlex '
        '&nbsp;&middot;&nbsp; AI summaries by configured LLM</p></div>'
        '</div></body></html>'
    )


def _send_capymail(subject: str, html_body: str) -> bool:
    script = "/home/node/.claude/skills/capymail/scripts/send_email.sh"
    if not os.path.exists(script):
        return False
    ok = True
    for recipient in RECIPIENTS:
        cmd = ["bash", script, "--to", recipient, "--subject", subject, "--html", html_body]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                log.info("capymail: sent OK -> %s", recipient)
            else:
                log.warning("capymail rc=%d -> %s: %s", r.returncode, recipient, (r.stderr or r.stdout)[:150])
                ok = False
        except Exception as exc:
            log.warning("capymail exception -> %s: %s", recipient, exc)
            ok = False
    return ok


def _send_smtp(subject: str, html_body: str) -> bool:
    sender = os.environ.get("GMAIL_ADDRESS", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

    if not sender or not password:
        log.warning("SMTP backend: GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, RECIPIENTS, msg.as_bytes())
        log.info("SMTP: sent OK -> %s", ", ".join(RECIPIENTS))
        return True
    except smtplib.SMTPAuthenticationError:
        log.error("SMTP auth failed - check GMAIL_ADDRESS and GMAIL_APP_PASSWORD.")
        return False
    except Exception as exc:
        log.error("SMTP send failed - %s", exc)
        return False


def send_email(papers: List[Dict], total_found: int, feedback_status: Dict | None = None) -> bool:
    """Send the digest email. Returns True on success."""
    if not papers:
        log.info("No new papers - skipping email.")
        return False
    if not RECIPIENTS:
        log.warning("No email recipients configured - skipping email.")
        return False

    today = date.today().strftime("%Y-%m-%d")
    subject = f"Prosocial Research Radar - {today} | {len(papers)} new papers"
    html_body = render_email(papers, total_found, feedback_status=feedback_status)

    log.info("Sending digest to [%s] (%d papers) ...", ", ".join(RECIPIENTS), len(papers))

    if _send_capymail(subject, html_body):
        return True

    log.info("capymail unavailable - trying SMTP backend.")
    return _send_smtp(subject, html_body)
