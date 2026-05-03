# Prosocial Research Radar

Daily research radar for prosocial behavior papers. It searches PubMed, enriches papers with OpenAlex citation counts, filters and scores candidates, generates structured AI summaries, saves reusable research outputs, and sends an email digest.

## What It Does

- Searches PubMed with a configurable research profile.
- Enriches DOI-matched papers with OpenAlex citation counts.
- Filters papers with profile-driven topic and method/context keywords.
- Explains why each candidate passed or was filtered out.
- Scores papers by relevance, recency, citations, and topic breadth, with a score breakdown.
- Applies GitHub-native human feedback from labelled issues.
- Removes papers already sent in previous digests.
- Produces structured AI extraction fields for literature review work.
- Saves compact durable outputs for new papers, Markdown digest, run report, history, and feedback.
- Uploads full candidate audits as GitHub Actions artifacts instead of committing large audit files.
- Sends an HTML email digest that includes paper cards, feedback buttons, and a Markdown literature brief.

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
│   ├── filter.py                   # dedup + profile-driven relevance filtering + filter audit
│   ├── scorer.py                   # relevance scoring and score explanations
│   ├── feedback.py                 # GitHub issue feedback sync and score adjustment
│   ├── digest.py                   # Markdown literature digest generation
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
```

## Run

```bash
python run_radar.py --top 8
python run_radar.py --no-ai
python run_radar.py --no-push
python run_radar.py --max 100
```

## Outputs

Each run writes files under `outputs/`:

- `new_papers_YYYYMMDD.csv`
- `new_papers_YYYYMMDD.json`
- `digest_YYYYMMDD.md`
- `run_report_YYYYMMDD.json`

The workflow also creates full audit files during the run:

- `all_candidates_YYYYMMDD.csv`
- `all_candidates_YYYYMMDD.json`

Those full audit files are uploaded as a GitHub Actions artifact named `all-candidates-<run_id>` and retained for 14 days. They are intentionally ignored and not committed to the repository to reduce output bloat.

`new_papers` contains only papers not already recorded in `data/sent_history.json`. The full candidate audit contains both retained and filtered-out papers.

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

The run report records counts for each stage: PMIDs found, details fetched, unique candidates, filtered-out candidates, after-filter candidates, new papers, summary attempts, successful summaries, feedback sync, email status, and output paths.

## Email Digest

The email contains:

- ranked paper cards
- structured AI summary fields when available
- `Why selected` explanations from filter and score fields
- four feedback buttons: `Must read`, `Useful`, `Maybe`, `Ignore`
- a visible `Markdown Literature Brief` block that mirrors `outputs/digest_YYYYMMDD.md`

The Markdown block is included directly in the email so it can be pasted into notes, Zotero notes, Obsidian, Notion, or a literature review draft.

## Human Feedback Loop

The first feedback loop is GitHub-native:

1. Click a feedback button in the email.
2. GitHub opens a prefilled new issue labelled `radar-feedback`.
3. Submit the issue as-is, or add notes under `Notes:`.
4. The next scheduled/manual Action reads labelled feedback issues using `GITHUB_TOKEN`.
5. The workflow syncs them into `data/feedback.json`.
6. Future runs adjust scores:
   - exact `must_read`, `useful`, `maybe`, and `ignore` feedback changes that paper's score strongly
   - similar journal/tag patterns provide smaller positive or negative nudges

No external database is required. Feedback remains versioned in GitHub and can be reverted with normal git history.

## GitHub Actions

The workflow at `.github/workflows/daily_radar.yml` runs daily at UTC 00:00, which is Beijing 08:00. Add these repository secrets before enabling the workflow:

- `DEEPSEEK_API_KEY`
- `GMAIL_ADDRESS`
- `GMAIL_APP_PASSWORD`
- optional: `ANTHROPIC_API_KEY`

The workflow permissions include:

- `contents: write` to commit compact outputs and history
- `issues: read` to sync `radar-feedback` issues

After each successful run, the workflow commits only compact durable files:

- `data/sent_history.json`
- `data/feedback.json`
- `outputs/new_papers_*.csv`
- `outputs/new_papers_*.json`
- `outputs/digest_*.md`
- `outputs/run_report_*.json`

See `GITHUB_SETUP.md` for step-by-step deployment notes.
