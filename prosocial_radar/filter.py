"""
Quality filter and deduplication layer.

The active profile controls tier keywords, tag rules, and target journals.
Journal is used as a quality badge, not as a hard filter.
"""

import logging
import re
from typing import Dict, Iterable, List

from .config import TAG_RULES, TARGET_JOURNALS, TIER_A, TIER_B
from .evidence import annotate_evidence

log = logging.getLogger(__name__)


def _lower_text(paper: Dict) -> str:
    return " ".join([
        paper.get("title", "") or "",
        paper.get("abstract", "") or "",
        paper.get("keywords", "") or "",
    ]).lower()


def _journal_match(paper: Dict) -> bool:
    journal = (paper.get("journal") or "").lower()
    return any(t in journal for t in TARGET_JOURNALS)


def _display_pattern(pattern: str) -> str:
    text = pattern.replace(r"\b", "").replace(r"\s+", " ")
    text = text.replace(".*", " ... ").replace("\\", "")
    text = re.sub(r"\s+", " ", text).strip(" ^$")
    return text or pattern


def _matched_patterns(patterns: Iterable[str], text: str) -> List[str]:
    matches = []
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            label = _display_pattern(pattern)
            if label not in matches:
                matches.append(label)
    return matches


def _matches_any(patterns: Iterable[str], text: str) -> bool:
    return bool(_matched_patterns(patterns, text))


def _passes_relevance(text: str) -> bool:
    """Paper must hit at least one core keyword and one context/method keyword."""
    return _matches_any(TIER_A, text) and _matches_any(TIER_B, text)


def _assign_tags(text: str) -> List[str]:
    tags = []
    for tag, patterns in TAG_RULES.items():
        if _matches_any(patterns, text):
            tags.append(tag)
    return tags


def _filter_reason(
    tier_a: List[str],
    tier_b: List[str],
    tags: List[str],
    high_quality: bool,
    evidence_decision: str,
    evidence_reason: str,
) -> str:
    reasons = []
    if tier_a:
        reasons.append("matched Tier-A core topic: " + ", ".join(tier_a[:6]))
    else:
        reasons.append("missing Tier-A core prosocial keyword")

    if tier_b:
        reasons.append("matched Tier-B context/method: " + ", ".join(tier_b[:6]))
    else:
        reasons.append("missing Tier-B context or method keyword")

    if evidence_decision == "passed":
        reasons.append("evidence tier retained: " + evidence_reason)
    else:
        reasons.append("evidence tier filtered: " + evidence_reason)

    if tags:
        reasons.append("topic tags: " + ", ".join(tags))
    if high_quality:
        reasons.append("journal matched target list")
    return "; ".join(reasons)


def annotate_filter_decision(paper: Dict) -> Dict:
    """Attach pass/fail audit fields to one paper."""
    text = _lower_text(paper)
    tier_a = _matched_patterns(TIER_A, text)
    tier_b = _matched_patterns(TIER_B, text)
    tags = _assign_tags(text)
    high_quality = _journal_match(paper)
    annotate_evidence(paper)
    evidence_decision = paper.get("evidence_decision", "passed")
    evidence_reason = paper.get("evidence_reason", "")
    passed = bool(tier_a and tier_b and evidence_decision == "passed")

    paper["matched_tier_a"] = "; ".join(tier_a)
    paper["matched_tier_b"] = "; ".join(tier_b)
    paper["matched_tags"] = "; ".join(tags)
    paper["topic_tags"] = "; ".join(tags)
    paper["is_high_quality"] = high_quality
    paper["filter_decision"] = "passed" if passed else "filtered_out"
    paper["filter_reason"] = _filter_reason(
        tier_a,
        tier_b,
        tags,
        high_quality,
        evidence_decision,
        evidence_reason,
    )
    return paper


def deduplicate(papers: List[Dict]) -> List[Dict]:
    """Remove duplicates by PMID first, then by DOI."""
    seen_pmids, seen_dois, unique = set(), set(), []
    for p in papers:
        pmid = p.get("pmid") or ""
        doi = (p.get("doi") or "").lower().strip()
        if pmid and pmid in seen_pmids:
            continue
        if doi and doi in seen_dois:
            continue
        if pmid:
            seen_pmids.add(pmid)
        if doi:
            seen_dois.add(doi)
        unique.append(p)
    log.info("Deduplication: %d -> %d papers", len(papers), len(unique))
    return unique


def build_filter_audit(papers: List[Dict]) -> List[Dict]:
    """Deduplicate and annotate every unique paper, including filtered-out items."""
    unique = deduplicate(papers)
    for paper in unique:
        annotate_filter_decision(paper)
    passed = sum(1 for paper in unique if paper.get("filter_decision") == "passed")
    log.info("Filter audit: %d unique papers, %d passed, %d filtered out", unique and len(unique) or 0, passed, len(unique) - passed)
    return unique


def apply_filters(papers: List[Dict]) -> List[Dict]:
    """Apply the profile's keyword relevance and evidence-tier gates."""
    for paper in papers:
        if not paper.get("filter_decision"):
            annotate_filter_decision(paper)
    passed = [p for p in papers if p.get("filter_decision") == "passed"]
    log.info("Relevance + evidence filter: %d -> %d papers", len(papers), len(passed))
    return passed


def enrich_metadata(papers: List[Dict]) -> List[Dict]:
    """Add topic_tags, match audit, evidence tier, and is_high_quality flag to each paper."""
    for p in papers:
        annotate_filter_decision(p)
    return papers


def run_filter_pipeline(papers: List[Dict]) -> List[Dict]:
    """Full pipeline: dedup -> relevance/evidence filter -> metadata enrichment."""
    audit = build_filter_audit(papers)
    papers = apply_filters(audit)
    log.info("Filter pipeline complete: %d papers retained", len(papers))
    return papers
