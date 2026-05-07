"""
OpenAlex integration.

Two roles are kept separate:
  1. citation enrichment for papers that already have DOIs
  2. candidate-source search for psychology, social science, and computational modeling papers
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, timedelta
from typing import Dict, Iterable, List

import requests

from . import config

log = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _build_filter(dois: List[str]) -> str:
    """Build an OpenAlex DOI filter string: doi:10.xxx|10.yyy."""
    if not dois:
        return ""
    return "doi:" + "|".join(dois)


def _retry_delay(response: requests.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), 1.0)
            except ValueError:
                pass
    return max(config.PUBMED_BACKOFF_SECONDS * attempt, 1.0)


def _get_json(url: str, params: Dict, timeout: int, label: str) -> Dict:
    max_retries = max(int(config.PUBMED_MAX_RETRIES), 1)
    for attempt in range(1, max_retries + 1):
        response: requests.Response | None = None
        try:
            response = requests.get(url, params=params, timeout=timeout)
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
                delay = _retry_delay(response, attempt)
                log.warning(
                    "OpenAlex %s returned HTTP %s; retrying in %.1fs (%d/%d)",
                    label,
                    response.status_code,
                    delay,
                    attempt,
                    max_retries,
                )
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            status = response.status_code if response is not None else None
            if status is not None and status not in RETRYABLE_STATUS_CODES:
                raise
            if attempt < max_retries:
                delay = _retry_delay(response, attempt)
                log.warning(
                    "OpenAlex %s failed: %s; retrying in %.1fs (%d/%d)",
                    label,
                    exc,
                    delay,
                    attempt,
                    max_retries,
                )
                time.sleep(delay)
                continue
            raise
    raise RuntimeError(f"OpenAlex {label} failed without a response")


def _strip_doi(value: str | None) -> str:
    return (value or "").replace("https://doi.org/", "").lower().strip()


def _unique(values: Iterable[str], limit: int | None = None) -> List[str]:
    seen, result = set(), []
    for value in values:
        text = " ".join(str(value or "").split())
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
            if limit and len(result) >= limit:
                break
    return result


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
            results = _get_json(config.OPENALEX_BASE, params=params, timeout=30, label=f"citation {i + 1}").get("results", [])
            for item in results:
                raw_doi = _strip_doi(item.get("doi"))
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


def _abstract_from_inverted_index(index: Dict | None) -> str:
    if not isinstance(index, dict):
        return ""
    positions: Dict[int, str] = {}
    for word, offsets in index.items():
        if not isinstance(offsets, list):
            continue
        for offset in offsets:
            try:
                positions[int(offset)] = str(word)
            except (TypeError, ValueError):
                continue
    return " ".join(positions[pos] for pos in sorted(positions))


def _pmid_from_ids(ids: Dict | None) -> str:
    if not isinstance(ids, dict):
        return ""
    raw = str(ids.get("pmid") or "")
    match = re.search(r"(\d+)$", raw)
    return match.group(1) if match else ""


def _source_name(item: Dict) -> str:
    source = (((item.get("primary_location") or {}).get("source") or {}).get("display_name") or "")
    return str(source).strip()


def _landing_url(item: Dict, doi_url: str) -> str:
    location = item.get("primary_location") or {}
    return str(location.get("landing_page_url") or doi_url or item.get("id") or "").strip()


def _author_fields(item: Dict) -> Dict[str, str]:
    authorships = item.get("authorships") or []
    names, affiliations = [], []
    first_affiliations: List[str] = []

    for idx, authorship in enumerate(authorships):
        author = authorship.get("author") or {}
        name = str(author.get("display_name") or "").strip()
        if name:
            names.append(name)

        author_affiliations = []
        for raw in authorship.get("raw_affiliation_strings") or []:
            if raw:
                author_affiliations.append(str(raw))
        for institution in authorship.get("institutions") or []:
            inst_name = str(institution.get("display_name") or "").strip()
            if inst_name:
                author_affiliations.append(inst_name)

        author_affiliations = _unique(author_affiliations)
        affiliations.extend(author_affiliations)
        if idx == 0:
            first_affiliations = author_affiliations

    authors_str = "; ".join(names[:6])
    if len(names) > 6:
        authors_str += " et al."

    all_affiliations = _unique(affiliations, limit=8)
    affiliations_str = "; ".join(all_affiliations)
    if len(_unique(affiliations)) > len(all_affiliations):
        affiliations_str += "; et al."

    return {
        "authors": authors_str,
        "first_author": names[0] if names else "",
        "last_author": names[-1] if names else "",
        "first_author_affiliation": "; ".join(first_affiliations),
        "affiliations": affiliations_str,
    }


def _keywords(item: Dict) -> str:
    values = []
    for key in ("keywords", "topics", "concepts"):
        for entry in item.get(key) or []:
            if isinstance(entry, dict):
                value = entry.get("display_name") or entry.get("keyword")
                if value:
                    values.append(str(value))
    primary_topic = item.get("primary_topic") or {}
    if isinstance(primary_topic, dict) and primary_topic.get("display_name"):
        values.append(str(primary_topic.get("display_name")))
    return "; ".join(_unique(values, limit=20))


def _publication_types(item: Dict) -> str:
    values = [str(item.get("type") or "").strip()]
    indexed_in = item.get("indexed_in") or []
    values.extend(str(value) for value in indexed_in if value)
    return "; ".join(_unique(values))


def _normalise_work(item: Dict, query_name: str, sort: str, rank: int) -> Dict:
    title = str(item.get("display_name") or item.get("title") or "").strip()
    doi = _strip_doi(item.get("doi"))
    doi_url = f"https://doi.org/{doi}" if doi else ""
    ids = item.get("ids") or {}
    authors = _author_fields(item)
    indexed_in = "; ".join(str(value) for value in (item.get("indexed_in") or []) if value)

    paper = {
        "source": "openalex",
        "source_id": str(item.get("id") or "").strip(),
        "source_query": f"{query_name}:{sort}:rank{rank}",
        "openalex_id": str(item.get("id") or "").strip(),
        "indexed_in": indexed_in,
        "pmid": _pmid_from_ids(ids),
        "title": title,
        "abstract": _abstract_from_inverted_index(item.get("abstract_inverted_index")),
        "year": str(item.get("publication_year") or ""),
        "journal": _source_name(item),
        "doi": doi,
        "url": _landing_url(item, doi_url),
        "doi_url": doi_url,
        "keywords": _keywords(item),
        "publication_types": _publication_types(item),
        "citation_count": item.get("cited_by_count"),
    }
    paper.update(authors)
    return paper


def _source_filter() -> str:
    source_days = max(int(getattr(config, "OPENALEX_SOURCE_RECENT_DAYS", config.RECENT_DAYS)), 1)
    since = date.today() - timedelta(days=source_days)
    parts = [
        f"from_publication_date:{since.isoformat()}",
        f"to_publication_date:{date.today().isoformat()}",
        "has_abstract:true",
        "is_retracted:false",
    ]
    return ",".join(parts)


def _search_works(query_name: str, query: str, max_results: int, sort: str) -> List[Dict]:
    if not query or max_results <= 0:
        return []

    per_page = max(1, min(int(config.OPENALEX_SOURCE_BATCH), 200, max_results))
    page, papers = 1, []
    while len(papers) < max_results:
        params = {
            "search": query,
            "filter": _source_filter(),
            "sort": sort,
            "per-page": per_page,
            "page": page,
            "mailto": config.OA_EMAIL,
            "select": ",".join([
                "id",
                "doi",
                "display_name",
                "title",
                "abstract_inverted_index",
                "authorships",
                "publication_year",
                "publication_date",
                "primary_location",
                "ids",
                "keywords",
                "concepts",
                "topics",
                "type",
                "indexed_in",
                "cited_by_count",
            ]),
        }
        try:
            data = _get_json(config.OPENALEX_BASE, params=params, timeout=40, label=f"source {query_name} page={page}")
        except Exception as exc:
            log.error("OpenAlex source search failed (%s, %s): %s", query_name, sort, exc)
            break

        results = data.get("results", [])
        if not results:
            break
        start_rank = len(papers) + 1
        papers.extend(
            _normalise_work(item, query_name=query_name, sort=sort, rank=start_rank + idx)
            for idx, item in enumerate(results)
        )
        log.info("OpenAlex source [%s,%s,page=%d] -> %d works", query_name, sort, page, len(results))
        if len(results) < per_page:
            break
        page += 1
        time.sleep(config.REQUEST_DELAY)

    return papers[:max_results]


def _default_searches() -> List[Dict[str, str]]:
    return [
        {"name": "core_prosocial", "query": "prosocial behavior altruism helping sharing generosity"},
        {"name": "social_decision", "query": "social decision making social preference dictator game"},
        {"name": "computational_modeling", "query": "computational modeling prosocial behavior altruism"},
    ]


def fetch_source_papers(max_results: int | None = None) -> List[Dict]:
    """Search OpenAlex directly for candidate papers."""
    per_search_limit = int(config.OPENALEX_SOURCE_MAX_RESULTS)
    if max_results is not None:
        per_search_limit = min(per_search_limit, max(int(max_results), 1))

    searches = config.OPENALEX_SOURCE_SEARCHES or _default_searches()
    sorts = config.OPENALEX_SOURCE_SORTS or ["relevance_score:desc", "publication_date:desc"]
    raw_papers: List[Dict] = []

    for search in searches:
        name = str(search.get("name") or "openalex").strip()
        query = str(search.get("query") or "").strip()
        if not query:
            continue
        for sort in sorts:
            raw_papers.extend(_search_works(name, query, per_search_limit, str(sort)))
            time.sleep(config.REQUEST_DELAY)

    seen, papers = set(), []
    for paper in raw_papers:
        key = (paper.get("doi") or paper.get("pmid") or paper.get("openalex_id") or "").lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        papers.append(paper)

    log.info("OpenAlex source search: %d raw works -> %d unique candidates", len(raw_papers), len(papers))
    return papers
