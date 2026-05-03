# Prosocial Research Radar

Daily research radar for prosocial behavior papers. It searches PubMed, enriches papers with OpenAlex citation counts, filters and scores candidates, generates structured AI summaries, saves reusable research outputs, and sends an email digest.

## What It Does

- Searches PubMed with a configurable research profile and retry/backoff handling for API rate limits.
- Enriches DOI-matched papers with OpenAlex citation counts.
- Filters papers with profile-driven topic and method/context keywords.
- Applies topic-scope screening so broad medical or biological uses of terms like `cooperation` do not pass without a human social-behavior context.
- Applies evidence-tier screening so low-value publication types are filtered before AI summarization.
- Preserves author and affiliation metadata from PubMed records.
- Explains why each candidate passed or was filtered out.
- Scores papers by relevance, recency, citations, topic breadth, and evidence tier, with a score breakdown.
- Applies GitHub-native human feedback from labelled issues.
- Removes papers already sent in previous digests.
- Produces structured AI extraction fields for literature review work.
- Saves compact durable outputs for new papers, run report, history, and feedback.
- Uploads full candidate audits as GitHub Actions artifacts instead of committing large audit files.
- Sends an HTML email digest with paper cards, author/institution lines, evidence tiers, AI fields, selection reasons, and feedback buttons.

## Project Structure

```text
.
├── profiles/
│   └── default.yml                 # research profile: query, filters, journals, recipients
├── prosocial_radar/
│   ├── config.py                   # loads profile + environment overrides
│   ├── profile.py                  # YAML profile loader
│   ├── pubmed.py                   # PubMed three-channel search and metadata parsing
│   ├── openalex.py                 # citation enrichment
│   ├── evidence.py                 # evidence-tier classification and screening rules
│   ├── filter.py                   # dedup + profile-driven relevance filtering + filter audit
│   ├── scorer.py                   # relevance scoring and score explanations
│   ├── feedback.py                 # GitHub issue feedback sync and score adjustment
│   ├── history.py                  # sent-history deduplication
│   ├── summarizer.py               # structured AI extraction
│   ├── push.py                     # email rendering and delivery
│   └── output.py                   # CSV/JSON/run-report output
├── data/
│   ├── sent_history.json           # papers already sent
│   └── feedback.json               # synced human feedback from GitHub issues
├── run_radar.py                    # main entry point
├── scheduler.py                    # optional local scheduler
├── .github/workflows/daily_radar.yml
└── requirements.txt
```

## Install

```bash
pip install -r requirements.txt
```

## Configure

The default profile is `profiles/default.yml`. It controls:

- PubMed query and date windows
- PubMed fetch batch size, retry count, and retry backoff
- OpenAlex polite-pool email
- email recipients
- target journals for high-quality badges
- tier-A and tier-B relevance keywords
- topic tag rules
- max abstract length sent to the AI summarizer

To run another profile:

```bash
RADAR_PROFILE=my_project python run_radar.py
```

This loads `profiles/my_project.yml`.

You can also point to an explicit file:

```bash
RADAR_PROFILE_PATH=profiles/empathy_neuro.yml python run_radar.py
```

Useful environment overrides:

```bash
export DEEPSEEK_API_KEY="sk-xxxx"
export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxxxxxxxxxxxxxx"
export RADAR_RECIPIENTS="name@example.com,other@example.com"
export OPENALEX_EMAIL="you@example.com"
export NCBI_API_KEY="optional-ncbi-api-key"
export PUBMED_FETCH_BATCH="50"
export PUBMED_MAX_RETRIES="4"
export PUBMED_BACKOFF_SECONDS="2.0"
```

## Run

```bash
python run_radar.py --top 8
python run_radar.py --no-ai
python run_radar.py --no-push
python run_radar.py --max 100
```

## Outputs

Each run writes compact durable files under `outputs/`:

- `new_papers_YYYYMMDD.csv`
- `new_papers_YYYYMMDD.json`
- `run_report_YYYYMMDD.json`

The workflow also creates full audit files during the run:

- `all_candidates_YYYYMMDD.csv`
- `all_candidates_YYYYMMDD.json`

Those full audit files are uploaded as a GitHub Actions artifact named `all-candidates-<run_id>` and retained for 14 days. They are intentionally ignored and not committed to the repository to reduce output bloat.

`new_papers` contains only papers not already recorded in `data/sent_history.json`. The full candidate audit contains both retained and filtered-out papers.

Bibliographic metadata fields include:

- `authors`
- `first_author`
- `last_author`
- `first_author_affiliation`
- `affiliations`
- `publication_types`

Topic-scope fields include:

- `topic_scope_decision`
- `topic_scope_reason`

Evidence-tier fields include:

- `evidence_level`
- `evidence_type`
- `evidence_decision`
- `evidence_reason`
- `evidence_score_adjustment`

Evidence-tier screening keeps higher-value literature review inputs and filters low-screening-value records:

- `L1 evidence synthesis`: meta-analysis, systematic review, umbrella/scoping review, review; retained but no longer given the strongest score boost
- `L2 causal/experimental`: randomized, controlled trial, experiment, intervention, causal inference
- `L3 longitudinal/cohort`: longitudinal, cohort, prospective, follow-up, panel designs
- `L4 human empirical`: survey, behavioral task, reported sample, human neuroscience measure
- `L5 computational/method`, `L5 nonhuman empirical`, or `L5 unclear evidence`: retained but downweighted when appropriate
- `L6 low evidence`: filtered out for protocol, editorial/commentary, letter/correction, case report, news item, or missing abstract

Audit and explanation fields include:

- `filter_decision`
- `filter_reason`
- `matched_tier_a`
- `matched_tier_b`
- `matched_tags`
- `score_keyword`
- `score_citation`
- `score_recency`
- `score_breadth`
- `score_evidence`
- `score_breakdown`
- `selection_reason`
- `feedback_rating`
- `feedback_adjustment`
- `feedback_reason`

Structured AI fields include:

- `ai_research_question`
- `ai_sample`
- `ai_design`
- `ai_measures`
- `ai_main_result`
- `ai_limitations`
- `ai_why_it_matters`
- `ai_bibtex_keywords`

The run report records counts for each stage: PMIDs found, details fetched, details missing after retries, unique candidates, topic-scope counts, filtered-out candidates, after-filter candidates, evidence-tier counts, new papers, summary attempts, successful summaries, feedback sync, email status, and output paths.

## Email Digest

The email contains:

- ranked paper cards
- authors and first-author institution/affiliation when PubMed provides them
- evidence tier and evidence reason
- structured AI summary fields when available
- `Why selected` explanations from filter, score, evidence, and feedback fields
- four feedback buttons: `Must read`, `Useful`, `Maybe`, `Ignore`

## Human Feedback Loop

The first feedback loop is GitHub-native:

1. Click a feedback button in the email.
2. GitHub opens a prefilled new issue labelled `radar-feedback`.
3. Submit the issue as-is, or add notes under `Notes:`.
4. The next scheduled/manual Action reads labelled feedback issues using `GITHUB_TOKEN`.
5. The workflow syncs them into `data/feedback.json`.
6. Future runs adjust scores before the history filter removes already-sent papers.

Because sent papers are deduplicated by `data/sent_history.json`, feedback on an already-pushed paper usually will not make that exact paper appear again. Its main effect is to teach the ranking model what kinds of future papers are related to your preference:

- exact `must_read`, `useful`, `maybe`, and `ignore` feedback is stored for audit and for cases where history is reset or identifiers differ
- similar journal and topic-tag patterns provide smaller positive or negative nudges to new candidate papers
- `selection_reason` and `feedback_reason` explain any feedback-based score movement

No external database is required. Feedback remains versioned in GitHub and can be reverted with normal git history.

## GitHub Actions

The workflow at `.github/workflows/daily_radar.yml` runs daily at UTC 00:00, which is Beijing 08:00. Add these repository secrets before enabling the workflow:

- `DEEPSEEK_API_KEY`
- `GMAIL_ADDRESS`
- `GMAIL_APP_PASSWORD`
- optional: `ANTHROPIC_API_KEY`
- optional: `NCBI_API_KEY` to raise PubMed API rate limits

The workflow permissions include:

- `contents: write` to commit compact outputs and history
- `issues: read` to sync `radar-feedback` issues

After each successful run, the workflow commits only compact durable files:

- `data/sent_history.json`
- `data/feedback.json`
- `outputs/new_papers_*.csv`
- `outputs/new_papers_*.json`
- `outputs/run_report_*.json`

See `GITHUB_SETUP.md` for step-by-step deployment notes.
