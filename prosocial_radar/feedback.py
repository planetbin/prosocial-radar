"""GitHub-native feedback support for radar papers."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import quote_plus

import requests

log = logging.getLogger(__name__)

FEEDBACK_PATH = Path("data/feedback.json")
RATINGS = ("must_read", "useful", "maybe", "ignore")
RATING_LABELS = {
    "must_read": "Must read",
    "useful": "Useful",
    "maybe": "Maybe",
    "ignore": "Ignore",
}
EXACT_ADJUSTMENTS = {
    "must_read": 25.0,
    "useful": 12.0,
    "maybe": 3.0,
    "ignore": -50.0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_full_name() -> str:
    return os.environ.get("GITHUB_REPOSITORY", "planetbin/prosocial-radar").strip()


def _normalise_doi(doi: str | None) -> str:
    return (doi or "").replace("https://doi.org/", "").lower().strip()


def paper_key(paper: Dict) -> str:
    return str(paper.get("pmid") or _normalise_doi(paper.get("doi")) or "").strip()


def load_feedback() -> Dict[str, Dict]:
    if not FEEDBACK_PATH.exists():
        return {}
    try:
        with FEEDBACK_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log.warning("Could not load feedback file: %s", exc)
        return {}


def save_feedback(feedback: Dict[str, Dict]) -> None:
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_PATH.open("w", encoding="utf-8") as fh:
        json.dump(feedback, fh, ensure_ascii=False, indent=2, sort_keys=True)


def feedback_issue_url(paper: Dict, rating: str) -> str:
    """Build a prefilled GitHub issue URL for one feedback action."""
    repo = _repo_full_name()
    safe_rating = rating if rating in RATINGS else "maybe"
    pmid = str(paper.get("pmid") or "").strip()
    doi = _normalise_doi(paper.get("doi"))
    title = str(paper.get("title") or "").strip()
    journal = str(paper.get("journal") or "").strip()
    tags = str(paper.get("topic_tags") or "").strip()
    score = str(paper.get("relevance_score") or "").strip()

    issue_title = f"[radar-feedback] {safe_rating} PMID:{pmid or 'none'}"
    body = "\n".join([
        "radar_feedback: true",
        f"rating: {safe_rating}",
        f"pmid: {pmid}",
        f"doi: {doi}",
        f"title: {title}",
        f"journal: {journal}",
        f"topic_tags: {tags}",
        f"score: {score}",
        "",
        "Notes:",
    ])
    return (
        f"https://github.com/{repo}/issues/new"
        f"?title={quote_plus(issue_title)}"
        f"&labels={quote_plus('radar-feedback')}"
        f"&body={quote_plus(body)}"
    )


def attach_feedback_links(papers: Iterable[Dict]) -> None:
    for paper in papers:
        paper["feedback_links"] = {rating: feedback_issue_url(paper, rating) for rating in RATINGS}
        for rating in RATINGS:
            paper[f"feedback_{rating}_url"] = paper["feedback_links"][rating]


def _parse_feedback_body(body: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for line in (body or "").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower().replace("-", "_")
        if key in {"rating", "pmid", "doi", "title", "journal", "topic_tags", "score"}:
            fields[key] = value.strip()
    return fields


def _issue_to_feedback(issue: Dict) -> Dict | None:
    body = issue.get("body") or ""
    if "radar_feedback" not in body and "[radar-feedback]" not in (issue.get("title") or ""):
        return None

    fields = _parse_feedback_body(body)
    rating = fields.get("rating", "").strip().lower()
    if rating not in RATINGS:
        title_match = re.search(r"\[radar-feedback\]\s+(\w+)", issue.get("title") or "", re.I)
        rating = (title_match.group(1).lower() if title_match else "")
    if rating not in RATINGS:
        return None

    pmid = fields.get("pmid", "").strip()
    doi = _normalise_doi(fields.get("doi"))
    key = pmid or doi
    if not key:
        return None

    return {
        "rating": rating,
        "pmid": pmid,
        "doi": doi,
        "title": fields.get("title", ""),
        "journal": fields.get("journal", ""),
        "topic_tags": fields.get("topic_tags", ""),
        "score": fields.get("score", ""),
        "issue_number": issue.get("number"),
        "issue_url": issue.get("html_url"),
        "updated_at": issue.get("updated_at") or _now(),
    }


def sync_feedback_from_github() -> Dict:
    """Pull radar-feedback issues into data/feedback.json when running in GitHub Actions."""
    repo = _repo_full_name()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        return {"enabled": False, "reason": "GITHUB_TOKEN not set", "count": len(load_feedback())}

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{repo}/issues"
    params = {"state": "all", "labels": "radar-feedback", "per_page": 100}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        issues = response.json()
    except Exception as exc:
        log.warning("Could not sync GitHub feedback issues: %s", exc)
        return {"enabled": True, "synced": False, "error": str(exc), "count": len(load_feedback())}

    feedback = load_feedback()
    imported = 0
    for issue in issues:
        item = _issue_to_feedback(issue)
        if not item:
            continue
        key = item.get("pmid") or item.get("doi")
        if key:
            feedback[key] = item
            imported += 1

    save_feedback(feedback)
    log.info("Feedback sync complete: %d issue(s), %d stored entries", imported, len(feedback))
    return {"enabled": True, "synced": True, "issues_imported": imported, "count": len(feedback)}


def _tags(value: str) -> set[str]:
    return {tag.strip().lower() for tag in (value or "").split(";") if tag.strip()}


def _rating_bucket(feedback: Dict[str, Dict], ratings: set[str]) -> List[Dict]:
    return [item for item in feedback.values() if item.get("rating") in ratings]


def _similarity_adjustment(paper: Dict, feedback: Dict[str, Dict]) -> tuple[float, List[str]]:
    paper_journal = (paper.get("journal") or "").lower().strip()
    paper_tags = _tags(paper.get("topic_tags") or "")
    adjustment = 0.0
    reasons: List[str] = []

    positive = _rating_bucket(feedback, {"must_read", "useful"})
    negative = _rating_bucket(feedback, {"ignore"})

    for item in positive:
        item_journal = (item.get("journal") or "").lower().strip()
        item_tags = _tags(item.get("topic_tags") or "")
        if item_journal and paper_journal and item_journal == paper_journal:
            adjustment += 2.0
        shared = paper_tags & item_tags
        if shared:
            adjustment += min(len(shared) * 1.5, 4.5)

    for item in negative:
        item_journal = (item.get("journal") or "").lower().strip()
        item_tags = _tags(item.get("topic_tags") or "")
        if item_journal and paper_journal and item_journal == paper_journal:
            adjustment -= 3.0
        shared = paper_tags & item_tags
        if shared:
            adjustment -= min(len(shared) * 2.0, 6.0)

    adjustment = max(min(adjustment, 12.0), -18.0)
    if adjustment > 0:
        reasons.append(f"similar to positively rated papers (+{adjustment:.1f})")
    elif adjustment < 0:
        reasons.append(f"similar to ignored papers ({adjustment:.1f})")
    return adjustment, reasons


def apply_feedback_adjustments(papers: List[Dict]) -> List[Dict]:
    feedback = load_feedback()
    if not feedback:
        for paper in papers:
            paper.setdefault("feedback_rating", "")
            paper.setdefault("feedback_adjustment", 0.0)
            paper.setdefault("feedback_reason", "")
        return papers

    for paper in papers:
        key = paper_key(paper)
        doi = _normalise_doi(paper.get("doi"))
        exact = feedback.get(key) or (feedback.get(doi) if doi else None)
        adjustment = 0.0
        reasons: List[str] = []
        rating = ""

        if exact:
            rating = exact.get("rating", "")
            adjustment += EXACT_ADJUSTMENTS.get(rating, 0.0)
            reasons.append(f"exact feedback: {rating} ({adjustment:+.1f})")
        else:
            similarity_adjustment, similarity_reasons = _similarity_adjustment(paper, feedback)
            adjustment += similarity_adjustment
            reasons.extend(similarity_reasons)

        old_score = paper.get("relevance_score")
        if isinstance(old_score, (int, float)) and adjustment:
            paper["relevance_score"] = max(0.0, min(100.0, round(old_score + adjustment, 1)))

        paper["feedback_rating"] = rating
        paper["feedback_adjustment"] = round(adjustment, 1)
        paper["feedback_reason"] = "; ".join(reasons)
        if reasons:
            existing = paper.get("selection_reason", "")
            paper["selection_reason"] = f"{existing}; feedback: {'; '.join(reasons)}" if existing else f"Feedback: {'; '.join(reasons)}"

    papers.sort(key=lambda x: -(x.get("relevance_score") or 0))
    return papers
