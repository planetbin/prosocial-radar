"""Output layer: save radar results and run diagnostics."""

import csv
import json
import logging
from datetime import date
from pathlib import Path
from typing import Dict, List

log = logging.getLogger(__name__)

CSV_FIELDS = [
    "pmid",
    "title",
    "authors",
    "first_author",
    "last_author",
    "first_author_affiliation",
    "affiliations",
    "publication_types",
    "year",
    "journal",
    "doi",
    "url",
    "doi_url",
    "is_new",
    "selection_status",
    "filter_decision",
    "filter_reason",
    "topic_tier",
    "topic_reason",
    "matched_core_terms",
    "matched_paradigm_terms",
    "matched_mechanism_terms",
    "matched_context_terms",
    "matched_soft_exclude_terms",
    "matched_hard_exclude_terms",
    "matched_tier_a",
    "matched_tier_b",
    "matched_tags",
    "relevance_score",
    "score_topic",
    "score_keyword",
    "score_keyword_raw",
    "score_citation",
    "score_recency",
    "score_breadth",
    "score_quality",
    "score_penalty",
    "score_breakdown",
    "selection_reason",
    "feedback_rating",
    "feedback_adjustment",
    "feedback_reason",
    "citation_count",
    "is_high_quality",
    "topic_tags",
    "ai_method",
    "ai_summary",
    "ai_finding",
    "ai_research_question",
    "ai_sample",
    "ai_design",
    "ai_measures",
    "ai_main_result",
    "ai_limitations",
    "ai_why_it_matters",
    "ai_bibtex_keywords",
    "feedback_must_read_url",
    "feedback_useful_url",
    "feedback_maybe_url",
    "feedback_ignore_url",
    "keywords",
    "abstract",
]


def _make_filename(prefix: str, ext: str, out_dir: Path) -> Path:
    today = date.today().strftime("%Y%m%d")
    return out_dir / f"{prefix}_{today}.{ext}"


def save_csv(papers: List[Dict], out_dir: Path, prefix: str = "prosocial_papers") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _make_filename(prefix, "csv", out_dir)

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for p in papers:
            writer.writerow({k: (p.get(k) if p.get(k) is not None else "") for k in CSV_FIELDS})

    log.info("CSV saved -> %s (%d rows)", path, len(papers))
    return path


def save_json(papers: List[Dict], out_dir: Path, prefix: str = "prosocial_papers") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _make_filename(prefix, "json", out_dir)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(papers, fh, ensure_ascii=False, indent=2)

    log.info("JSON saved -> %s (%d entries)", path, len(papers))
    return path


def save_run_report(report: Dict, out_dir: Path, prefix: str = "run_report") -> Path:
    """Persist machine-readable diagnostics for the current run."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _make_filename(prefix, "json", out_dir)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    log.info("Run report saved -> %s", path)
    return path


def print_summary(papers: List[Dict], title: str = "Prosocial Research Radar") -> None:
    """Print a human-readable summary table to stdout."""
    print(f"\n{'=' * 80}")
    print(f"  {title} - {len(papers)} papers")
    print(f"{'=' * 80}")
    for i, p in enumerate(papers[:20], 1):
        paper_title = (p.get("title") or "")[:72]
        journal = (p.get("journal") or "")[:40]
        year = p.get("year", "")
        cites = p.get("citation_count")
        cites_s = str(cites) if cites is not None else "-"
        tags = p.get("topic_tags", "")
        tier = p.get("topic_tier", "")
        status = p.get("selection_status", "")
        reason = (p.get("selection_reason") or p.get("filter_reason") or "")[:140]
        authors = (p.get("authors") or "")[:100]
        affiliation = (p.get("first_author_affiliation") or p.get("affiliations") or "")[:120]
        print(f"\n[{i:>3}] {paper_title}")
        print(f"       {journal} ({year}) | citations: {cites_s} | {status}")
        if authors:
            print(f"       authors: {authors}")
        if affiliation:
            print(f"       affiliation: {affiliation}")
        if tier:
            print(f"       tier: {tier} | tags: {tags}")
        else:
            print(f"       tags: {tags}")
        if reason:
            print(f"       why: {reason}")
    if len(papers) > 20:
        print(f"\n  ... and {len(papers) - 20} more papers in the output files.")
    print(f"\n{'=' * 80}\n")
