"""
OpenAlex citation supplement.

Given a list of papers (each with a 'doi' field), queries the OpenAlex API in
batches to retrieve citation counts and appends them to the paper dicts.
"""

import logging
import time
from typing import List, Dict

import requests

from .config import OPENALEX_BASE, OA_EMAIL, OA_BATCH, REQUEST_DELAY

log = logging.getLogger(__name__)


def _build_filter(dois: List[str]) -> str:
    """
    Build a DOI filter string for OpenAlex.
    Correct format: doi:10.xxx|10.yyy  (prefix appears only once)
    """
    if not dois:
        return ""
    # First DOI gets the 'doi:' prefix; subsequent ones are just DOI values
    return "doi:" + "|".join(dois)


def enrich_with_citations(papers: List[Dict]) -> List[Dict]:
    """
    For papers that have a DOI, query OpenAlex for citation_count.
    Papers without DOI get citation_count = None.
    Returns the enriched list.
    """
    # Index papers by DOI (lowercase) for fast lookup
    doi_index: Dict[str, Dict] = {}
    for p in papers:
        if p.get("doi"):
            doi_index[p["doi"].lower().strip()] = p

    dois = list(doi_index.keys())
    log.info("Querying OpenAlex for %d DOIs", len(dois))

    for i in range(0, len(dois), OA_BATCH):
        batch = dois[i:i + OA_BATCH]
        log.info("  OpenAlex batch %d-%d / %d", i + 1, i + len(batch), len(dois))

        params = {
            "filter":     _build_filter(batch),
            "select":     "doi,cited_by_count",
            "per-page":   OA_BATCH,
            "mailto":     OA_EMAIL,
        }
        try:
            r = requests.get(OPENALEX_BASE, params=params, timeout=30)
            r.raise_for_status()
            results = r.json().get("results", [])
            for item in results:
                raw_doi = (item.get("doi") or "").replace("https://doi.org/", "").lower().strip()
                count   = item.get("cited_by_count")
                if raw_doi in doi_index:
                    doi_index[raw_doi]["citation_count"] = count
        except Exception as exc:
            log.error("OpenAlex batch %d failed: %s", i, exc)

        time.sleep(REQUEST_DELAY)

    # Fill missing citation_count
    for p in papers:
        p.setdefault("citation_count", None)

    log.info("Citation enrichment complete.")
    return papers
