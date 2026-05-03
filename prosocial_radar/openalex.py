"""
OpenAlex citation supplement.

Given a list of papers with DOI values, query OpenAlex in batches to retrieve
citation counts and append them to the paper dictionaries.
"""

import logging
import time
from typing import Dict, List

import requests

from . import config

log = logging.getLogger(__name__)


def _build_filter(dois: List[str]) -> str:
    """Build an OpenAlex DOI filter string: doi:10.xxx|10.yyy."""
    if not dois:
        return ""
    return "doi:" + "|".join(dois)


def enrich_with_citations(papers: List[Dict]) -> List[Dict]:
    """For papers with DOI, query OpenAlex for citation counts."""
    doi_index: Dict[str, Dict] = {}
    for p in papers:
        if p.get("doi"):
            doi_index[p["doi"].lower().strip()] = p

    dois = list(doi_index.keys())
    log.info("Querying OpenAlex for %d DOIs", len(dois))

    for i in range(0, len(dois), config.OA_BATCH):
        batch = dois[i:i + config.OA_BATCH]
        log.info("  OpenAlex batch %d-%d / %d", i + 1, i + len(batch), len(dois))

        params = {
            "filter": _build_filter(batch),
            "select": "doi,cited_by_count",
            "per-page": config.OA_BATCH,
            "mailto": config.OA_EMAIL,
        }
        try:
            r = requests.get(config.OPENALEX_BASE, params=params, timeout=30)
            r.raise_for_status()
            results = r.json().get("results", [])
            for item in results:
                raw_doi = (item.get("doi") or "").replace("https://doi.org/", "").lower().strip()
                count = item.get("cited_by_count")
                if raw_doi in doi_index:
                    doi_index[raw_doi]["citation_count"] = count
        except Exception as exc:
            log.error("OpenAlex batch %d failed: %s", i, exc)

        time.sleep(config.REQUEST_DELAY)

    for p in papers:
        p.setdefault("citation_count", None)

    log.info("Citation enrichment complete.")
    return papers
