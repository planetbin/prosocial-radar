#!/usr/bin/env python3
"""
Prosocial Research Radar — main entry point.

Full pipeline:
  PubMed fetch → OpenAlex citations → filter → score → history dedup
  → AI summarize → save CSV/JSON → email push

Usage:
    python run_radar.py [options]

Options:
    --no-openalex     Skip OpenAlex citation enrichment
    --no-filter       Disable journal/keyword quality filter
    --no-score        Skip relevance scoring
    --no-ai           Skip AI summarization
    --no-push         Skip email push (dry run)
    --out-dir DIR     Output directory (default: ./outputs)
    --max N           Max PMIDs per PubMed channel (default: 200)
    --top N           Papers to summarize + push per run (default: 8)
    --help            Show this help
"""

import argparse
import logging
import sys
from pathlib import Path

from prosocial_radar import config
from prosocial_radar.pubmed      import get_all_pmids, fetch_details
from prosocial_radar.openalex    import enrich_with_citations
from prosocial_radar.filter      import run_filter_pipeline
from prosocial_radar.scorer      import score_papers
from prosocial_radar.summarizer  import summarize_papers
from prosocial_radar.history     import filter_new_papers, mark_as_sent
from prosocial_radar.output      import save_csv, save_json, print_summary
from prosocial_radar.push        import send_email


def parse_args():
    p = argparse.ArgumentParser(description="Prosocial Research Radar")
    p.add_argument("--no-openalex", action="store_true")
    p.add_argument("--no-filter",   action="store_true")
    p.add_argument("--no-score",    action="store_true")
    p.add_argument("--no-ai",       action="store_true")
    p.add_argument("--no-push",     action="store_true")
    p.add_argument("--out-dir",     default="outputs")
    p.add_argument("--max",  type=int, default=config.MAX_RESULTS)
    p.add_argument("--top",  type=int, default=8,
                   help="How many top papers to summarize and push (default: 8)")
    return p.parse_args()


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main():
    setup_logging()
    args    = parse_args()
    out_dir = Path(args.out_dir)
    config.MAX_RESULTS = args.max

    log = logging.getLogger("run_radar")
    log.info("=== Prosocial Research Radar starting ===")

    # ── 1. PubMed fetch ───────────────────────────────────────────────────────
    pmids = get_all_pmids()
    if not pmids:
        log.error("No PMIDs returned. Check query or network.")
        sys.exit(1)

    papers = fetch_details(pmids)
    if not papers:
        log.error("No paper details fetched.")
        sys.exit(1)
    log.info("Raw papers fetched: %d", len(papers))

    # ── 2. OpenAlex citations ─────────────────────────────────────────────────
    if not args.no_openalex:
        papers = enrich_with_citations(papers)
    else:
        for p in papers:
            p.setdefault("citation_count", None)

    # ── 3. Quality filter ─────────────────────────────────────────────────────
    if not args.no_filter:
        papers = run_filter_pipeline(papers)
    else:
        for p in papers:
            p.setdefault("topic_tags", "")
            p.setdefault("is_high_quality", False)

    total_after_filter = len(papers)

    # ── 4. Score ──────────────────────────────────────────────────────────────
    if not args.no_score:
        papers = score_papers(papers)
    else:
        for p in papers:
            p.setdefault("relevance_score", None)

    # ── 5. History dedup (new papers only) ────────────────────────────────────
    new_papers = filter_new_papers(papers)

    # ── 6. AI summarize top N new papers ─────────────────────────────────────
    if not args.no_ai and new_papers:
        new_papers = summarize_papers(new_papers, max_papers=args.top)
    else:
        for p in new_papers:
            p.update({"ai_summary": "", "ai_method": "", "ai_finding": ""})
        # Still fill fields for all papers
        for p in papers:
            p.setdefault("ai_summary", "")
            p.setdefault("ai_method",  "")
            p.setdefault("ai_finding", "")

    # ── 7. Merge summaries back into full list then save ─────────────────────
    # Build lookup for new papers
    new_by_pmid = {p["pmid"]: p for p in new_papers if p.get("pmid")}
    for p in papers:
        if p.get("pmid") in new_by_pmid:
            np = new_by_pmid[p["pmid"]]
            p["ai_summary"]      = np.get("ai_summary", "")
            p["ai_method"]       = np.get("ai_method", "")
            p["ai_finding"]      = np.get("ai_finding", "")
            p["relevance_score"] = np.get("relevance_score", p.get("relevance_score"))
        else:
            p.setdefault("ai_summary", "")
            p.setdefault("ai_method",  "")
            p.setdefault("ai_finding", "")

    csv_path  = save_csv(papers, out_dir)
    json_path = save_json(papers, out_dir)
    print_summary(papers)

    log.info("Output files:")
    log.info("  CSV  → %s", csv_path)
    log.info("  JSON → %s", json_path)

    # ── 8. Email push ─────────────────────────────────────────────────────────
    top_new = new_papers[:args.top]

    if not args.no_push:
        sent = send_email(top_new, total_found=total_after_filter)
        if sent:
            mark_as_sent(top_new)
    else:
        log.info("Email push skipped (--no-push). Top %d new papers:", len(top_new))
        for i, p in enumerate(top_new, 1):
            log.info("  [%d] %.1f pts | %s",
                     i, p.get("relevance_score", 0), p.get("title", "")[:70])

    log.info("=== Done ===")


if __name__ == "__main__":
    main()
