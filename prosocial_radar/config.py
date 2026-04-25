"""
Configuration constants for the Prosocial Research Radar system.
"""

# ─── PubMed API ───────────────────────────────────────────────────────────────
PUBMED_BASE   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_SEARCH = f"{PUBMED_BASE}/esearch.fcgi"
PUBMED_FETCH  = f"{PUBMED_BASE}/efetch.fcgi"

# How many PMIDs to fetch per batch (PubMed recommends ≤200)
FETCH_BATCH   = 100
# Max results per sort channel
MAX_RESULTS   = 200
# "Latest" channel: only papers published within this many days
RECENT_DAYS   = 90
# All channels: only fetch papers published within this many days (3 years)
MAX_AGE_DAYS  = 1095
# Pause between requests (seconds) — NCBI policy: ≤3 req/s without API key
REQUEST_DELAY = 0.5

# ─── OpenAlex API ─────────────────────────────────────────────────────────────
OPENALEX_BASE = "https://api.openalex.org/works"
OA_EMAIL      = "research-radar@example.com"   # polite-pool email
OA_BATCH      = 50   # works per request (max 200)

# ─── Search Query ─────────────────────────────────────────────────────────────
PUBMED_QUERY = (
    '('
    'prosocial[tiab] OR altruism[tiab] OR altruistic[tiab] OR empathy[tiab] OR '
    '"charitable giving"[tiab] OR "social decision making"[tiab] OR '
    '"trust game"[tiab] OR "dictator game"[tiab] OR "ultimatum game"[tiab] OR '
    '"public goods game"[tiab] OR "cooperation"[tiab] OR "helping behavior"[tiab]'
    ')'
    ' AND ('
    'development[tiab] OR child*[tiab] OR adolescent*[tiab] OR '
    'fMRI[tiab] OR "functional MRI"[tiab] OR EEG[tiab] OR neuroimaging[tiab] OR '
    '"neural"[tiab] OR "brain"[tiab]'
    ')'
)

# ─── Target Journals (quality filter) ─────────────────────────────────────────
TARGET_JOURNALS = {
    # Exact journal name as it appears in PubMed / partial match keys (lower-cased)
    "psychological science",
    "journal of personality and social psychology",
    "journal of neuroscience",
    "neuroimage",
    "social cognitive and affective neuroscience",
    "developmental science",
    "child development",
    "cerebral cortex",
    "biological psychology",
    "neuropsychologia",
    # Extended tier — high-impact adjacent journals
    "nature human behaviour",
    "pnas",
    "proceedings of the national academy of sciences",
    "science",
    "nature",
    "current biology",
    "journal of experimental psychology: general",
    "cognition",
    "psychological review",
    "trends in cognitive sciences",
    "developmental psychology",
    "plos one",
    "journal of experimental child psychology",
}
