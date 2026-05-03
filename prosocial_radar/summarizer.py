"""
AI summarization module.

Backend priority:
  1. DeepSeek API (DEEPSEEK_API_KEY)
  2. HappyCapy AI Gateway (AI_GATEWAY_API_KEY)
  3. Anthropic direct (ANTHROPIC_API_KEY)

Each summarized paper keeps the legacy three fields and adds structured fields
that are easier to reuse in literature matrices, research notes, and Zotero.
"""

import json as _json
import logging
import os
import time
from typing import Dict, List

import requests

from . import config

log = logging.getLogger(__name__)

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

AI_GATEWAY_URL = "https://ai-gateway.happycapy.ai/api/v1/chat/completions"
AI_GATEWAY_MODEL = "anthropic/claude-haiku-4.5"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

REQUEST_DELAY = 0.5

SUMMARY_KEYS = [
    "summary",
    "method",
    "finding",
    "research_question",
    "sample",
    "design",
    "measures",
    "main_result",
    "limitations",
    "why_it_matters",
    "bibtex_keywords",
]

SUMMARY_DEFAULT = {
    "summary": "",
    "method": "other",
    "finding": "",
    "research_question": "",
    "sample": "",
    "design": "",
    "measures": "",
    "main_result": "",
    "limitations": "",
    "why_it_matters": "",
    "bibtex_keywords": "",
}

PAPER_SUMMARY_DEFAULTS = {
    "ai_summary": "",
    "ai_method": "",
    "ai_finding": "",
    "ai_research_question": "",
    "ai_sample": "",
    "ai_design": "",
    "ai_measures": "",
    "ai_main_result": "",
    "ai_limitations": "",
    "ai_why_it_matters": "",
    "ai_bibtex_keywords": "",
}

METHOD_ALIASES = {
    "behavioral": "behavioral",
    "behavioural": "behavioral",
    "fmri": "fMRI",
    "functional mri": "fMRI",
    "eeg": "EEG",
    "computational": "computational",
    "review": "review",
    "mixed": "mixed",
    "other": "other",
}

SYSTEM_PROMPT = """You are a scientific assistant specialising in psychology and neuroscience.
Given a paper title and abstract, respond ONLY with a JSON object and no markdown fences.
Use exactly these keys:
- "summary": one sentence, <=25 words, plain-English summary of what the paper does
- "method": one of behavioral | fMRI | EEG | computational | review | mixed | other
- "finding": core result in <=15 words
- "research_question": the specific question or hypothesis
- "sample": participants, species, age group, or dataset; write "not reported" if absent
- "design": study design or analysis type, such as longitudinal, experiment, survey, review, meta-analysis, hyperscanning, or other
- "measures": key tasks, measures, instruments, or neural modalities
- "main_result": one concise sentence about the most important result
- "limitations": one concise limitation or "not clear from abstract"
- "why_it_matters": how it may matter for prosocial behavior research
- "bibtex_keywords": 3-6 comma-separated keywords for reference management
Do not add any other text outside the JSON."""


def ensure_summary_fields(paper: Dict) -> Dict:
    """Ensure every output row has all summary columns."""
    for key, value in PAPER_SUMMARY_DEFAULTS.items():
        paper.setdefault(key, value)
    return paper


def _parse_json(raw: str) -> Dict:
    """Strip accidental markdown fences and parse JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return _json.loads(raw.strip())


def _normalise_result(data: Dict) -> Dict:
    result = SUMMARY_DEFAULT.copy()
    if isinstance(data, dict):
        for key in SUMMARY_KEYS:
            if key in data and data[key] is not None:
                result[key] = str(data[key]).strip()
    if not result["main_result"] and result["finding"]:
        result["main_result"] = result["finding"]
    if not result["finding"] and result["main_result"]:
        result["finding"] = result["main_result"][:120]
    result["method"] = METHOD_ALIASES.get(result["method"].strip().lower(), "other")
    return result


def _apply_summary(paper: Dict, result: Dict) -> Dict:
    paper["ai_summary"] = result.get("summary", "")
    paper["ai_method"] = result.get("method", "other")
    paper["ai_finding"] = result.get("finding", "")
    paper["ai_research_question"] = result.get("research_question", "")
    paper["ai_sample"] = result.get("sample", "")
    paper["ai_design"] = result.get("design", "")
    paper["ai_measures"] = result.get("measures", "")
    paper["ai_main_result"] = result.get("main_result", "")
    paper["ai_limitations"] = result.get("limitations", "")
    paper["ai_why_it_matters"] = result.get("why_it_matters", "")
    paper["ai_bibtex_keywords"] = result.get("bibtex_keywords", "")
    return paper


def _user_prompt(title: str, abstract: str) -> str:
    abstract_limit = config.SUMMARY_MAX_ABSTRACT_CHARS
    return f"Title: {title}\n\nAbstract: {(abstract or '')[:abstract_limit]}"


def _openai_compat(url: str, model: str, api_key: str, title: str, abstract: str) -> Dict:
    """Call any OpenAI-compatible endpoint: DeepSeek or AI Gateway."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(title, abstract)},
        ],
        "max_tokens": 500,
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return _normalise_result(_parse_json(r.json()["choices"][0]["message"]["content"]))


def _call_anthropic(title: str, abstract: str, api_key: str) -> Dict:
    """Anthropic Messages API."""
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 500,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": _user_prompt(title, abstract)}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    r = requests.post(ANTHROPIC_URL, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return _normalise_result(_parse_json(r.json()["content"][0]["text"]))


def _call_llm(title: str, abstract: str) -> Dict:
    """Try backends in order: DeepSeek -> AI Gateway -> Anthropic."""
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    gw_key = os.environ.get("AI_GATEWAY_API_KEY", "").strip()
    ant_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not any([ds_key, gw_key, ant_key]):
        log.warning("No LLM API key found - skipping summarization")
        return SUMMARY_DEFAULT.copy()

    if ds_key:
        try:
            return _openai_compat(DEEPSEEK_URL, DEEPSEEK_MODEL, ds_key, title, abstract)
        except Exception as exc:
            log.debug("DeepSeek failed: %s", exc)

    if gw_key:
        try:
            return _openai_compat(AI_GATEWAY_URL, AI_GATEWAY_MODEL, gw_key, title, abstract)
        except Exception as exc:
            log.debug("AI Gateway failed: %s", exc)

    if ant_key:
        try:
            return _call_anthropic(title, abstract, ant_key)
        except Exception as exc:
            log.debug("Anthropic failed for '%s': %s", title[:55], exc)

    return SUMMARY_DEFAULT.copy()


def summarize_papers(papers: List[Dict], max_papers: int = 10) -> List[Dict]:
    """Generate structured AI summaries for the top max_papers papers."""
    has_key = any(
        os.environ.get(k, "").strip()
        for k in ("DEEPSEEK_API_KEY", "AI_GATEWAY_API_KEY", "ANTHROPIC_API_KEY")
    )
    if not has_key:
        log.warning("No LLM API key - skipping all summaries")
        for p in papers:
            ensure_summary_fields(p)
        return papers

    n = min(max_papers, len(papers))
    log.info("Generating structured AI summaries for top %d papers...", n)

    for i, p in enumerate(papers):
        ensure_summary_fields(p)
        if i < max_papers:
            result = _call_llm(p.get("title", ""), p.get("abstract", ""))
            _apply_summary(p, result)
            log.debug("[%d/%d] %s -> %s", i + 1, n, p.get("title", "")[:55], p.get("ai_method"))
            time.sleep(REQUEST_DELAY)

    log.info("AI summarization complete.")
    return papers
