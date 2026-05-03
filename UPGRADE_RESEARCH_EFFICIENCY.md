# Research Efficiency Upgrade Notes

Branch: `codex/research-efficiency-upgrades`
Base branch: `master`
Base commit: `65748665d04ee4cf678a17eb8cc92604363a8171`

## Scope

This upgrade improves the radar's usefulness for day-to-day research work by adding:

- profile-based research configuration in `profiles/default.yml`
- structured AI extraction fields for literature review notes
- split outputs for all candidates vs new papers
- daily machine-readable run diagnostics
- profile-driven email recipients and filters

## Rollback

Before merging, rollback is simple: close or ignore the branch `codex/research-efficiency-upgrades`.

After merging, use GitHub's revert button on the merge commit, or revert the commits from this branch in reverse order. The branch was intentionally built from small commits so config, output, summarization, and documentation changes can be reverted separately if needed.

## Operational Notes

- The default workflow still runs on `master`; these changes will not affect daily automation until the branch is merged.
- The new dependency is `PyYAML>=6.0.1` for loading research profiles.
- The default profile preserves the previous PubMed query, target journal list, relevance filter terms, and recipient.
- New outputs are written as `all_candidates_YYYYMMDD.*`, `new_papers_YYYYMMDD.*`, and `run_report_YYYYMMDD.json`.
