"""
Relevance scoring module.

Computes a relevance_score (0-100) for each paper based on:
  - Topic relevance tier, especially direct title anchors   -> up to 55 pts
  - Citation bonus (log-scaled)                            -> up to 12 pts
  - Recency bonus (papers <=3 years old)                   -> up to 18 pts
  - Topic breadth bonus (multiple tags hit)                -> up to 6 pts
  - Target-journal quality badge                           -> up to 4 pts
  - Adjacent/noisy-topic penalty                           -> up to -24 pts
"""

import logging
import math
from datetime import date
from typing import Dict, List

log = logging.getLogger(__name__)

CURRENT_YEAR = date.today().year

TIER_BASE = {
    "mechanism_linked": 34.0,
    "core": 34.0,
    "adjacent": 8.0,
    "exclude": 0.0,
}


def _split_field(paper: Dict, field: str) -> List[str]:
    return [item.strip() for item in str(paper.get(field) or "").split(";") if item.strip()]


def _topic_score(paper: Dict) -> float:
    """Topic tier dominates ranking so broad recency/citation signals cannot win alone."""
    tier = str(paper.get("topic_tier") or "").strip().lower()
    base = TIER_BASE.get(tier, 0.0)
    title_anchors = _split_field(paper, "matched_title_anchor_terms")
    core = _split_field(paper, "matched_core_terms")
    paradigms = _split_field(paper, "matched_paradigm_terms")
    mechanisms = _split_field(paper, "matched_mechanism_terms")

    title_bonus = 14.0 if title_anchors else 0.0
    anchor_bonus = min(len(core) * 2.5, 8.0) + min(len(paradigms) * 4.0, 8.0)
    mechanism_bonus = min(len(mechanisms) * 1.0, 4.0) if tier == "mechanism_linked" else 0.0
    abstract_only_penalty = 5.0 if tier in {"core", "mechanism_linked"} and not title_anchors else 0.0
    return min(max(base + title_bonus + anchor_bonus + mechanism_bonus - abstract_only_penalty, 0.0), 55.0)


def _citation_bonus(paper: Dict) -> float:
    """Log-scaled citation bonus, max 12 pts."""
    c = paper.get("citation_count")
    if not c or c <= 0:
        return 0.0
    return min(math.log10(c + 1) * 4.0, 12.0)


def _recency_bonus(paper: Dict) -> float:
    """Bonus for papers published <=3 years ago, max 18 pts."""
    try:
        year = int(str(paper.get("year", "") or "")[:4])
        age = CURRENT_YEAR - year
        if age <= 0:
            return 18.0
        if age <= 1:
            return 15.0
        if age <= 2:
            return 9.0
        if age <= 3:
            return 4.0
        return 0.0
    except (ValueError, TypeError):
        return 0.0


def _breadth_bonus(paper: Dict) -> float:
    """Bonus for hitting multiple topic tags, max 6 pts."""
    tags = _split_field(paper, "topic_tags")
    return min(len(tags) * 1.5, 6.0)


def _quality_bonus(paper: Dict) -> float:
    return 4.0 if paper.get("is_high_quality") else 0.0


def _noise_penalty(paper: Dict) -> float:
    soft = _split_field(paper, "matched_soft_exclude_terms")
    hard = _split_field(paper, "matched_hard_exclude_terms")
    penalty = min(len(soft) * 5.0, 20.0)
    if hard and str(paper.get("topic_tier") or "") in {"core", "mechanism_linked"}:
        penalty = min(penalty + 10.0, 24.0)
    return penalty


def _score_components(paper: Dict) -> Dict[str, float]:
    topic = _topic_score(paper)
    cit = _citation_bonus(paper)
    rec = _recency_bonus(paper)
    br = _breadth_bonus(paper)
    quality = _quality_bonus(paper)
    penalty = _noise_penalty(paper)
    final = max(0.0, min(round(topic + cit + rec + br + quality - penalty, 1), 100.0))
    return {
        "topic": round(topic, 1),
        "keyword": round(topic, 1),  # Backward-compatible output column.
        "keyword_raw": round(topic + penalty, 1),
        "citation": round(cit, 1),
        "recency": round(rec, 1),
        "breadth": round(br, 1),
        "quality": round(quality, 1),
        "penalty": round(penalty, 1),
        "final": final,
    }


def _selection_reason(paper: Dict, components: Dict[str, float]) -> str:
    parts = [
        "score {final:.1f}: topic {topic:.1f}/55, citations {citation:.1f}/12, recency {recency:.1f}/18, breadth {breadth:.1f}/6, quality {quality:.1f}/4, penalty -{penalty:.1f}".format(**components)
    ]
    if paper.get("topic_tier"):
        parts.append(f"topic tier: {paper.get('topic_tier')}")
    if paper.get("matched_title_anchor_terms"):
        parts.append("title anchor: " + str(paper.get("matched_title_anchor_terms")))
    if paper.get("topic_reason"):
        parts.append(str(paper.get("topic_reason")))
    elif paper.get("filter_reason"):
        parts.append("filter passed because " + str(paper.get("filter_reason")))
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
        p["score_topic"] = components["topic"]
        p["score_keyword"] = components["keyword"]
        p["score_keyword_raw"] = components["keyword_raw"]
        p["score_citation"] = components["citation"]
        p["score_recency"] = components["recency"]
        p["score_breadth"] = components["breadth"]
        p["score_quality"] = components["quality"]
        p["score_penalty"] = components["penalty"]
        p["relevance_score"] = components["final"]
        p["score_breakdown"] = (
            f"topic={components['topic']:.1f}; "
            f"citation={components['citation']:.1f}; "
            f"recency={components['recency']:.1f}; "
            f"breadth={components['breadth']:.1f}; "
            f"quality={components['quality']:.1f}; "
            f"penalty=-{components['penalty']:.1f}"
        )
        p["selection_reason"] = _selection_reason(p, components)

    papers.sort(key=lambda x: -(x["relevance_score"] or 0))
    log.info(
        "Scoring complete. Top score: %.1f | Median: %.1f",
        papers[0]["relevance_score"] if papers else 0,
        papers[len(papers) // 2]["relevance_score"] if papers else 0,
    )
    return papers
