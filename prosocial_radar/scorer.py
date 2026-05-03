"""
Relevance scoring module.

Computes a relevance_score (0-100) for each paper based on:
  - Keyword hits in title (weighted x3) and abstract (x1)  -> up to 40 pts
  - Citation bonus (log-scaled)                            -> up to 25 pts
  - Recency bonus (papers <=3 years old, heavily weighted) -> up to 25 pts
  - Topic breadth bonus (multiple tags hit)                -> up to 10 pts
  - Evidence-tier adjustment                               -> -25 to +10 pts
"""

import logging
import math
import re
from datetime import date
from typing import Dict, List

log = logging.getLogger(__name__)

CURRENT_YEAR = date.today().year

# Keyword tiers with weights: higher weight = stronger signal.
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
    title = (paper.get("title", "") or "").lower()
    abstract = (paper.get("abstract", "") or "").lower()
    score = 0.0
    for weight, patterns in KEYWORD_TIERS:
        for pat in patterns:
            if re.search(pat, title, re.IGNORECASE):
                score += weight * 3
            if re.search(pat, abstract, re.IGNORECASE):
                score += weight * 1
    return score


def _citation_bonus(paper: Dict) -> float:
    """Log-scaled citation bonus, max 25 pts."""
    c = paper.get("citation_count")
    if not c or c <= 0:
        return 0.0
    return min(math.log10(c + 1) * 5.0, 25.0)


def _recency_bonus(paper: Dict) -> float:
    """Bonus for papers published <=3 years ago, max 25 pts."""
    try:
        year = int(str(paper.get("year", "") or "")[:4])
        age = CURRENT_YEAR - year
        if age <= 0:
            return 25.0
        if age <= 1:
            return 20.0
        if age <= 2:
            return 12.0
        if age <= 3:
            return 5.0
        return 0.0
    except (ValueError, TypeError):
        return 0.0


def _breadth_bonus(paper: Dict) -> float:
    """Bonus for hitting multiple topic tags, max 10 pts."""
    tags = [t.strip() for t in (paper.get("topic_tags") or "").split(";") if t.strip()]
    return min(len(tags) * 2.5, 10.0)


def _evidence_adjustment(paper: Dict) -> float:
    """Evidence-tier adjustment assigned during filtering."""
    try:
        return float(paper.get("evidence_score_adjustment") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _score_components(paper: Dict) -> Dict[str, float]:
    kw_raw = _keyword_score(paper)
    kw = min(kw_raw, 40.0)
    cit = _citation_bonus(paper)
    rec = _recency_bonus(paper)
    br = _breadth_bonus(paper)
    ev = _evidence_adjustment(paper)
    final = min(max(round(kw + cit + rec + br + ev, 1), 0.0), 100.0)
    return {
        "keyword": round(kw, 1),
        "keyword_raw": round(kw_raw, 1),
        "citation": round(cit, 1),
        "recency": round(rec, 1),
        "breadth": round(br, 1),
        "evidence": round(ev, 1),
        "final": final,
    }


def _selection_reason(paper: Dict, components: Dict[str, float]) -> str:
    parts = [
        (
            "score {final:.1f}: keywords {keyword:.1f}/40, citations {citation:.1f}/25, "
            "recency {recency:.1f}/25, breadth {breadth:.1f}/10, evidence {evidence:+.1f}"
        ).format(**components)
    ]
    if paper.get("filter_reason"):
        parts.append("filter passed because " + str(paper.get("filter_reason")))
    if paper.get("evidence_level"):
        parts.append("evidence tier: " + str(paper.get("evidence_level")))
    if paper.get("is_high_quality"):
        parts.append("target-journal quality badge")
    return "; ".join(parts)


def score_paper(paper: Dict) -> float:
    """Compute final relevance_score (0-100) for a single paper."""
    components = _score_components(paper)
    return components["final"]


def score_papers(papers: List[Dict]) -> List[Dict]:
    """Add relevance_score plus explanation fields to all papers and sort descending."""
    for p in papers:
        components = _score_components(p)
        p["score_keyword"] = components["keyword"]
        p["score_keyword_raw"] = components["keyword_raw"]
        p["score_citation"] = components["citation"]
        p["score_recency"] = components["recency"]
        p["score_breadth"] = components["breadth"]
        p["score_evidence"] = components["evidence"]
        p["relevance_score"] = components["final"]
        p["score_breakdown"] = (
            f"keyword={components['keyword']:.1f}; "
            f"citation={components['citation']:.1f}; "
            f"recency={components['recency']:.1f}; "
            f"breadth={components['breadth']:.1f}; "
            f"evidence={components['evidence']:+.1f}"
        )
        p["selection_reason"] = _selection_reason(p, components)

    papers.sort(key=lambda x: -(x["relevance_score"] or 0))
    log.info(
        "Scoring complete. Top score: %.1f | Median: %.1f",
        papers[0]["relevance_score"] if papers else 0,
        papers[len(papers) // 2]["relevance_score"] if papers else 0,
    )
    return papers
