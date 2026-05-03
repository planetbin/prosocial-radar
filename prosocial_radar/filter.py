"""
Quality filter and deduplication layer.

The active profile controls topic relevance, tag rules, and target journals.
Journal is used as a quality badge, not as a hard filter.
"""

import logging
import re
from typing import Dict, Iterable, List

from .config import (
    TAG_RULES,
    TARGET_JOURNALS,
    TIER_A,
    TIER_B,
    TOPIC_CONTEXT_TERMS,
    TOPIC_CORE_TERMS,
    TOPIC_HARD_EXCLUDE_TERMS,
    TOPIC_MECHANISM_TERMS,
    TOPIC_PARADIGM_TERMS,
    TOPIC_SOFT_EXCLUDE_TERMS,
)

log = logging.getLogger(__name__)

PASSED_TIERS = {"core", "mechanism_linked"}


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


def _assign_tags(text: str) -> List[str]:
    tags = []
    for tag, patterns in TAG_RULES.items():
        if _matches_any(patterns, text):
            tags.append(tag)
    return tags


def _join(values: Iterable[str], limit: int | None = None) -> str:
    values = [v for v in values if v]
    if limit is not None:
        values = values[:limit]
    return "; ".join(values)


def _topic_patterns() -> Dict[str, List[str]]:
    # Backward compatible fallback: older profiles still use Tier-A/Tier-B.
    return {
        "core": TOPIC_CORE_TERMS or TIER_A,
        "paradigm": TOPIC_PARADIGM_TERMS,
        "mechanism": TOPIC_MECHANISM_TERMS or TIER_B,
        "context": TOPIC_CONTEXT_TERMS,
        "soft_exclude": TOPIC_SOFT_EXCLUDE_TERMS,
        "hard_exclude": TOPIC_HARD_EXCLUDE_TERMS,
    }


def _classify_topic(paper: Dict, text: str) -> Dict[str, object]:
    patterns = _topic_patterns()
    title = (paper.get("title") or "").lower()

    core = _matched_patterns(patterns["core"], text)
    paradigm = _matched_patterns(patterns["paradigm"], text)
    mechanism = _matched_patterns(patterns["mechanism"], text)
    context = _matched_patterns(patterns["context"], text)
    soft_exclude = _matched_patterns(patterns["soft_exclude"], text)
    hard_exclude = _matched_patterns(patterns["hard_exclude"], text)
    title_core = _matched_patterns(patterns["core"] + patterns["paradigm"], title)

    direct_anchor = bool(core or paradigm)
    if direct_anchor:
        tier = "mechanism_linked" if mechanism else "core"
        reason = "selected: direct prosocial/social-decision anchor"
        if title_core:
            reason += " in title: " + _join(title_core, 4)
        else:
            reason += ": " + _join(core + paradigm, 5)
        if mechanism:
            reason += "; linked mechanism/method: " + _join(mechanism, 4)
        if context:
            reason += "; context: " + _join(context, 4)
        if soft_exclude:
            reason += "; caution signal: " + _join(soft_exclude, 3)
        if hard_exclude:
            reason += "; hard-exclude signal overridden by direct anchor: " + _join(hard_exclude, 3)
    elif hard_exclude:
        tier = "exclude"
        reason = (
            "filtered: hard-exclude signal without a direct prosocial/social-decision anchor: "
            + _join(hard_exclude, 4)
        )
        if mechanism or context:
            reason += "; adjacent matches only: " + _join(mechanism + context, 5)
    elif mechanism or context:
        tier = "adjacent"
        reason = (
            "filtered: adjacent mechanism/context only; missing direct prosocial behavior, "
            "altruism, cooperation, helping, sharing, donation, or social-decision anchor"
        )
        reason += "; adjacent matches: " + _join(mechanism + context, 6)
    else:
        tier = "exclude"
        reason = "filtered: no configured topic relevance signal"

    return {
        "topic_tier": tier,
        "topic_reason": reason,
        "matched_core_terms": core,
        "matched_paradigm_terms": paradigm,
        "matched_mechanism_terms": mechanism,
        "matched_context_terms": context,
        "matched_soft_exclude_terms": soft_exclude,
        "matched_hard_exclude_terms": hard_exclude,
    }


def _filter_reason(topic: Dict[str, object], tags: List[str], high_quality: bool) -> str:
    reasons = [str(topic.get("topic_reason") or "")]
    if tags:
        reasons.append("topic tags: " + ", ".join(tags))
    if high_quality:
        reasons.append("journal matched target list")
    return "; ".join(reason for reason in reasons if reason)


def annotate_filter_decision(paper: Dict) -> Dict:
    """Attach pass/fail audit fields to one paper."""
    text = _lower_text(paper)
    topic = _classify_topic(paper, text)
    tags = _assign_tags(text)
    high_quality = _journal_match(paper)
    passed = topic["topic_tier"] in PASSED_TIERS

    paper["topic_tier"] = topic["topic_tier"]
    paper["topic_reason"] = topic["topic_reason"]
    paper["matched_core_terms"] = _join(topic["matched_core_terms"])
    paper["matched_paradigm_terms"] = _join(topic["matched_paradigm_terms"])
    paper["matched_mechanism_terms"] = _join(topic["matched_mechanism_terms"])
    paper["matched_context_terms"] = _join(topic["matched_context_terms"])
    paper["matched_soft_exclude_terms"] = _join(topic["matched_soft_exclude_terms"])
    paper["matched_hard_exclude_terms"] = _join(topic["matched_hard_exclude_terms"])

    # Preserve older audit column names for existing outputs and feedback links.
    paper["matched_tier_a"] = _join(topic["matched_core_terms"] + topic["matched_paradigm_terms"])
    paper["matched_tier_b"] = _join(topic["matched_mechanism_terms"] + topic["matched_context_terms"])
    paper["matched_tags"] = "; ".join(tags)
    paper["topic_tags"] = "; ".join(tags)
    paper["is_high_quality"] = high_quality
    paper["filter_decision"] = "passed" if passed else "filtered_out"
    paper["filter_reason"] = _filter_reason(topic, tags, high_quality)
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


def _tier_counts(papers: List[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for paper in papers:
        tier = str(paper.get("topic_tier") or "unknown")
        counts[tier] = counts.get(tier, 0) + 1
    return counts


def build_filter_audit(papers: List[Dict]) -> List[Dict]:
    """Deduplicate and annotate every unique paper, including filtered-out items."""
    unique = deduplicate(papers)
    for paper in unique:
        annotate_filter_decision(paper)
    passed = sum(1 for paper in unique if paper.get("filter_decision") == "passed")
    log.info("Filter audit: %d unique papers, %d passed, %d filtered out", len(unique), passed, len(unique) - passed)
    log.info("Topic tier counts: %s", _tier_counts(unique))
    return unique


def apply_filters(papers: List[Dict]) -> List[Dict]:
    """Apply the profile's topic relevance gate."""
    for paper in papers:
        if not paper.get("filter_decision"):
            annotate_filter_decision(paper)
    passed = [p for p in papers if p.get("filter_decision") == "passed"]
    log.info("Relevance filter: %d -> %d papers", len(papers), len(passed))
    return passed


def enrich_metadata(papers: List[Dict]) -> List[Dict]:
    """Add topic_tags, match audit, and is_high_quality flag to each paper."""
    for p in papers:
        annotate_filter_decision(p)
    return papers


def run_filter_pipeline(papers: List[Dict]) -> List[Dict]:
    """Full pipeline: dedup -> relevance filter -> metadata enrichment."""
    audit = build_filter_audit(papers)
    papers = apply_filters(audit)
    log.info("Filter pipeline complete: %d papers retained", len(papers))
    return papers
