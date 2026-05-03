"""Markdown literature digest generation."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List

FEEDBACK_LABELS = (
    ("must_read", "Must read"),
    ("useful", "Useful"),
    ("maybe", "Maybe"),
    ("ignore", "Ignore"),
)

CATEGORY_ORDER = [
    "Must read",
    "Intervention / education",
    "Development",
    "Neuroscience",
    "Review / meta-analysis",
    "Low priority",
    "Other",
]


def _clean(value, fallback: str = "") -> str:
    return str(value or fallback).strip()


def _squash(value: str, limit: int = 520) -> str:
    text = re.sub(r"\s+", " ", _clean(value)).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _score(value) -> str:
    return f"{value:.1f}" if isinstance(value, (int, float)) else "-"


def _links(paper: Dict) -> str:
    parts = []
    if paper.get("url"):
        parts.append(f"[PubMed]({paper['url']})")
    if paper.get("doi_url"):
        parts.append(f"[DOI]({paper['doi_url']})")
    return " | ".join(parts)


def _feedback_links(paper: Dict) -> str:
    links = paper.get("feedback_links") or {}
    parts = [f"[{label}]({links[rating]})" for rating, label in FEEDBACK_LABELS if links.get(rating)]
    return " | ".join(parts)


def _category(paper: Dict) -> str:
    if paper.get("feedback_rating") == "must_read":
        return "Must read"

    tags = {t.strip().lower() for t in _clean(paper.get("topic_tags")).split(";") if t.strip()}
    title = _clean(paper.get("title")).lower()
    method = _clean(paper.get("ai_method")).lower()
    journal = _clean(paper.get("journal")).lower()
    score = paper.get("relevance_score") or 0

    if score and score < 25:
        return "Low priority"
    if any(term in title for term in ["intervention", "training", "education", "picture book", "program"]):
        return "Intervention / education"
    if "development" in tags or any(term in title for term in ["child", "children", "adolescent", "preschool"]):
        return "Development"
    if "neuroscience" in tags or method in {"fmri", "eeg", "neuroimaging"}:
        return "Neuroscience"
    if "review" in method or "meta-analysis" in title or "review" in title or "review" in journal:
        return "Review / meta-analysis"
    return "Other"


def _paper_lines(rank: int, paper: Dict) -> List[str]:
    title = _clean(paper.get("title"), "Untitled")
    year = _clean(paper.get("year"), "n.d.")
    journal = _clean(paper.get("journal"), "unknown journal")
    citations = paper.get("citation_count")
    citation_text = str(citations) if citations is not None else "-"
    tags = _clean(paper.get("topic_tags"), "-")
    summary = _squash(paper.get("ai_summary") or paper.get("abstract"), 520)
    selected = _clean(paper.get("selection_reason") or paper.get("filter_reason"), "Selected by profile keyword gate and relevance score.")
    feedback = _feedback_links(paper)

    lines = [
        f"{rank}. **{title}** ({year}). *{journal}*.",
        f"   - Score: {_score(paper.get('relevance_score'))}; citations: {citation_text}; tags: {tags}",
        f"   - Why selected: {_squash(selected, 360)}",
    ]

    for label, field in [
        ("Question", "ai_research_question"),
        ("Sample", "ai_sample"),
        ("Design", "ai_design"),
        ("Main result", "ai_main_result"),
        ("Why it matters", "ai_why_it_matters"),
    ]:
        value = _squash(paper.get(field), 300)
        if value:
            lines.append(f"   - {label}: {value}")

    if summary:
        lines.append(f"   - Summary: {summary}")
    if _links(paper):
        lines.append(f"   - Links: {_links(paper)}")
    if feedback:
        lines.append(f"   - Feedback: {feedback}")
    return lines


def build_markdown_digest(papers: Iterable[Dict], total_found: int, run_date: date | None = None) -> str:
    """Return a researcher-facing Markdown digest for selected papers."""
    selected = list(papers)
    today = run_date or date.today()
    lines = [
        f"# Prosocial Research Radar Digest - {today.isoformat()}",
        "",
        f"Selected {len(selected)} new papers from {total_found} filtered candidates.",
        "",
        "## At a Glance",
        "",
    ]

    if not selected:
        lines.extend(["No new papers were selected in this run.", ""])
    else:
        for idx, paper in enumerate(selected, 1):
            title = _clean(paper.get("title"), "Untitled")
            lines.append(f"- {idx}. {title} ({_score(paper.get('relevance_score'))})")
        lines.append("")

    grouped = {category: [] for category in CATEGORY_ORDER}
    for paper in selected:
        grouped.setdefault(_category(paper), []).append(paper)

    rank = 1
    for category in CATEGORY_ORDER:
        papers_in_category = grouped.get(category) or []
        if not papers_in_category:
            continue
        lines.extend([f"## {category}", ""])
        for paper in papers_in_category:
            lines.extend(_paper_lines(rank, paper))
            lines.append("")
            rank += 1

    lines.extend([
        "## Notes",
        "",
        "- Feedback links create GitHub issues labelled `radar-feedback`; the next scheduled run syncs those issues into `data/feedback.json` and adjusts future scores.",
        "- The full candidate audit is uploaded as a GitHub Actions artifact, while the repository keeps only compact durable outputs.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def save_markdown_digest(markdown: str, out_dir: Path, prefix: str = "digest") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{prefix}_{date.today().strftime('%Y%m%d')}.md"
    with path.open("w", encoding="utf-8") as fh:
        fh.write(markdown)
    return path
