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
    "year",
    "journal",
    "doi",
    "url",
    "doi_url",
    "is_new",
    "selection_status",
    "relevance_score",
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
        status = p.get("selection_status", "")
        print(f"\n[{i:>3}] {paper_title}")
        print(f"       {journal} ({year}) | citations: {cites_s} | {status}")
        print(f"       tags: {tags}")
    if len(papers) > 20:
        print(f"\n  ... and {len(papers) - 20} more papers in the output files.")
    print(f"\n{'=' * 80}\n")
