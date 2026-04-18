"""
Quality filter and deduplication layer.

Redesigned for daily freshness:

  OLD: hard journal whitelist  →  many new papers blocked every day
  NEW: keyword relevance gate  →  all topically relevant papers pass
       is_high_quality flag     →  marks tier-1 journal papers (used in scoring)

Steps:
  1. Deduplicate by PMID, then by DOI.
  2. Relevance gate: title/abstract must hit ≥2 core prosocial keywords.
     (≥1 from tier-A "core concepts", ≥1 from tier-B "methods/context")
  3. Tag papers with topic_tags and is_high_quality flag.
"""

import logging
import re
from typing import List, Dict

from .config import TARGET_JOURNALS

log = logging.getLogger(__name__)


# ─── Tier-A: Core prosocial concepts (must hit ≥1) ───────────────────────────
TIER_A = [
    r"\bprosocial\b",
    r"\baltruism\b",
    r"\baltruistic\b",
    r"\bempathy\b",
    r"\bempathic\b",
    r"\bempathetic\b",
    r"\bcharitable\b",
    r"\bcooperation\b",
    r"\bcooperative\b",
    r"\bhelping behavior\b",
    r"\bhelping behaviour\b",
    r"\btrust game\b",
    r"\bdictator game\b",
    r"\bultimatum game\b",
    r"\bpublic goods game\b",
    r"\bsocial preference\b",
    r"\bsocial decision",
    r"\bprosociality\b",
]

# ─── Tier-B: Context / method indicators (must hit ≥1) ───────────────────────
TIER_B = [
    r"\bchild\b", r"\bchildren\b", r"\binfant\b", r"\badolescent\b",
    r"\bdevelopment\b", r"\bdevelopmental\b",
    r"\bfmri\b", r"\bfunctional mri\b", r"\beeg\b", r"\bneuroimaging\b",
    r"\bneural\b", r"\bbrain\b", r"\bneuroscience\b",
    r"\bbehavior\b", r"\bbehaviour\b",
    r"\bdecision[- ]making\b",
    r"\bfairness\b", r"\bmoral\b",
    r"\bgiving\b", r"\bdonat\b",
]

# ─── Topic tag rules ──────────────────────────────────────────────────────────
TAG_RULES = {
    "altruism":        [r"\baltruism\b", r"\baltruistic\b"],
    "empathy":         [r"\bempathy\b", r"\bempathic\b", r"\bempathetic\b"],
    "cooperation":     [r"\bcooperation\b", r"\bcooperative\b"],
    "economic_games":  [r"\btrust game\b", r"\bdictator game\b",
                        r"\bultimatum game\b", r"\bpublic goods\b"],
    "development":     [r"\bchild\b", r"\bchildren\b", r"\badolescent\b",
                        r"\bdevelopment\b", r"\binfant\b"],
    "neuroscience":    [r"\bfmri\b", r"\beeg\b", r"\bneuroimaging\b",
                        r"\bneural\b", r"\bbrain\b"],
    "decision_making": [r"\bdecision[- ]making\b", r"\bsocial decision\b"],
    "moral":           [r"\bmoral\b", r"\bethics\b"],
}


def _lower_text(paper: Dict) -> str:
    return " ".join([
        paper.get("title",    "") or "",
        paper.get("abstract", "") or "",
        paper.get("keywords", "") or "",
    ]).lower()


def _journal_match(paper: Dict) -> bool:
    journal = (paper.get("journal") or "").lower()
    return any(t in journal for t in TARGET_JOURNALS)


def _passes_relevance(text: str) -> bool:
    """Paper must hit ≥1 Tier-A keyword AND ≥1 Tier-B keyword."""
    hit_a = any(re.search(p, text, re.IGNORECASE) for p in TIER_A)
    hit_b = any(re.search(p, text, re.IGNORECASE) for p in TIER_B)
    return hit_a and hit_b


def _assign_tags(text: str) -> List[str]:
    tags = []
    for tag, patterns in TAG_RULES.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            tags.append(tag)
    return tags


def deduplicate(papers: List[Dict]) -> List[Dict]:
    """Remove duplicates by PMID first, then by DOI."""
    seen_pmids, seen_dois, unique = set(), set(), []
    for p in papers:
        pmid = p.get("pmid") or ""
        doi  = (p.get("doi") or "").lower().strip()
        if pmid and pmid in seen_pmids:
            continue
        if doi and doi in seen_dois:
            continue
        if pmid:
            seen_pmids.add(pmid)
        if doi:
            seen_dois.add(doi)
        unique.append(p)
    log.info("Deduplication: %d → %d papers", len(papers), len(unique))
    return unique


def apply_filters(papers: List[Dict]) -> List[Dict]:
    """
    Keyword-only relevance gate (Tier-A AND Tier-B).
    Journal is NOT used as a hard filter — only as a quality flag.
    This ensures new papers from any journal flow through daily.
    """
    passed = [p for p in papers if _passes_relevance(_lower_text(p))]
    log.info("Relevance filter: %d → %d papers", len(papers), len(passed))
    return passed


def enrich_metadata(papers: List[Dict]) -> List[Dict]:
    """Add topic_tags and is_high_quality flag to each paper."""
    for p in papers:
        text = _lower_text(p)
        p["topic_tags"]      = "; ".join(_assign_tags(text))
        p["is_high_quality"] = _journal_match(p)   # tier-1 journal badge
    return papers


def run_filter_pipeline(papers: List[Dict]) -> List[Dict]:
    """Full pipeline: dedup → relevance filter → metadata enrichment."""
    papers = deduplicate(papers)
    papers = apply_filters(papers)
    papers = enrich_metadata(papers)
    log.info("Filter pipeline complete: %d papers retained", len(papers))
    return papers
