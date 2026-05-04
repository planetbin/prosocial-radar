"""Research-profile alignment for the prosocial radar.

The rules here are intentionally abstract. They encode public research themes
rather than private manuscript details: aging/lifespan prosociality, helping,
sharing, comforting, cost/familiarity mechanisms, measurement, attention, and
neural decision mechanisms.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Tuple


TAG_RULES: list[tuple[str, float, list[str]]] = [
    (
        "aging_prosociality",
        7.0,
        [
            r"\bolder adults?\b",
            r"\baging\b",
            r"\bageing\b",
            r"\belderly\b",
            r"\blate[- ]life\b",
            r"\blifespan\b",
            r"\blife span\b",
            r"\bgerontolog\w*\b",
        ],
    ),
    (
        "age_comparison",
        4.0,
        [
            r"\byounger and older\b",
            r"\byoung and older\b",
            r"\bage difference\w*\b",
            r"\bage-related\b",
            r"\bage group\w*\b",
            r"\bage comparison\w*\b",
        ],
    ),
    ("helping_decision", 5.0, [r"\bhelping\b", r"\bhelping behavior\b", r"\bdecid\w* to help\b", r"\bprosocial decision\w*\b"]),
    ("sharing", 4.0, [r"\bsharing\b", r"\bresource sharing\b", r"\bshare resources\b"]),
    ("comforting", 4.0, [r"\bcomforting\b", r"\bcomfort\b", r"\bemotional support\b", r"\bconsole\w*\b"]),
    (
        "cost_mechanism",
        4.0,
        [
            r"\bcost\w*\b",
            r"\bcost-benefit\b",
            r"\beffort\w*\b",
            r"\btrade[- ]off\w*\b",
            r"\bsacrifice\w*\b",
            r"\bopportunity cost\w*\b",
        ],
    ),
    (
        "familiarity_mechanism",
        4.0,
        [
            r"\bfamiliar\w*\b",
            r"\bstranger\w*\b",
            r"\bclose other\w*\b",
            r"\bsocial distance\b",
            r"\btarget familiarity\b",
            r"\bkin\b",
        ],
    ),
    (
        "ses_resource_mechanism",
        4.0,
        [
            r"\bsocioeconomic\b",
            r"\bSES\b",
            r"\bincome\b",
            r"\bwealth\b",
            r"\bresource\w*\b",
            r"\bfinancial\b",
        ],
    ),
    (
        "value_based_decision",
        5.0,
        [
            r"\bvalue[- ]based\b",
            r"\bsubjective value\b",
            r"\butility\b",
            r"\breward\w*\b",
            r"\bsocial preference\w*\b",
            r"\bdecision value\b",
        ],
    ),
    (
        "attentional_mechanism",
        6.0,
        [
            r"\battention\b",
            r"\battentional\b",
            r"\bgaze\b",
            r"\beye[- ]tracking\b",
            r"\bvisual attention\b",
            r"\bsalience\b",
        ],
    ),
    (
        "neural_mechanism",
        6.0,
        [
            r"\bneural\b",
            r"\bbrain\b",
            r"\bfMRI\b",
            r"\bfunctional MRI\b",
            r"\bEEG\b",
            r"\bTPJ\b",
            r"\btemporoparietal\b",
            r"\bvmPFC\b",
            r"\bventromedial prefrontal\b",
            r"\bSocial Cognitive and Affective Neuroscience\b",
        ],
    ),
    (
        "measurement_validation",
        4.0,
        [
            r"\bvalidation\b",
            r"\bvalidat\w*\b",
            r"\bscale\b",
            r"\bscale development\b",
            r"\binstrument development\b",
            r"\bmeasure development\b",
        ],
    ),
    (
        "picture_vignette_method",
        5.0,
        [
            r"\bpicture[- ]based\b",
            r"\bpicture\w*\b",
            r"\bvignette\w*\b",
            r"\bscenario\w*\b",
            r"\becological validity\b",
        ],
    ),
    (
        "psychometrics",
        5.0,
        [
            r"\bpsychometric\w*\b",
            r"\bfactor analysis\b",
            r"\bconfirmatory factor\b",
            r"\bexploratory factor\b",
            r"\bCFA\b",
            r"\bEFA\b",
            r"\bmeasurement invariance\b",
            r"\breliability\b",
        ],
    ),
    ("meta_analysis", 5.0, [r"\bmeta-analysis\b", r"\bmeta analysis\b", r"\bsystematic review\b", r"\bscoping review\b"]),
    ("mediation_moderation", 3.0, [r"\bmediation\b", r"\bmediator\w*\b", r"\bmoderation\b", r"\bmoderator\w*\b"]),
    (
        "computational_modeling_bridge",
        6.0,
        [
            r"\bcomputational model\w*\b",
            r"\bcomputational modelling\b",
            r"\breinforcement learning\b",
            r"\bdrift[- ]diffusion\b",
            r"\bBayesian model\b",
            r"\butility model\b",
            r"\bchoice model\b",
            r"\bmodel[- ]based\b",
        ],
    ),
]

PERIPHERAL_PATTERNS = [
    r"\blocal government\b",
    r"\bpublic administration\b",
    r"\bpublic policy\b",
    r"\bnonprofit sector\b",
    r"\bvoluntary sector\b",
    r"\bwillingness to donate\b",
    r"\bsocial capital\b",
    r"\bhometown tax\b",
    r"\bpublic economics\b",
    r"\bprobit model\b",
    r"\bordered probit\b",
]

PSYCH_JOURNAL_PATTERNS = [
    r"psycholog",
    r"gerontolog",
    r"neuroscience",
    r"cognition",
    r"cognitive",
    r"decision",
    r"human behaviour",
    r"human behavior",
    r"acta psychologica",
]


def _text(paper: Dict) -> str:
    return " ".join(
        str(paper.get(field) or "")
        for field in ("title", "abstract", "keywords", "journal", "publication_types")
    )


def _matches(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _join(values: Iterable[str]) -> str:
    return "; ".join(dict.fromkeys(v for v in values if v))


def _existing_tags(paper: Dict) -> set[str]:
    return {tag.strip().lower() for tag in str(paper.get("topic_tags") or "").split(";") if tag.strip()}


def _score_tags(text: str) -> Tuple[List[str], float]:
    tags: List[str] = []
    score = 0.0
    for tag, weight, patterns in TAG_RULES:
        if _matches(patterns, text):
            tags.append(tag)
            score += weight
    return tags, min(score, 34.0)


def _peripheral_penalty(paper: Dict, tags: List[str], text: str) -> float:
    topic_tags = _existing_tags(paper)
    tagset = set(tags)
    strong_profile_anchor = bool(
        tagset
        & {
            "aging_prosociality",
            "age_comparison",
            "cost_mechanism",
            "familiarity_mechanism",
            "value_based_decision",
            "attentional_mechanism",
            "neural_mechanism",
            "computational_modeling_bridge",
        }
    )
    method_anchor = bool(
        (tagset & {"measurement_validation", "psychometrics", "picture_vignette_method", "meta_analysis"})
        and (tagset & {"aging_prosociality", "helping_decision", "sharing", "comforting"})
    )
    penalty = 0.0
    if _matches(PERIPHERAL_PATTERNS, text) and not (strong_profile_anchor or method_anchor):
        penalty += 9.0
    if re.search(r"\b(charitable giving|donat\w*)\b", text, re.IGNORECASE) and not (
        tagset & {"aging_prosociality", "helping_decision", "sharing", "comforting", "neural_mechanism", "attentional_mechanism"}
    ):
        penalty += 5.0
    if "altruism" in topic_tags and not ({"aging_prosociality", "helping_decision", "sharing", "comforting"} & tagset):
        penalty += 2.0
    return min(penalty, 14.0)


def _section(tags: List[str], penalty: float) -> str:
    tagset = set(tags)
    if "aging_prosociality" in tagset:
        return "aging_lifespan"
    if {"neural_mechanism", "attentional_mechanism"} & tagset:
        return "neural_attention"
    if {"measurement_validation", "psychometrics", "picture_vignette_method", "meta_analysis"} & tagset:
        return "measurement_methods"
    if "computational_modeling_bridge" in tagset:
        return "computational_modeling"
    if {"cost_mechanism", "familiarity_mechanism", "ses_resource_mechanism", "value_based_decision"} & tagset:
        return "mechanism_leads"
    if penalty:
        return "peripheral_watch"
    return "general_prosocial"


def _takeaway(tags: List[str], paper: Dict, penalty: float) -> str:
    tagset = set(tags)
    if "aging_prosociality" in tagset and {"helping_decision", "sharing", "comforting"} & tagset:
        return "Directly relevant to aging/lifespan prosociality and behavior-specific differences in helping, sharing, or comforting."
    if {"neural_mechanism", "attentional_mechanism"} & tagset and {"helping_decision", "sharing", "comforting"} & tagset:
        return "Useful for the neural or attentional mechanism line linking perception, attention, and prosocial decisions."
    if {"measurement_validation", "psychometrics", "picture_vignette_method"} & tagset:
        return "Useful for measurement work, especially ecological or picture/vignette-based assessment of prosociality."
    if "meta_analysis" in tagset:
        return "Useful as synthesis material for mapping age-related or mechanism-related prosocial evidence."
    if "computational_modeling_bridge" in tagset and {"value_based_decision", "cost_mechanism"} & tagset:
        return "Good bridge candidate for computational accounts of cost-benefit or value-based prosocial decisions."
    if {"cost_mechanism", "familiarity_mechanism", "ses_resource_mechanism", "value_based_decision"} & tagset:
        return "Mechanism-relevant: may inform cost, familiarity, resources, or value-based explanations of prosocial behavior."
    if {"helping_decision", "sharing", "comforting"} & tagset:
        return "Behaviorally relevant because it separates concrete prosocial actions rather than treating prosociality as a broad label."
    if penalty:
        return "Peripheral to the main psychology profile; keep only if the policy or applied context is strategically useful."
    return "General prosociality paper; inspect if the title, sample, or method fits current reading priorities."


def annotate_research_profile(paper: Dict) -> Dict:
    """Attach profile-fit fields used for ranking, output, and email grouping."""
    text = _text(paper)
    tags, raw_score = _score_tags(text)
    journal = str(paper.get("journal") or "")
    if _matches(PSYCH_JOURNAL_PATTERNS, journal):
        raw_score = min(raw_score + 2.0, 34.0)
        if "psychology_priority" not in tags:
            tags.append("psychology_priority")

    penalty = _peripheral_penalty(paper, tags, text)
    adjustment = round(min(raw_score * 0.55, 18.0) - penalty, 1)

    paper["research_use_tags"] = _join(tags)
    paper["research_alignment_score"] = round(raw_score, 1)
    paper["research_alignment_penalty"] = round(penalty, 1)
    paper["research_alignment_adjustment"] = adjustment
    paper["research_alignment_reason"] = (
        f"profile tags: {paper['research_use_tags'] or 'none'}; "
        f"fit={raw_score:.1f}/34; peripheral_penalty=-{penalty:.1f}; score_adjustment={adjustment:+.1f}"
    )
    paper["research_takeaway"] = _takeaway(tags, paper, penalty)
    paper["email_section"] = _section(tags, penalty)
    return paper
