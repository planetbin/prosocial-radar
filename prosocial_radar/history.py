"""
History tracker — deduplication against previously sent papers.

Stores a JSON file at data/sent_history.json with structure:
{
  "sent_pmids": ["12345678", ...],
  "sent_dois":  ["10.1016/...", ...],
  "log": [
    {"date": "2026-03-22", "pmids": [...], "count": 5}
  ]
}
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Dict, List, Set

log = logging.getLogger(__name__)

HISTORY_PATH = Path("data/sent_history.json")


def _load() -> Dict:
    if HISTORY_PATH.exists():
        try:
            with open(HISTORY_PATH, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            log.warning("Could not load history file: %s", exc)
    return {"sent_pmids": [], "sent_dois": [], "log": []}


def _save(history: Dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as fh:
        json.dump(history, fh, ensure_ascii=False, indent=2)


def get_sent_ids() -> tuple[Set[str], Set[str]]:
    """Return (sent_pmids, sent_dois) as sets."""
    h = _load()
    return set(h.get("sent_pmids", [])), set(h.get("sent_dois", []))


def filter_new_papers(papers: List[Dict]) -> List[Dict]:
    """Return only papers that have NOT been sent before."""
    sent_pmids, sent_dois = get_sent_ids()
    new = []
    for p in papers:
        pmid = p.get("pmid") or ""
        doi  = (p.get("doi") or "").lower().strip()
        if pmid and pmid in sent_pmids:
            continue
        if doi and doi in sent_dois:
            continue
        new.append(p)

    log.info("History filter: %d total → %d new (not previously sent)",
             len(papers), len(new))
    return new


def mark_as_sent(papers: List[Dict]) -> None:
    """Record these papers as sent in the history file."""
    if not papers:
        return
    h = _load()
    sent_pmids = set(h.get("sent_pmids", []))
    sent_dois  = set(h.get("sent_dois", []))

    new_pmids = []
    for p in papers:
        pmid = p.get("pmid") or ""
        doi  = (p.get("doi") or "").lower().strip()
        if pmid:
            sent_pmids.add(pmid)
            new_pmids.append(pmid)
        if doi:
            sent_dois.add(doi)

    h["sent_pmids"] = sorted(sent_pmids)
    h["sent_dois"]  = sorted(sent_dois)
    h.setdefault("log", []).append({
        "date":  date.today().isoformat(),
        "pmids": new_pmids,
        "count": len(papers),
    })

    _save(h)
    log.info("History updated: %d papers marked as sent (total in history: %d)",
             len(papers), len(h["sent_pmids"]))
