"""
Relevance scoring module.

Computes a relevance_score (0–100) for each paper based on:
  - Keyword hits in title (weighted x3) and abstract (x1)
  - Citation bonus (log-scaled, up to 30 pts)
  - Recency bonus (papers ≤2 years old, up to 10 pts)
  - Topic breadth bonus (multiple tags hit, up to 10 pts)
"""

import math
import re
import logging
from datetime import date
from typing import Dict, List

log = logging.getLogger(__name__)

CURRENT_YEAR = date.today().year

# Keyword tiers with weights — higher weight = stronger signal
KEYWORD_TIERS = [
    # Tier 1: Core constructs (weight 3)
    (3, [
        r"\bprosocial\b", r"\baltruism\b", r"\baltruistic\b",
        r"\bempathy\b", r"\bempathic\b", r"\bcompassion\b",
    ]),
    # Tier 2: Economic games / paradigms (weight 3)
    (3, [
        r"\btrust game\b", r"\bdictator game\b", r"\bultimatum game\b",
        r"\bpublic goods game\b", r"\bprisoner.s dilemma\b",
    ]),
    # Tier 3: Neural methods (weight 2)
    (2, [
        r"\bfmri\b", r"\bfunctional mri\b", r"\beeg\b",
        r"\bneuroimaging\b", r"\bneural\b", r"\bbrain activat\b",
    ]),
    # Tier 4: Developmental / social (weight 2)
    (2, [
        r"\bchild\b", r"\bchildren\b", r"\badolescent\b",
        r"\bdevelopment\b", r"\bsocial decision\b", r"\bcooperation\b",
    ]),
    # Tier 5: Adjacent concepts (weight 1)
    (1, [
        r"\bfairness\b", r"\bmoral\b", r"\bhelping\b",
        r"\bcharitable\b", r"\bgiving\b", r"\bsocial preference\b",
    ]),
]


def _keyword_score(paper: Dict) -> float:
    """Return raw keyword hit score from title + abstract."""
    title    = (paper.get("title",    "") or "").lower()
    abstract = (paper.get("abstract", "") or "").lower()
    score = 0.0
    for weight, patterns in KEYWORD_TIERS:
        for pat in patterns:
            if re.search(pat, title, re.IGNORECASE):
                score += weight * 3   # title weight x3
            if re.search(pat, abstract, re.IGNORECASE):
                score += weight * 1
    return score


def _citation_bonus(paper: Dict) -> float:
    """Log-scaled citation bonus, max 30 pts."""
    c = paper.get("citation_count")
    if not c or c <= 0:
        return 0.0
    # log10(10)=1 → 6 pts, log10(100)=2 → 12 pts, log10(1000)=3 → 18 pts, cap 30
    return min(math.log10(c + 1) * 6.0, 30.0)


def _recency_bonus(paper: Dict) -> float:
    """Bonus for papers published ≤2 years ago, max 10 pts."""
    try:
        year = int(str(paper.get("year", "") or "")[:4])
        age  = CURRENT_YEAR - year
        if age <= 0:
            return 10.0
        if age <= 1:
            return 8.0
        if age <= 2:
            return 5.0
        return 0.0
    except (ValueError, TypeError):
        return 0.0


def _breadth_bonus(paper: Dict) -> float:
    """Bonus for hitting multiple topic tags, max 10 pts."""
    tags = [t.strip() for t in (paper.get("topic_tags") or "").split(";") if t.strip()]
    return min(len(tags) * 2.5, 10.0)


def score_paper(paper: Dict) -> float:
    """Compute final relevance_score (0–100) for a single paper."""
    kw   = _keyword_score(paper)
    cit  = _citation_bonus(paper)
    rec  = _recency_bonus(paper)
    br   = _breadth_bonus(paper)

    # Keyword score normalised to max ~50 pts (assume ceiling ≈ raw 40)
    kw_norm = min(kw / 40.0 * 50.0, 50.0)

    raw   = kw_norm + cit + rec + br
    final = min(round(raw, 1), 100.0)
    return final


def score_papers(papers: List[Dict]) -> List[Dict]:
    """Add relevance_score to all papers and sort descending."""
    for p in papers:
        p["relevance_score"] = score_paper(p)
    papers.sort(key=lambda x: -(x["relevance_score"] or 0))
    log.info("Scoring complete. Top score: %.1f  |  Median: %.1f",
             papers[0]["relevance_score"] if papers else 0,
             papers[len(papers) // 2]["relevance_score"] if papers else 0)
    return papers
