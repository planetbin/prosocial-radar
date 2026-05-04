"""Candidate source orchestration for the radar pipeline."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List

from . import config
from .openalex import fetch_source_papers as fetch_openalex_source_papers
from .pubmed import fetch_details as fetch_pubmed_details
from .pubmed import get_all_pmids

log = logging.getLogger(__name__)


def _normalise_sources(enabled_sources: str | Iterable[str] | None = None) -> List[str]:
    if enabled_sources is None or enabled_sources == "":
        raw = config.SOURCE_ENABLED
    elif isinstance(enabled_sources, str):
        raw = enabled_sources.replace(";", ",").split(",")
    else:
        raw = list(enabled_sources)

    seen, result = set(), []
    for source in raw:
        key = str(source or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _mark_source_defaults(papers: List[Dict], source: str) -> List[Dict]:
    for paper in papers:
        paper.setdefault("source", source)
        if source == "pubmed":
            paper.setdefault("source_id", paper.get("pmid", ""))
        paper.setdefault("source_query", "")
        paper.setdefault("openalex_id", "")
        paper.setdefault("indexed_in", "")
    return papers


def fetch_candidate_papers(max_results: int | None = None, enabled_sources: str | Iterable[str] | None = None) -> Dict[str, object]:
    """Fetch raw candidate papers from all enabled sources.

    PubMed remains the biomedical baseline. OpenAlex broadens coverage into
    psychology, social science, and computational modeling literature.
    """
    sources = _normalise_sources(enabled_sources)
    papers: List[Dict] = []
    counts: Dict[str, int] = {}
    details: Dict[str, object] = {"enabled": sources, "counts": counts, "errors": []}

    if "pubmed" in sources:
        pmids = get_all_pmids(max_results=max_results)
        counts["pubmed_pmids"] = len(pmids)
        if pmids:
            pubmed_papers = _mark_source_defaults(fetch_pubmed_details(pmids), "pubmed")
            counts["pubmed_details"] = len(pubmed_papers)
            papers.extend(pubmed_papers)
        else:
            counts["pubmed_details"] = 0
            details["errors"].append("PubMed returned no PMIDs")

    if "openalex" in sources:
        openalex_papers = fetch_openalex_source_papers(max_results=max_results)
        counts["openalex_details"] = len(openalex_papers)
        papers.extend(_mark_source_defaults(openalex_papers, "openalex"))

    unsupported = [source for source in sources if source not in {"pubmed", "openalex"}]
    if unsupported:
        details["errors"].append("Unsupported sources: " + ", ".join(unsupported))
        log.warning("Unsupported candidate sources ignored: %s", ", ".join(unsupported))

    counts["raw_total"] = len(papers)
    log.info("Candidate sources complete: %s", counts)
    details["papers"] = papers
    return details
