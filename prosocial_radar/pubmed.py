"""
PubMed fetch pipeline.

Three-channel strategy:
  1. sort=pub+date + recent window -> fresh papers
  2. sort=pub+date + max-age window -> recent high-volume papers
  3. sort=relevance + max-age window -> high-relevance papers

Results are merged and deduplicated by PMID.
"""

import logging
import time
import xml.etree.ElementTree as ET
from typing import Dict, List

import requests

from . import config

log = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
FALLBACK_BATCH_SIZE = 10


def _with_api_key(params: Dict) -> Dict:
    payload = dict(params)
    if config.NCBI_API_KEY:
        payload["api_key"] = config.NCBI_API_KEY
    return payload


def _retry_delay(response: requests.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), 1.0)
            except ValueError:
                pass
    return max(config.PUBMED_BACKOFF_SECONDS * attempt, 1.0)


def _get_with_retry(url: str, params: Dict, timeout: int, label: str) -> requests.Response:
    max_retries = max(int(config.PUBMED_MAX_RETRIES), 1)
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        response: requests.Response | None = None
        try:
            response = requests.get(url, params=_with_api_key(params), timeout=timeout)
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
                delay = _retry_delay(response, attempt)
                log.warning(
                    "PubMed %s returned HTTP %s; retrying in %.1fs (%d/%d)",
                    label,
                    response.status_code,
                    delay,
                    attempt,
                    max_retries,
                )
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            status = response.status_code if response is not None else None
            if status is not None and status not in RETRYABLE_STATUS_CODES:
                raise
            if attempt < max_retries:
                delay = _retry_delay(response, attempt)
                log.warning(
                    "PubMed %s failed: %s; retrying in %.1fs (%d/%d)",
                    label,
                    exc,
                    delay,
                    attempt,
                    max_retries,
                )
                time.sleep(delay)
                continue
            raise

    if last_error:
        raise last_error
    raise RuntimeError(f"PubMed {label} failed without a response")


def _search_pmids(sort: str, retmax: int | None = None, recent_only: bool = False) -> List[str]:
    """Return PMIDs for the configured query and date window."""
    result_limit = retmax if retmax is not None else config.MAX_RESULTS
    days = config.RECENT_DAYS if recent_only else config.MAX_AGE_DAYS
    params = {
        "db": "pubmed",
        "term": config.PUBMED_QUERY,
        "retmax": result_limit,
        "retmode": "json",
        "sort": sort,
        "reldate": days,
        "datetype": "pdat",
    }

    try:
        r = _get_with_retry(config.PUBMED_SEARCH, params=params, timeout=30, label=f"search sort={sort}")
        data = r.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])
        log.info("PubMed [sort=%s,reldate=%dd] -> %d PMIDs found", sort, days, len(pmids))
        return pmids
    except Exception as exc:
        log.error("PubMed search failed (sort=%s): %s", sort, exc)
        return []


def get_all_pmids(max_results: int | None = None) -> List[str]:
    """Run three PubMed searches, then merge and deduplicate PMIDs."""
    recent = _search_pmids("pub+date", retmax=max_results, recent_only=True)
    by_date = _search_pmids("pub+date", retmax=max_results, recent_only=False)
    by_rel = _search_pmids("relevance", retmax=max_results, recent_only=False)

    seen, merged = set(), []
    for pmid in recent + by_date + by_rel:
        if pmid not in seen:
            seen.add(pmid)
            merged.append(pmid)
    log.info("Total unique PMIDs after merge: %d", len(merged))
    return merged


def _text(elem, path: str, default: str = "") -> str:
    node = elem.find(path)
    return (node.text or "").strip() if node is not None else default


def _unique(values: List[str], limit: int | None = None) -> List[str]:
    seen, result = set(), []
    for value in values:
        text = " ".join((value or "").split())
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
            if limit and len(result) >= limit:
                break
    return result


def _parse_affiliations(author) -> List[str]:
    affiliations = []
    for node in author.findall(".//AffiliationInfo/Affiliation"):
        if node.text:
            affiliations.append(node.text)
    return _unique(affiliations)


def _parse_article(article_elem) -> Dict:
    """Extract fields from a <PubmedArticle> XML element."""
    medline = article_elem.find(".//MedlineCitation")
    if medline is None:
        return {}

    pmid = _text(medline, "PMID")
    art = medline.find("Article")
    if art is None:
        return {}

    title = _text(art, "ArticleTitle")
    abstract = " ".join((n.text or "").strip() for n in art.findall(".//AbstractText"))

    authors = []
    all_affiliations = []
    first_author_affiliations = []
    for idx, author in enumerate(art.findall(".//Author")):
        last = _text(author, "LastName")
        fore = _text(author, "ForeName")
        name = f"{last} {fore}".strip() if last else _text(author, "CollectiveName")
        if name:
            authors.append(name)

        author_affiliations = _parse_affiliations(author)
        all_affiliations.extend(author_affiliations)
        if idx == 0:
            first_author_affiliations = author_affiliations

    authors_str = "; ".join(authors[:6])
    if len(authors) > 6:
        authors_str += " et al."

    affiliations = _unique(all_affiliations, limit=8)
    affiliations_str = "; ".join(affiliations)
    if len(_unique(all_affiliations)) > len(affiliations):
        affiliations_str += "; et al."

    journal = _text(art, "Journal/Title") or _text(art, "Journal/ISOAbbreviation")
    year = _text(art, "Journal/JournalIssue/PubDate/Year") or _text(
        art, "Journal/JournalIssue/PubDate/MedlineDate"
    )[:4]

    doi = ""
    for eid in art.findall(".//ELocationID"):
        if eid.get("EIdType") == "doi":
            doi = (eid.text or "").strip()
            break
    if not doi:
        for aid in article_elem.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                doi = (aid.text or "").strip()
                break

    keywords = []
    for kw in medline.findall(".//MeshHeading"):
        descriptor = kw.find("DescriptorName")
        value = _text(kw, "DescriptorName") or (descriptor.text if descriptor is not None else "")
        if value:
            keywords.append(value)

    publication_types = []
    for pub_type in art.findall(".//PublicationType"):
        if pub_type.text:
            publication_types.append(pub_type.text)

    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    doi_url = f"https://doi.org/{doi}" if doi else ""

    return {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "authors": authors_str,
        "first_author": authors[0] if authors else "",
        "last_author": authors[-1] if authors else "",
        "first_author_affiliation": "; ".join(first_author_affiliations),
        "affiliations": affiliations_str,
        "year": year,
        "journal": journal,
        "doi": doi,
        "url": url,
        "doi_url": doi_url,
        "keywords": "; ".join(keywords),
        "publication_types": "; ".join(_unique(publication_types)),
    }


def _fetch_detail_batch(batch: List[str], start: int, total: int) -> List[Dict]:
    log.info("Fetching details: batch %d-%d / %d", start + 1, start + len(batch), total)
    params = {
        "db": "pubmed",
        "id": ",".join(batch),
        "rettype": "xml",
        "retmode": "xml",
    }
    response = _get_with_retry(
        config.PUBMED_FETCH,
        params=params,
        timeout=60,
        label=f"fetch {start + 1}-{start + len(batch)}",
    )
    root = ET.fromstring(response.content)
    parsed_papers = []
    for article in root.findall(".//PubmedArticle"):
        parsed = _parse_article(article)
        if parsed.get("pmid"):
            parsed_papers.append(parsed)
    return parsed_papers


def fetch_details(pmids: List[str]) -> List[Dict]:
    """Fetch and parse detailed metadata for a list of PMIDs."""
    papers = []
    total = len(pmids)
    batch_size = max(1, min(int(config.FETCH_BATCH), int(config.PUBMED_MAX_FETCH_BATCH)))
    if batch_size < int(config.FETCH_BATCH):
        log.info("PubMed fetch batch capped: %d -> %d", config.FETCH_BATCH, batch_size)

    for i in range(0, total, batch_size):
        batch = pmids[i:i + batch_size]
        try:
            papers.extend(_fetch_detail_batch(batch, i, total))
        except Exception as exc:
            log.error("Fetch batch %d-%d failed after retries: %s", i + 1, i + len(batch), exc)
            if len(batch) <= FALLBACK_BATCH_SIZE:
                time.sleep(config.REQUEST_DELAY)
                continue
            log.warning("Retrying failed PubMed batch %d-%d in chunks of %d", i + 1, i + len(batch), FALLBACK_BATCH_SIZE)
            for j in range(0, len(batch), FALLBACK_BATCH_SIZE):
                sub_batch = batch[j:j + FALLBACK_BATCH_SIZE]
                try:
                    papers.extend(_fetch_detail_batch(sub_batch, i + j, total))
                except Exception as sub_exc:
                    log.error("Fetch fallback batch %d-%d failed: %s", i + j + 1, i + j + len(sub_batch), sub_exc)
                time.sleep(config.REQUEST_DELAY)

        time.sleep(config.REQUEST_DELAY)

    log.info("Fetched details for %d papers", len(papers))
    return papers
