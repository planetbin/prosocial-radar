"""
AI Summarization module.

Backend priority:
  1. DeepSeek API  (DEEPSEEK_API_KEY)       — primary, cheapest
  2. HappyCapy AI Gateway (AI_GATEWAY_API_KEY) — sandbox fallback
  3. Anthropic direct (ANTHROPIC_API_KEY)    — GitHub Actions fallback

For each paper produces:
  summary  : one-sentence plain-English summary (≤25 words)
  method   : behavioral | fMRI | EEG | computational | review | mixed | other
  finding  : core result in ≤15 words
"""

import json as _json
import logging
import os
import time
from typing import Dict, List

import requests

log = logging.getLogger(__name__)

# ─── API endpoints ────────────────────────────────────────────────────────────
DEEPSEEK_URL   = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

AI_GATEWAY_URL   = "https://ai-gateway.happycapy.ai/api/v1/chat/completions"
AI_GATEWAY_MODEL = "anthropic/claude-haiku-4.5"

ANTHROPIC_URL   = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

REQUEST_DELAY = 0.5   # seconds between calls (DeepSeek rate limit: 60 req/min free)

# ─── Prompt ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are a scientific assistant specialising in psychology and neuroscience. "
    "Given a paper title and abstract, respond ONLY with a JSON object (no markdown fences) "
    "with exactly three keys:\n"
    '  "summary": one sentence (≤25 words) plain-English summary of what the paper does\n'
    '  "method": one of: behavioral | fMRI | EEG | computational | review | mixed | other\n'
    '  "finding": the core result in ≤15 words\n'
    "Do not add any other text or explanation outside the JSON."
)

_DEFAULT = {"summary": "", "method": "other", "finding": ""}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> Dict:
    """Strip accidental markdown fences and parse JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return _json.loads(raw.strip())


def _openai_compat(url: str, model: str, api_key: str,
                   title: str, abstract: str) -> Dict:
    """Call any OpenAI-compatible endpoint (DeepSeek / AI Gateway)."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",
             "content": f"Title: {title}\n\nAbstract: {(abstract or '')[:1500]}"},
        ],
        "max_tokens":  200,
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return _parse_json(r.json()["choices"][0]["message"]["content"])


def _call_anthropic(title: str, abstract: str, api_key: str) -> Dict:
    """Anthropic Messages API (not OpenAI-compatible)."""
    payload = {
        "model":      ANTHROPIC_MODEL,
        "max_tokens": 200,
        "system":     SYSTEM_PROMPT,
        "messages": [
            {"role": "user",
             "content": f"Title: {title}\n\nAbstract: {(abstract or '')[:1500]}"},
        ],
    }
    headers = {
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type":      "application/json",
    }
    r = requests.post(ANTHROPIC_URL, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return _parse_json(r.json()["content"][0]["text"])


# ─── Main dispatcher ──────────────────────────────────────────────────────────

def _call_llm(title: str, abstract: str) -> Dict:
    """
    Try backends in order: DeepSeek → AI Gateway → Anthropic.
    Returns dict with summary / method / finding.
    """
    ds_key  = os.environ.get("DEEPSEEK_API_KEY",   "").strip()
    gw_key  = os.environ.get("AI_GATEWAY_API_KEY", "").strip()
    ant_key = os.environ.get("ANTHROPIC_API_KEY",  "").strip()

    if not any([ds_key, gw_key, ant_key]):
        log.warning("No LLM API key found — skipping summarization")
        return _DEFAULT.copy()

    # 1. DeepSeek (primary)
    if ds_key:
        try:
            return _openai_compat(DEEPSEEK_URL, DEEPSEEK_MODEL,
                                  ds_key, title, abstract)
        except Exception as exc:
            log.debug("DeepSeek failed: %s", exc)

    # 2. HappyCapy AI Gateway
    if gw_key:
        try:
            return _openai_compat(AI_GATEWAY_URL, AI_GATEWAY_MODEL,
                                  gw_key, title, abstract)
        except Exception as exc:
            log.debug("AI Gateway failed: %s", exc)

    # 3. Anthropic direct
    if ant_key:
        try:
            return _call_anthropic(title, abstract, ant_key)
        except Exception as exc:
            log.debug("Anthropic failed for '%s': %s", title[:55], exc)

    return _DEFAULT.copy()


# ─── Public interface ─────────────────────────────────────────────────────────

def summarize_papers(papers: List[Dict], max_papers: int = 10) -> List[Dict]:
    """
    Generate AI summaries for the top `max_papers` papers (by relevance_score).
    Papers beyond max_papers receive empty summary fields.
    """
    has_key = any(
        os.environ.get(k, "").strip()
        for k in ("DEEPSEEK_API_KEY", "AI_GATEWAY_API_KEY", "ANTHROPIC_API_KEY")
    )
    if not has_key:
        log.warning("No LLM API key — skipping all summaries")
        for p in papers:
            p.update({"ai_summary": "", "ai_method": "", "ai_finding": ""})
        return papers

    n = min(max_papers, len(papers))
    log.info("Generating AI summaries for top %d papers (DeepSeek)...", n)

    for i, p in enumerate(papers):
        if i < max_papers:
            result = _call_llm(p.get("title", ""), p.get("abstract", ""))
            p["ai_summary"] = result.get("summary", "")
            p["ai_method"]  = result.get("method",  "other")
            p["ai_finding"] = result.get("finding", "")
            log.debug("[%d/%d] %s → %s", i + 1, n,
                      p.get("title", "")[:55], p.get("ai_method"))
            time.sleep(REQUEST_DELAY)
        else:
            p["ai_summary"] = ""
            p["ai_method"]  = ""
            p["ai_finding"] = ""

    log.info("AI summarization complete.")
    return papers
