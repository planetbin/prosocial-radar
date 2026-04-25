"""
PubMed fetch pipeline.

Two-channel strategy:
  1. sort=pub+date  → latest papers
  2. sort=relevance → most relevant papers

Results are merged and deduplicated by PMID.
"""

import time
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict

import requests

from .config import (
    PUBMED_SEARCH, PUBMED_FETCH,
    PUBMED_QUERY, MAX_RESULTS, FETCH_BATCH, REQUEST_DELAY,
    RECENT_DAYS, MAX_AGE_DAYS,
)

log = logging.getLogger(__name__)


# ─── Search ───────────────────────────────────────────────────────────────────

def _search_pmids(sort: str, retmax: int = MAX_RESULTS,
                  recent_only: bool = False) -> List[str]:
    """
    Return a list of PMIDs for the configured query.

    recent_only=True  → restrict to papers published within RECENT_DAYS days
                        (used for the pub+date channel to guarantee daily freshness)
    recent_only=False → restrict to papers published within MAX_AGE_DAYS days (3 years)
    """
    params = {
        "db":      "pubmed",
        "term":    PUBMED_QUERY,
        "retmax":  retmax,
        "retmode": "json",
        "sort":    sort,
        "reldate": RECENT_DAYS if recent_only else MAX_AGE_DAYS,
        "datetype": "pdat",
    }

    try:
        r = requests.get(PUBMED_SEARCH, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])
        days  = RECENT_DAYS if recent_only else MAX_AGE_DAYS
        log.info("PubMed [sort=%s,reldate=%dd] → %d PMIDs found", sort, days, len(pmids))
        return pmids
    except Exception as exc:
        log.error("PubMed search failed (sort=%s): %s", sort, exc)
        return []


def get_all_pmids() -> List[str]:
    """
    Three-channel search, merged & deduplicated:
      1. pub+date + reldate=RECENT_DAYS  → guaranteed fresh papers
      2. pub+date (all time)             → recent high-volume
      3. relevance (all time)            → classic high-relevance papers
    """
    recent    = _search_pmids("pub+date", recent_only=True)
    by_date   = _search_pmids("pub+date", recent_only=False)
    by_rel    = _search_pmids("relevance", recent_only=False)

    # Prioritise: recent first, then by_date, then relevance
    seen, merged = set(), []
    for pmid in recent + by_date + by_rel:
        if pmid not in seen:
            seen.add(pmid)
            merged.append(pmid)
    log.info("Total unique PMIDs after merge: %d", len(merged))
    return merged


# ─── Fetch & Parse XML ────────────────────────────────────────────────────────

def _text(elem, path: str, default: str = "") -> str:
    node = elem.find(path)
    return (node.text or "").strip() if node is not None else default


def _parse_article(article_elem) -> Dict:
    """Extract fields from a <PubmedArticle> XML element."""
    medline = article_elem.find(".//MedlineCitation")
    if medline is None:
        return {}

    pmid = _text(medline, "PMID")

    art = medline.find("Article")
    if art is None:
        return {}

    title    = _text(art, "ArticleTitle")
    abstract = " ".join(
        (n.text or "").strip()
        for n in art.findall(".//AbstractText")
    )

    # Authors
    authors = []
    for author in art.findall(".//Author"):
        last  = _text(author, "LastName")
        fore  = _text(author, "ForeName")
        name  = f"{last} {fore}".strip() if last else _text(author, "CollectiveName")
        if name:
            authors.append(name)
    authors_str = "; ".join(authors[:6])
    if len(authors) > 6:
        authors_str += " et al."

    # Journal
    journal = _text(art, "Journal/Title") or _text(art, "Journal/ISOAbbreviation")

    # Year
    year = (
        _text(art, "Journal/JournalIssue/PubDate/Year")
        or _text(art, "Journal/JournalIssue/PubDate/MedlineDate")[:4]
    )

    # DOI
    doi = ""
    for eid in art.findall(".//ELocationID"):
        if eid.get("EIdType") == "doi":
            doi = (eid.text or "").strip()
            break
    # Fallback: ArticleIdList
    if not doi:
        for aid in article_elem.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                doi = (aid.text or "").strip()
                break

    # MeSH keywords
    keywords = [
        _text(kw, "DescriptorName") or (kw.find("DescriptorName").text if kw.find("DescriptorName") is not None else "")
        for kw in medline.findall(".//MeshHeading")
    ]
    keywords_str = "; ".join(filter(None, keywords))

    url     = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    doi_url = f"https://doi.org/{doi}" if doi else ""

    return {
        "pmid":        pmid,
        "title":       title,
        "abstract":    abstract,
        "authors":     authors_str,
        "year":        year,
        "journal":     journal,
        "doi":         doi,
        "url":         url,
        "doi_url":     doi_url,
        "keywords":    keywords_str,
    }


def fetch_details(pmids: List[str]) -> List[Dict]:
    """Fetch and parse detailed metadata for a list of PMIDs."""
    papers = []
    total  = len(pmids)

    for i in range(0, total, FETCH_BATCH):
        batch = pmids[i:i + FETCH_BATCH]
        log.info("Fetching details: batch %d-%d / %d", i + 1, i + len(batch), total)

        params = {
            "db":      "pubmed",
            "id":      ",".join(batch),
            "rettype": "xml",
            "retmode": "xml",
        }
        try:
            r = requests.get(PUBMED_FETCH, params=params, timeout=60)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            for article in root.findall(".//PubmedArticle"):
                parsed = _parse_article(article)
                if parsed.get("pmid"):
                    papers.append(parsed)
        except Exception as exc:
            log.error("Fetch batch %d failed: %s", i, exc)

        time.sleep(REQUEST_DELAY)

    log.info("Fetched details for %d papers", len(papers))
    return papers
