"""Rule-based evidence stratification for literature screening."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Tuple

Signal = Tuple[str, str]

LOW_SIGNAL_RULES: List[Signal] = [
    (r"\bstudy protocol\b|\btrial protocol\b|\bprotocol for\b", "study protocol"),
    (r"\beditorial\b|\bcommentary\b|\bcomment\b", "editorial/commentary"),
    (r"\bletter\b|\bletter to the editor\b", "letter"),
    (r"\bcorrection\b|\bcorrigendum\b|\berratum\b", "correction/erratum"),
    (r"\bnews\b|\bnewspaper article\b", "news item"),
    (r"\bcase report\b|\bcase reports\b|\bcase series\b", "case report"),
]

NONHUMAN_SIGNALS: List[Signal] = [
    (r"\bmice\b|\bmouse\b|\brat\b|\brats\b|\brodent\b", "rodent sample"),
    (r"\bmonkey\b|\bmonkeys\b|\bmacaque\b|\bmarmoset\b", "nonhuman primate sample"),
    (r"\bchimpanzee\b|\bchimpanzees\b|\bbonobo\b|\bbonobos\b", "ape sample"),
    (r"\bvole\b|\bvoles\b|\banimal model\b", "nonhuman animal model"),
]

HUMAN_SIGNALS: List[Signal] = [
    (r"\bhuman\b|\bhumans\b", "human sample"),
    (r"\bparticipant\b|\bparticipants\b|\bsubjects\b", "participants"),
    (r"\badult\b|\badults\b|\bstudents\b|\bchildren\b|\badolescents\b|\bpatients\b", "human group"),
    (r"\bsurvey\b|\bquestionnaire\b|\bself-report\b|\binterview\b", "human measures"),
]

EVIDENCE_RULES = [
    {
        "type": "evidence_synthesis",
        "level": "L1 evidence synthesis",
        "score": 5.0,
        "signals": [
            (r"\bmeta-analysis\b|\bmeta analysis\b", "meta-analysis"),
            (r"\bsystematic review\b", "systematic review"),
            (r"\bumbrella review\b", "umbrella review"),
            (r"\bscoping review\b", "scoping review"),
            (r"\breview\b", "review"),
        ],
    },
    {
        "type": "causal_experimental",
        "level": "L2 causal/experimental",
        "score": 10.0,
        "signals": [
            (r"\brandomi[sz]ed\b|\brandomised\b", "randomized design"),
            (r"\brandomized controlled trial\b|\bcontrolled trial\b", "controlled trial"),
            (r"\bexperiment\b|\bexperimental\b|\bfield experiment\b", "experimental design"),
            (r"\bintervention\b|\btraining\b", "intervention"),
            (r"\bcausal\b", "causal inference"),
        ],
    },
    {
        "type": "longitudinal_cohort",
        "level": "L3 longitudinal/cohort",
        "score": 7.0,
        "signals": [
            (r"\blongitudinal\b", "longitudinal design"),
            (r"\bcohort\b|\bprospective\b", "cohort/prospective design"),
            (r"\bfollow-up\b|\bfollow up\b|\bpanel study\b", "follow-up/panel design"),
            (r"\bcross-lagged\b|\bgrowth curve\b", "developmental longitudinal model"),
        ],
    },
    {
        "type": "empirical_human",
        "level": "L4 human empirical",
        "score": 4.0,
        "signals": [
            (r"\bcross-sectional\b|\bcorrelational\b", "observational empirical design"),
            (r"\bsurvey\b|\bquestionnaire\b|\bself-report\b", "survey/self-report"),
            (r"\bparticipant\b|\bparticipants\b|\bsample of\b|\bn\s*=\s*\d+", "reported sample"),
            (r"\bfmri\b|\bfunctional mri\b|\beeg\b|\bneuroimaging\b", "human neuroscience measure"),
            (r"\btask\b|\bgame\b|\bdictator game\b|\btrust game\b|\bpublic goods game\b", "behavioral task"),
        ],
    },
    {
        "type": "computational_method",
        "level": "L5 computational/method",
        "score": 1.0,
        "signals": [
            (r"\bcomputational\b|\bmodel\b|\bmodeling\b|\bmodelling\b", "computational model"),
            (r"\bsimulation\b|\bagent-based\b", "simulation"),
            (r"\bmachine learning\b|\bclassification model\b", "machine learning"),
            (r"\bdataset\b|\bdatabase\b|\bmethod\b|\bscale development\b", "method/resource"),
        ],
    },
]

DEFAULT_RESULT = {
    "evidence_level": "L5 unclear evidence",
    "evidence_type": "unclear",
    "evidence_decision": "passed",
    "evidence_reason": "no strong design signal detected; retained with a small evidence penalty",
    "evidence_score_adjustment": -2.0,
}


def _text(paper: Dict, fields: Iterable[str]) -> str:
    return " ".join(str(paper.get(field) or "") for field in fields).lower()


def _matched(signals: Iterable[Signal], text: str) -> List[str]:
    labels: List[str] = []
    for pattern, label in signals:
        if re.search(pattern, text, re.IGNORECASE) and label not in labels:
            labels.append(label)
    return labels


def _result(level: str, typ: str, decision: str, reason: str, score: float) -> Dict:
    return {
        "evidence_level": level,
        "evidence_type": typ,
        "evidence_decision": decision,
        "evidence_reason": reason,
        "evidence_score_adjustment": round(score, 1),
    }


def classify_evidence(paper: Dict) -> Dict:
    """Classify one paper into an evidence tier and retention decision."""
    title_and_type = _text(paper, ["title", "publication_types"])
    body_text = _text(paper, ["title", "abstract", "keywords", "publication_types"])
    abstract = str(paper.get("abstract") or "").strip()

    low_matches = _matched(LOW_SIGNAL_RULES, title_and_type)
    if low_matches:
        return _result(
            "L6 low evidence",
            "low_signal_publication",
            "filtered_out",
            "publication type is low screening value: " + ", ".join(low_matches[:4]),
            -25.0,
        )

    if not abstract:
        return _result(
            "L6 low evidence",
            "no_abstract",
            "filtered_out",
            "no abstract available for efficient screening",
            -20.0,
        )

    synthesis_rule = EVIDENCE_RULES[0]
    synthesis_matches = _matched(synthesis_rule["signals"], title_and_type)
    if synthesis_matches:
        return _result(
            synthesis_rule["level"],
            synthesis_rule["type"],
            "passed",
            "matched evidence signal: " + ", ".join(synthesis_matches[:4]),
            float(synthesis_rule["score"]),
        )

    nonhuman = _matched(NONHUMAN_SIGNALS, body_text)
    human = _matched(HUMAN_SIGNALS, body_text)
    if nonhuman and not human:
        return _result(
            "L5 nonhuman empirical",
            "nonhuman_empirical",
            "passed",
            "nonhuman empirical signal: " + ", ".join(nonhuman[:3]),
            -1.0,
        )

    for rule in EVIDENCE_RULES[1:]:
        matches = _matched(rule["signals"], body_text)
        if matches:
            return _result(
                rule["level"],
                rule["type"],
                "passed",
                "matched evidence signal: " + ", ".join(matches[:4]),
                float(rule["score"]),
            )

    return DEFAULT_RESULT.copy()


def annotate_evidence(paper: Dict) -> Dict:
    """Attach evidence tier fields to a paper dictionary."""
    paper.update(classify_evidence(paper))
    return paper
