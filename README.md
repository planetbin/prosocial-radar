# Prosocial Research Radar

Daily research radar for prosocial behavior papers. It searches PubMed, enriches papers with OpenAlex citation counts, filters and scores candidates, generates structured AI summaries, saves reusable research outputs, and sends an email digest.

## What It Does

- Searches PubMed with a configurable research profile.
- Enriches DOI-matched papers with OpenAlex citation counts.
- Filters papers with profile-driven topic and method/context keywords.
- Scores papers by relevance, recency, citations, and topic breadth.
- Removes papers already sent in previous digests.
- Produces structured AI extraction fields for literature review work.
- Saves separate outputs for all candidates and new papers.
- Writes a daily run report that explains what happened in the pipeline.
- Sends an HTML digest with research-question, sample, design, result, limitation, and relevance fields.

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
│   ├── filter.py                   # dedup + profile-driven relevance filtering
│   ├── scorer.py                   # relevance scoring
│   ├── history.py                  # sent-history deduplication
│   ├── summarizer.py               # structured AI extraction
│   ├── push.py                     # email rendering and delivery
│   └── output.py                   # CSV/JSON/run-report output
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

- `all_candidates_YYYYMMDD.csv`
- `all_candidates_YYYYMMDD.json`
- `new_papers_YYYYMMDD.csv`
- `new_papers_YYYYMMDD.json`
- `run_report_YYYYMMDD.json`

`all_candidates` contains every filtered and scored paper for the day. `new_papers` contains only papers not already recorded in `data/sent_history.json`.

Structured AI fields include:

- `ai_research_question`
- `ai_sample`
- `ai_design`
- `ai_measures`
- `ai_main_result`
- `ai_limitations`
- `ai_why_it_matters`
- `ai_bibtex_keywords`

The run report records counts for each stage: PMIDs found, details fetched, after-filter candidates, new papers, summary attempts, successful summaries, email status, and output paths.

## GitHub Actions

The workflow at `.github/workflows/daily_radar.yml` runs daily at UTC 00:00, which is Beijing 08:00. Add these repository secrets before enabling the workflow:

- `DEEPSEEK_API_KEY`
- `GMAIL_ADDRESS`
- `GMAIL_APP_PASSWORD`
- optional: `ANTHROPIC_API_KEY`

The workflow commits updated `data/sent_history.json` and `outputs/` files back to the repository after each successful run.

See `GITHUB_SETUP.md` for step-by-step deployment notes.
