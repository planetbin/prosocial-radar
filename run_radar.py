#!/usr/bin/env python3
"""
Prosocial Research Radar main entry point.

Pipeline:
  PubMed fetch -> OpenAlex citations -> dedup/filter audit -> score
  -> GitHub feedback adjustment -> history dedup -> structured AI summarize
  -> split CSV/JSON/Markdown outputs -> email push -> run report
"""

import argparse
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from prosocial_radar import config
from prosocial_radar.digest import build_markdown_digest, save_markdown_digest
from prosocial_radar.feedback import apply_feedback_adjustments, attach_feedback_links, sync_feedback_from_github
from prosocial_radar.filter import build_filter_audit
from prosocial_radar.history import filter_new_papers, mark_as_sent
from prosocial_radar.openalex import enrich_with_citations
from prosocial_radar.output import print_summary, save_csv, save_json, save_run_report
from prosocial_radar.pubmed import fetch_details, get_all_pmids
from prosocial_radar.push import send_email
from prosocial_radar.scorer import score_papers
from prosocial_radar.summarizer import ensure_summary_fields, summarize_papers


def parse_args():
    p = argparse.ArgumentParser(description="Prosocial Research Radar")
    p.add_argument("--no-openalex", action="store_true")
    p.add_argument("--no-filter", action="store_true")
    p.add_argument("--no-score", action="store_true")
    p.add_argument("--no-ai", action="store_true")
    p.add_argument("--no-push", action="store_true")
    p.add_argument("--out-dir", default="outputs")
    p.add_argument("--max", type=int, default=config.MAX_RESULTS)
    p.add_argument("--top", type=int, default=8, help="How many top papers to summarize and push")
    return p.parse_args()


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(path: Path | None) -> str:
    return str(path) if path else ""


def _run_report_path(out_dir: Path) -> Path:
    return out_dir / f"run_report_{date.today().strftime('%Y%m%d')}.json"


def _new_identity(paper):
    return paper.get("pmid") or (paper.get("doi") or "").lower().strip()


def _init_report(args) -> dict:
    return {
        "started_at_utc": _utc_now(),
        "finished_at_utc": "",
        "status": "running",
        "profile": {
            "name": config.PROFILE_NAME,
            "path": config.PROFILE_PATH,
        },
        "parameters": {
            "max_per_channel": args.max,
            "top": args.top,
            "no_openalex": args.no_openalex,
            "no_filter": args.no_filter,
            "no_score": args.no_score,
            "no_ai": args.no_ai,
            "no_push": args.no_push,
        },
        "stages": {},
        "summaries": {},
        "outputs": {},
        "email": {},
        "feedback": {},
        "errors": [],
    }


def _finish_report(report: dict, out_dir: Path, status: str, error: str | None = None) -> Path:
    report["status"] = status
    report["finished_at_utc"] = _utc_now()
    report.setdefault("outputs", {})["run_report_json"] = _path(_run_report_path(out_dir))
    if error:
        report.setdefault("errors", []).append(error)
    return save_run_report(report, out_dir)


def _mark_new_status(papers, new_papers):
    new_ids = {_new_identity(p) for p in new_papers if _new_identity(p)}
    for p in papers:
        is_new = _new_identity(p) in new_ids
        p["is_new"] = is_new
        p["selection_status"] = "new" if is_new else "already_seen"


def _mark_filtered_status(candidate_audit):
    for p in candidate_audit:
        if p.get("filter_decision") != "passed":
            p.setdefault("is_new", False)
            p.setdefault("selection_status", "filtered_out")
        else:
            p.setdefault("selection_status", "passed_not_checked")


def _set_unscored_defaults(papers):
    for p in papers:
        p.setdefault("relevance_score", None)
        p.setdefault("score_keyword", None)
        p.setdefault("score_keyword_raw", None)
        p.setdefault("score_citation", None)
        p.setdefault("score_recency", None)
        p.setdefault("score_breadth", None)
        p.setdefault("score_breakdown", "")
        p.setdefault("selection_reason", p.get("filter_reason", ""))


def main():
    setup_logging()
    args = parse_args()
    out_dir = Path(args.out_dir)
    report = _init_report(args)

    log = logging.getLogger("run_radar")
    log.info("=== Prosocial Research Radar starting ===")
    log.info("Profile: %s (%s)", config.PROFILE_NAME, config.PROFILE_PATH)

    report["feedback"] = sync_feedback_from_github()

    pmids = get_all_pmids(max_results=args.max)
    report["stages"]["pubmed_pmids"] = len(pmids)
    if not pmids:
        log.error("No PMIDs returned. Check query or network.")
        _finish_report(report, out_dir, "failed", "No PMIDs returned from PubMed")
        sys.exit(1)

    papers = fetch_details(pmids)
    report["stages"]["pubmed_details"] = len(papers)
    if not papers:
        log.error("No paper details fetched.")
        _finish_report(report, out_dir, "failed", "No paper details fetched")
        sys.exit(1)
    log.info("Raw papers fetched: %d", len(papers))

    if not args.no_openalex:
        papers = enrich_with_citations(papers)
        report["stages"]["openalex_enriched"] = sum(1 for p in papers if p.get("citation_count") is not None)
    else:
        for p in papers:
            p.setdefault("citation_count", None)
        report["stages"]["openalex_enriched"] = 0

    before_filter = len(papers)
    candidate_audit = build_filter_audit(papers)
    if args.no_filter:
        for p in candidate_audit:
            audit_reason = p.get("filter_reason", "")
            p["filter_decision"] = "passed"
            p["filter_reason"] = f"--no-filter flag used; audit only. {audit_reason}".strip()
        papers = candidate_audit
    else:
        papers = [p for p in candidate_audit if p.get("filter_decision") == "passed"]

    report["stages"]["before_filter"] = before_filter
    report["stages"]["unique_after_dedup"] = len(candidate_audit)
    report["stages"]["after_filter"] = len(papers)
    report["stages"]["filtered_out"] = len(candidate_audit) - len(papers)
    total_after_filter = len(papers)

    if not args.no_score:
        papers = score_papers(papers)
    else:
        _set_unscored_defaults(papers)
    report["stages"]["scored"] = len(papers) if not args.no_score else 0

    papers = apply_feedback_adjustments(papers)
    report["stages"]["feedback_adjusted"] = sum(1 for p in papers if p.get("feedback_adjustment"))

    new_papers = filter_new_papers(papers)
    _mark_new_status(papers, new_papers)
    _mark_filtered_status(candidate_audit)
    report["stages"]["new_after_history"] = len(new_papers)
    report["stages"]["already_seen_after_history"] = len(papers) - len(new_papers)

    for p in candidate_audit:
        ensure_summary_fields(p)

    if not args.no_ai and new_papers:
        summarize_papers(new_papers, max_papers=args.top)
    report["summaries"]["attempted"] = 0 if args.no_ai else min(args.top, len(new_papers))
    report["summaries"]["with_summary"] = sum(
        1 for p in new_papers[:args.top] if p.get("ai_summary") or p.get("ai_main_result")
    )
    report["summaries"]["skipped_no_ai_flag"] = args.no_ai

    attach_feedback_links(candidate_audit)
    top_new = new_papers[:args.top]
    digest_markdown = build_markdown_digest(top_new, total_found=total_after_filter)
    digest_path = save_markdown_digest(digest_markdown, out_dir)

    all_csv = save_csv(candidate_audit, out_dir, prefix="all_candidates")
    all_json = save_json(candidate_audit, out_dir, prefix="all_candidates")
    new_csv = save_csv(new_papers, out_dir, prefix="new_papers")
    new_json = save_json(new_papers, out_dir, prefix="new_papers")

    report["outputs"].update(
        {
            "all_candidates_csv": _path(all_csv),
            "all_candidates_json": _path(all_json),
            "all_candidates_policy": "GitHub Actions artifact only; not committed back to the repository",
            "new_papers_csv": _path(new_csv),
            "new_papers_json": _path(new_json),
            "digest_markdown": _path(digest_path),
        }
    )

    print_summary(new_papers, title="New Prosocial Papers")
    log.info("Output files:")
    for key, value in report["outputs"].items():
        log.info("  %s -> %s", key, value)

    if not args.no_push:
        sent = send_email(top_new, total_found=total_after_filter, digest_markdown=digest_markdown)
        report["email"] = {
            "attempted": bool(top_new),
            "sent": bool(sent),
            "paper_count": len(top_new),
            "recipient_count": len(config.EMAIL_RECIPIENTS),
            "includes_markdown_digest": bool(digest_markdown.strip()),
            "includes_feedback_links": bool(top_new),
        }
        if sent:
            mark_as_sent(top_new)
    else:
        report["email"] = {
            "attempted": False,
            "sent": False,
            "paper_count": len(top_new),
            "reason": "--no-push",
            "includes_markdown_digest": bool(digest_markdown.strip()),
        }
        log.info("Email push skipped (--no-push). Top %d new papers:", len(top_new))
        for i, p in enumerate(top_new, 1):
            log.info("  [%d] %.1f pts | %s", i, (p.get("relevance_score") or 0), p.get("title", "")[:70])

    report_path = _finish_report(report, out_dir, "ok")
    log.info("Run report -> %s", report_path)
    log.info("=== Done ===")


if __name__ == "__main__":
    main()
