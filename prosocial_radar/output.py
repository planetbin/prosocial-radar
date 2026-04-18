"""
Output layer: save results to CSV and JSON.
"""

import csv
import json
import logging
from datetime import date
from pathlib import Path
from typing import List, Dict

log = logging.getLogger(__name__)

# Canonical column order for CSV output
CSV_FIELDS = [
    "pmid", "title", "authors", "year", "journal",
    "doi", "url", "doi_url",
    "relevance_score", "citation_count", "is_high_quality",
    "topic_tags", "ai_method", "ai_summary", "ai_finding",
    "keywords", "abstract",
]


def _make_filename(prefix: str, ext: str, out_dir: Path) -> Path:
    today = date.today().strftime("%Y%m%d")
    return out_dir / f"{prefix}_{today}.{ext}"


def save_csv(papers: List[Dict], out_dir: Path, prefix: str = "prosocial_papers") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _make_filename(prefix, "csv", out_dir)

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=CSV_FIELDS,
            extrasaction="ignore",
        )
        writer.writeheader()
        for p in papers:
            writer.writerow({k: (p.get(k) if p.get(k) is not None else "") for k in CSV_FIELDS})

    log.info("CSV saved → %s (%d rows)", path, len(papers))
    return path


def save_json(papers: List[Dict], out_dir: Path, prefix: str = "prosocial_papers") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _make_filename(prefix, "json", out_dir)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(papers, fh, ensure_ascii=False, indent=2)

    log.info("JSON saved → %s (%d entries)", path, len(papers))
    return path


def print_summary(papers: List[Dict]) -> None:
    """Print a human-readable summary table to stdout."""
    print(f"\n{'='*80}")
    print(f"  Prosocial Research Radar — {len(papers)} papers found")
    print(f"{'='*80}")
    for i, p in enumerate(papers[:20], 1):
        title   = (p.get("title") or "")[:72]
        journal = (p.get("journal") or "")[:40]
        year    = p.get("year", "")
        cites   = p.get("citation_count")
        cites_s = str(cites) if cites is not None else "—"
        tags    = p.get("topic_tags", "")
        print(f"\n[{i:>3}] {title}")
        print(f"       {journal} ({year})  |  citations: {cites_s}")
        print(f"       tags: {tags}")
    if len(papers) > 20:
        print(f"\n  ... and {len(papers) - 20} more papers in the output files.")
    print(f"\n{'='*80}\n")
