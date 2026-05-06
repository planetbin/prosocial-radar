# Prosocial Research Radar

Prosocial Research Radar is a GitHub Actions based literature radar for prosocial behavior research. It fetches papers from PubMed and OpenAlex, filters and ranks them against a configurable research profile, generates structured AI summaries, sends an HTML email digest, and records enough audit data to explain why each paper was selected or filtered.

The current default profile is tuned for research on prosociality, aging/lifespan differences, helping, sharing, comforting, cost and familiarity mechanisms, neural and attentional mechanisms, measurement/psychometrics, and computational modeling of prosocial decision making.

## Current Pipeline

Each run follows this flow:

1. Fetch candidate papers from enabled sources: PubMed and OpenAlex.
2. Enrich DOI-matched records with OpenAlex citation counts.
3. Deduplicate by PMID, DOI, OpenAlex/source id, and title/year fallback.
4. Build a full filter audit for both retained and filtered papers.
5. Classify topic relevance into `core`, `mechanism_linked`, `adjacent`, or `exclude`.
6. Add research-profile tags such as `aging_prosociality`, `helping_decision`, `neural_mechanism`, `attentional_mechanism`, `measurement_validation`, and `computational_modeling_bridge`.
7. Score papers using topic fit, recency, citations, topic breadth, target-journal match, research-profile alignment, and noise penalties.
8. Sync GitHub-native feedback issues and use them to adjust ranking.
9. Remove papers already sent in earlier successful email pushes.
10. Generate structured AI extraction fields for the top papers.
11. Save compact outputs, upload the full audit as an Actions artifact, send the email digest, and then mark sent papers in history.

## What It Optimizes For

The project is designed to reduce daily literature-screening time by making the email itself actionable:

- Broad source coverage from PubMed plus OpenAlex psychology/social science searches.
- Explicit computational-modeling search channels for model-based, utility, reinforcement-learning, drift-diffusion, Bayesian, and choice-model papers.
- Research-profile reranking around aging/lifespan prosociality, helping/sharing/comforting, costs, familiarity, resources, neural mechanisms, attention, and measurement.
- Compact `Why selected` explanations that show core signal, mechanism, context, profile fit, why it is worth seeing, caution flags, and score components.
- Full selection traces retained behind details in the email and in output files.
- Author and affiliation metadata in both email and CSV/JSON outputs when the source provides it.
- GitHub-native feedback buttons for closing the loop without a separate database.

## Project Structure

```text
.
|-- profiles/
|   `-- default.yml                 # source, query, filter, journal, recipient, and profile settings
|-- prosocial_radar/
|   |-- config.py                   # loads profile and environment overrides
|   |-- profile.py                  # YAML profile loader
|   |-- sources.py                  # multi-source candidate orchestration
|   |-- pubmed.py                   # PubMed search, retry/backoff, metadata parsing
|   |-- openalex.py                 # OpenAlex citation enrichment and source search
|   |-- filter.py                   # deduplication, relevance gate, and filter audit
|   |-- research_profile.py         # research-use tags and profile-fit adjustment
|   |-- scorer.py                   # relevance score and score explanations
|   |-- feedback.py                 # GitHub issue feedback sync and score adjustment
|   |-- history.py                  # sent-history deduplication
|   |-- summarizer.py               # structured AI extraction
|   |-- push.py                     # HTML email rendering and delivery
|   `-- output.py                   # CSV, JSON, and run-report output
|-- data/
|   |-- sent_history.json           # papers already sent successfully
|   `-- feedback.json               # synced GitHub feedback issues
|-- outputs/                        # compact outputs from successful non-dry-run Actions
|-- run_radar.py                    # main entry point
|-- scheduler.py                    # optional local scheduler
|-- .github/workflows/daily_radar.yml
`-- requirements.txt
```

## Configuration

The default profile is `profiles/default.yml`. It controls:

- enabled sources, currently `pubmed` and `openalex`
- PubMed query, date windows, request delay, batch size, retries, and backoff
- OpenAlex search channels, result limits, sorting, and polite-pool email
- email recipients
- target journals used as quality badges
- topic relevance patterns and exclusion patterns
- topic tags and research-profile tags
- maximum abstract length sent to the AI summarizer

Use another profile by setting one of these environment variables:

```bash
RADAR_PROFILE=my_project python run_radar.py
RADAR_PROFILE_PATH=profiles/my_project.yml python run_radar.py
```

Useful environment variables:

```bash
DEEPSEEK_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."          # optional fallback if configured by summarizer
GMAIL_ADDRESS="sender@gmail.com"
GMAIL_APP_PASSWORD="xxxxxxxxxxxxxxxx"
RADAR_RECIPIENTS="name@example.com,other@example.com"
OPENALEX_EMAIL="you@example.com"
NCBI_API_KEY="optional-ncbi-api-key"
PUBMED_FETCH_BATCH="50"
PUBMED_MAX_RETRIES="4"
PUBMED_BACKOFF_SECONDS="2.0"
```

## Running Locally

```bash
pip install -r requirements.txt
python run_radar.py --top 8
python run_radar.py --top 8 --no-push
python run_radar.py --top 8 --no-ai --no-push
python run_radar.py --max 100 --sources pubmed,openalex --no-push
```

Important flags:

- `--top N`: number of top new papers to summarize and push.
- `--max N`: max source results per source/channel where supported.
- `--sources pubmed,openalex`: override enabled sources.
- `--no-ai`: skip structured AI summaries.
- `--no-push`: skip email sending and sent-history marking.
- `--no-filter`, `--no-score`, `--no-openalex`: debugging switches for pipeline inspection.

## GitHub Actions

The production workflow is `.github/workflows/daily_radar.yml`.

It runs on:

- schedule: daily at UTC 00:00, which is Beijing 08:00
- manual dispatch from the GitHub Actions tab
- a GitHub-native formal trigger when `.github/radar-triggers/formal_email.txt` is updated on `master`

Manual inputs:

- `top`: number of top papers to summarize and push, default `8`
- `no_ai`: set `true` to skip AI summaries
- `dry_run`: set `true` for ranking preview only; no email, no artifacts, no output commit

Required repository secrets for full production runs:

- `DEEPSEEK_API_KEY`
- `GMAIL_ADDRESS`
- `GMAIL_APP_PASSWORD`
- optional: `ANTHROPIC_API_KEY`
- optional: `NCBI_API_KEY`

Workflow permissions:

- `contents: write` to commit compact outputs, feedback sync, and sent history
- `issues: read` to read labelled feedback issues

## Email Digest

The email is an HTML research digest, not just a raw list. It includes:

- `Today's Map`, a table of contents for the email sections
- a `Today's must-read` block for the top ranked papers
- sectioned paper cards for aging/lifespan, neural/attention, measurement/methods, computational modeling, mechanism leads, general prosociality, and peripheral watch items
- title, journal, year, authors, and first-author institution/affiliation when available
- method and topic badges
- score, citation count, and research-profile fit
- compact `Why selected` rows: Core, Mechanism, Context, Profile, Worth seeing, Caution, and Score
- expandable full selection trace
- structured AI fields: research question, sample, design, measures, result, limitations, why it matters, and BibTeX keywords
- feedback buttons: `Must read`, `Useful`, `Maybe`, and `Ignore`

## Outputs

A successful non-dry-run writes compact durable files under `outputs/`:

- `new_papers_YYYYMMDD.csv`
- `new_papers_YYYYMMDD.json`
- `run_report_YYYYMMDD.json`

It also generates full candidate audit files during the run:

- `all_candidates_YYYYMMDD.csv`
- `all_candidates_YYYYMMDD.json`

Full candidate audits are uploaded as GitHub Actions artifacts named `all-candidates-<run_id>` and retained for 14 days. They are intentionally not committed to the repository to avoid output bloat.

`new_papers` contains only papers not already recorded in `data/sent_history.json`. The full audit contains retained, already-seen, and filtered-out candidates.

Key output fields include:

- bibliographic metadata: `authors`, `first_author`, `last_author`, `first_author_affiliation`, `affiliations`, `publication_types`
- source metadata: `source`, `source_id`, `source_query`, `openalex_id`, `indexed_in`
- relevance audit: `filter_decision`, `filter_reason`, `topic_tier`, `topic_reason`, matched core/mechanism/context/exclusion terms
- scoring: `relevance_score`, `score_topic`, `score_citation`, `score_recency`, `score_breadth`, `score_research_alignment`, `score_penalty`, `score_breakdown`
- research profile: `research_use_tags`, `research_alignment_score`, `research_alignment_penalty`, `research_takeaway`, `email_section`
- feedback: `feedback_rating`, `feedback_adjustment`, `feedback_reason`, feedback issue URLs
- AI extraction: `ai_research_question`, `ai_sample`, `ai_design`, `ai_measures`, `ai_main_result`, `ai_limitations`, `ai_why_it_matters`, `ai_bibtex_keywords`

The run report records source counts, filter counts, new/already-seen counts, summary attempts, summary success, feedback sync status, email status, and output paths.

## Human Feedback Loop

The feedback loop is GitHub-native:

1. Click a feedback button in the email.
2. GitHub opens a prefilled new issue labelled `radar-feedback`.
3. Submit the issue as-is, or add notes under `Notes:`.
4. The next scheduled or manual Action reads labelled feedback issues with `GITHUB_TOKEN`.
5. Feedback is synced into `data/feedback.json`.
6. Future runs adjust scores before history deduplication removes already-sent papers.

Exact feedback adjustments:

- `must_read`: +25
- `useful`: +12
- `maybe`: +3
- `ignore`: -50

If there is no exact match, the system applies smaller similarity nudges based on journal, topic tags, and research-use tags. Because sent papers are deduplicated by `data/sent_history.json`, feedback on an already-sent paper usually affects similar future papers rather than causing the same paper to be resent.

## Resetting Push History

To restart the digest as if no paper has been sent before, reset `data/sent_history.json` to:

```json
{
  "sent_pmids": [],
  "sent_dois": [],
  "sent_source_ids": [],
  "log": []
}
```

Then remove committed compact output files under `outputs/` if you want the repository to show only new results from the next run. This should be done as a normal commit so it can be reverted through Git history.

## Version Management

The project keeps operational state in versioned files:

- `data/sent_history.json`: sent-paper deduplication state
- `data/feedback.json`: synced feedback state
- `outputs/new_papers_*.csv/json`: compact daily result set
- `outputs/run_report_*.json`: run diagnostics

Rollback is normal Git rollback: revert the relevant commit or restore the relevant file from an earlier commit.

## Notes

- `master` is the production branch.
- Scheduled production runs send email only when there are new selected papers and email credentials are configured.
- `--no-push` runs do not mark papers as sent.
- Dry-run Actions are for ranking preview and do not write durable outputs.
- OpenAlex is used both as an enrichment source and as an independent candidate source for broader psychology and computational-modeling coverage.
