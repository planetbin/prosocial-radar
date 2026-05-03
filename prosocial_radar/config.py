"""
Configuration constants for the Prosocial Research Radar system.

Most project-specific settings come from profiles/*.yml. Environment variables
can still override operational values in GitHub Actions or local runs.
"""

from __future__ import annotations

import os
from typing import Any, Iterable

from .profile import load_profile


PROFILE = load_profile()
PROFILE_NAME = str(PROFILE.get("name") or os.environ.get("RADAR_PROFILE") or "default")
PROFILE_PATH = str(PROFILE.get("__path__", ""))


def _get(path: str, default: Any = None) -> Any:
    node: Any = PROFILE
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value if value else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return int(default)
    try:
        return int(value)
    except ValueError:
        return int(default)


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name, "").strip()
    if not value:
        return float(default)
    try:
        return float(value)
    except ValueError:
        return float(default)


def _as_list(value: Any, default: Iterable[str]) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _env_list(name: str, default: Iterable[str]) -> list[str]:
    value = os.environ.get(name, "").strip()
    if not value:
        return list(default)
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


# PubMed API
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_SEARCH = f"{PUBMED_BASE}/esearch.fcgi"
PUBMED_FETCH = f"{PUBMED_BASE}/efetch.fcgi"

DEFAULT_PUBMED_QUERY = (
    "(prosocial[tiab] OR altruism[tiab] OR altruistic[tiab] OR empathy[tiab] OR "
    '"charitable giving"[tiab] OR "social decision making"[tiab] OR '
    '"trust game"[tiab] OR "dictator game"[tiab] OR "ultimatum game"[tiab] OR '
    '"public goods game"[tiab] OR "cooperation"[tiab] OR "helping behavior"[tiab])'
    " AND (development[tiab] OR child*[tiab] OR adolescent*[tiab] OR "
    'fMRI[tiab] OR "functional MRI"[tiab] OR EEG[tiab] OR neuroimaging[tiab] OR '
    '"neural"[tiab] OR "brain"[tiab])'
)

FETCH_BATCH = _env_int("PUBMED_FETCH_BATCH", _get("pubmed.fetch_batch", 100))
MAX_RESULTS = _env_int("RADAR_MAX_RESULTS", _get("pubmed.max_results", 200))
RECENT_DAYS = _env_int("RADAR_RECENT_DAYS", _get("pubmed.recent_days", 90))
MAX_AGE_DAYS = _env_int("RADAR_MAX_AGE_DAYS", _get("pubmed.max_age_days", 1095))
REQUEST_DELAY = _env_float("RADAR_REQUEST_DELAY", _get("pubmed.request_delay", 0.5))
PUBMED_QUERY = _env_str("PUBMED_QUERY", str(_get("pubmed.query", DEFAULT_PUBMED_QUERY)))

# OpenAlex API
OPENALEX_BASE = "https://api.openalex.org/works"
OA_EMAIL = _env_str("OPENALEX_EMAIL", str(_get("openalex.polite_pool_email", "research-radar@example.com")))
OA_BATCH = _env_int("OPENALEX_BATCH", _get("openalex.batch_size", 50))

# Delivery
EMAIL_RECIPIENTS = _env_list(
    "RADAR_RECIPIENTS",
    _as_list(_get("email.recipients"), ["duo12.li@connect.polyu.hk"]),
)

# AI summary behavior
SUMMARY_MAX_ABSTRACT_CHARS = _env_int(
    "SUMMARY_MAX_ABSTRACT_CHARS",
    _get("summary.max_abstract_chars", 2500),
)

# Target journals mark high-quality papers; they are not a hard filter.
TARGET_JOURNALS = {
    journal.lower().strip()
    for journal in _as_list(
        _get("target_journals"),
        [
            "psychological science",
            "journal of personality and social psychology",
            "journal of neuroscience",
            "neuroimage",
            "social cognitive and affective neuroscience",
            "developmental science",
            "child development",
            "cerebral cortex",
            "biological psychology",
            "neuropsychologia",
            "nature human behaviour",
            "pnas",
            "proceedings of the national academy of sciences",
            "science",
            "nature",
            "current biology",
            "journal of experimental psychology: general",
            "cognition",
            "psychological review",
            "trends in cognitive sciences",
            "developmental psychology",
            "plos one",
            "journal of experimental child psychology",
        ],
    )
    if journal.strip()
}

TIER_A = _as_list(_get("filters.tier_a"), [r"\bprosocial\b", r"\baltruism\b", r"\bempathy\b"])
TIER_B = _as_list(_get("filters.tier_b"), [r"\bdevelopment\b", r"\bneural\b", r"\bbehavior\b"])
TAG_RULES = {
    str(tag): _as_list(patterns, [])
    for tag, patterns in (_get("filters.tag_rules", {}) or {}).items()
}
