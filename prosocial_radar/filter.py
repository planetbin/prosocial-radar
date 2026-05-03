"""
Quality filter and deduplication layer.

The active profile controls tier keywords, tag rules, and target journals.
Journal is used as a quality badge, not as a hard filter.
"""

import logging
import re
from typing import Dict, Iterable, List

from .config import TAG_RULES, TARGET_JOURNALS, TIER_A, TIER_B

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


def _matches_any(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _passes_relevance(text: str) -> bool:
    """Paper must hit at least one core keyword and one context/method keyword."""
    return _matches_any(TIER_A, text) and _matches_any(TIER_B, text)


def _assign_tags(text: str) -> List[str]:
    tags = []
    for tag, patterns in TAG_RULES.items():
        if _matches_any(patterns, text):
            tags.append(tag)
    return tags


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


def apply_filters(papers: List[Dict]) -> List[Dict]:
    """Apply the profile's keyword relevance gate."""
    passed = [p for p in papers if _passes_relevance(_lower_text(p))]
    log.info("Relevance filter: %d -> %d papers", len(papers), len(passed))
    return passed


def enrich_metadata(papers: List[Dict]) -> List[Dict]:
    """Add topic_tags and is_high_quality flag to each paper."""
    for p in papers:
        text = _lower_text(p)
        p["topic_tags"] = "; ".join(_assign_tags(text))
        p["is_high_quality"] = _journal_match(p)
    return papers


def run_filter_pipeline(papers: List[Dict]) -> List[Dict]:
    """Full pipeline: dedup -> relevance filter -> metadata enrichment."""
    papers = deduplicate(papers)
    papers = apply_filters(papers)
    papers = enrich_metadata(papers)
    log.info("Filter pipeline complete: %d papers retained", len(papers))
    return papers
