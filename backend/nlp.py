import logging
import json
import re
from typing import Optional, Any, Dict, List
import google.generativeai as genai
from models import ParsedQuery
from config import settings

logger = logging.getLogger(__name__)


def _init_gemini():
    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)
    else:
        logger.warning("GEMINI_API_KEY not set - NLP parsing will use fallback mode.")


_init_gemini()

SYSTEM_PROMPT = """You are a search query parser for a NZ second-hand and retail market aggregator.
Parse the user's natural language query into structured JSON search parameters.

Return ONLY valid JSON in this exact format:
{
  "keywords": ["keyword1", "keyword2"],
  "max_price": 1000,
  "min_specs": ["16GB RAM", "SSD", "i7 or Ryzen 7"]
}

Rules:
- keywords: 3-6 concise search terms most likely to match product listings. Always include the product type.
- max_price: numeric price limit in NZD (null if not mentioned)
- min_specs: list of minimum technical requirements (empty array if none mentioned)
- Never include currency symbols or units in max_price
- Extract implied specs (e.g. "can run docker and 50 chrome tabs" → "16GB RAM minimum", "SSD required")
- Keywords should be what you'd type into a search box, not full sentences

Examples:
Query: "Computer that can run docker, windsurf, 50 chrome tabs budget $1000"
Response: {"keywords": ["laptop computer desktop", "16GB RAM", "SSD", "intel i5 OR ryzen 5", "windows 11"], "max_price": 1000, "min_specs": ["16GB RAM", "256GB SSD", "Intel i5 or AMD Ryzen 5"]}

Query: "iPhone 14 or 15 under $600 good condition"
Response: {"keywords": ["iPhone 14", "iPhone 15"], "max_price": 600, "min_specs": []}

Query: "gaming monitor 144hz 27 inch under $400"
Response: {"keywords": ["gaming monitor 144hz 27 inch"], "max_price": 400, "min_specs": ["144Hz refresh rate", "27 inch"]}
"""

EVALUATION_SYSTEM_PROMPT = """You are a strict e-commerce relevance and pricing analyst for NZ shoppers.
Given a user's intent and a batch of listing summaries, return JSON with:
{
  "results": [
    {
      "url": "https://...",
      "is_likely_fit": true,
      "fit_score": 0,
      "fit_reason": "short reason",
      "price_assessment": "good|fair|high|unknown",
      "price_reason": "short reason"
    }
  ]
}

Rules:
- Be strict on fit: reject accessories/peripherals if user asked for a full computer/laptop.
- fit_score is 0-100.
- price_assessment compares listing price to NZ market expectations for that type and the user's budget.
- Return only valid JSON.
"""


def _candidate_models() -> list[str]:
    configured = (settings.GEMINI_MODEL or "").strip()
    candidates = [configured] if configured else []
    for fallback in ["gemini-2.0-flash", "gemini-1.5-flash"]:
        if fallback not in candidates:
            candidates.append(fallback)
    return candidates


def _extract_json_block(text: str) -> Dict[str, Any]:
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    return json.loads(text)


def _normalize_price_assessment(value: Optional[str]) -> str:
    v = (value or "").strip().lower()
    if v in {"good", "great", "cheap", "value"}:
        return "good"
    if v in {"fair", "reasonable", "ok", "average"}:
        return "fair"
    if v in {"high", "overpriced", "expensive"}:
        return "high"
    return "unknown"


async def parse_query(raw_query: str) -> ParsedQuery:
    """Use Gemini to parse a natural language query into structured search parameters."""
    if not settings.GEMINI_API_KEY:
        logger.warning("Using fallback NLP parser (no Gemini API key).")
        return _fallback_parse(raw_query)

    for model_name in _candidate_models():
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=SYSTEM_PROMPT,
            )
            response = model.generate_content(
                raw_query,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=512,
                ),
            )
            text = response.text.strip()
            data = _extract_json_block(text)

            return ParsedQuery(
                keywords=data.get("keywords", [raw_query]),
                max_price=data.get("max_price"),
                min_specs=data.get("min_specs", []),
                raw_query=raw_query,
            )
        except Exception as e:
            logger.warning(f"Gemini model '{model_name}' failed: {e}")

    logger.error("Gemini NLP parsing failed for all candidate models. Falling back to keyword extraction.")
    return _fallback_parse(raw_query)


def _fallback_parse(raw_query: str) -> ParsedQuery:
    """Simple rule-based fallback when Gemini is unavailable."""
    price_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', raw_query)
    max_price = None
    if price_match:
        max_price = float(price_match.group(1).replace(',', ''))

    stop_words = {
        'a', 'an', 'the', 'and', 'or', 'for', 'in', 'on', 'at', 'to', 'of',
        'is', 'it', 'that', 'this', 'with', 'can', 'run', 'tabs', 'budget',
        'under', 'below', 'around', 'about', 'good', 'condition', 'chrome',
    }
    clean = re.sub(r'\$[\d,]+', '', raw_query)
    words = clean.lower().split()
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]
    keywords = list(dict.fromkeys(keywords))[:6]

    return ParsedQuery(
        keywords=keywords if keywords else [raw_query],
        max_price=max_price,
        min_specs=[],
        raw_query=raw_query,
    )


def _fallback_evaluate_items(raw_query: str, items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    parsed = _fallback_parse(raw_query)
    max_price = parsed.max_price
    include_tokens = {
        "laptop", "notebook", "desktop", "computer", "pc", "workstation",
        "thinkpad", "macbook", "ryzen", "intel", "i5", "i7", "16gb", "32gb", "ssd",
    }
    exclude_tokens = {
        "mouse", "keyboard", "dock", "adapter", "cable", "router", "chair",
        "tablet", "monitor", "motherboard", "gpu", "graphics card", "headset",
    }
    out: Dict[str, Dict[str, Any]] = {}
    for item in items:
        url = (item.get("url") or "").strip()
        if not url:
            continue
        title = (item.get("title") or "").lower()
        price = item.get("price")
        include_score = sum(1 for tok in include_tokens if tok in title)
        exclude_score = sum(1 for tok in exclude_tokens if tok in title)
        base_score = min(100, include_score * 20)
        penalty = min(60, exclude_score * 25)
        fit_score = max(0, base_score - penalty)
        is_fit = fit_score >= 35

        if price is None:
            price_assessment = "unknown"
            price_reason = "No price available to compare."
        elif max_price is None:
            price_assessment = "fair"
            price_reason = "No budget limit provided."
        elif price <= max_price * 0.75:
            price_assessment = "good"
            price_reason = f"Well under budget (${max_price:.0f})."
        elif price <= max_price:
            price_assessment = "fair"
            price_reason = f"Within budget (${max_price:.0f})."
        else:
            price_assessment = "high"
            price_reason = f"Over budget (${max_price:.0f})."

        fit_reason = (
            "Appears to be a full computer listing."
            if is_fit
            else "Likely accessory/component or weak match to requested computer intent."
        )
        out[url] = {
            "is_likely_fit": is_fit,
            "fit_score": fit_score,
            "fit_reason": fit_reason,
            "price_assessment": price_assessment,
            "price_reason": price_reason,
        }
    return out


async def evaluate_items_for_query(raw_query: str, items: List[Dict[str, Any]], batch_size: int = 40) -> Dict[str, Dict[str, Any]]:
    if not items:
        return {}
    if not settings.GEMINI_API_KEY:
        logger.warning("Gemini evaluation unavailable (no API key); using fallback evaluator.")
        return _fallback_evaluate_items(raw_query, items)

    evaluations: Dict[str, Dict[str, Any]] = {}
    model_names = _candidate_models()
    for i in range(0, len(items), batch_size):
        chunk = items[i:i + batch_size]
        chunk_payload = [
            {
                "url": item.get("url"),
                "title": item.get("title"),
                "price": item.get("price"),
                "platform": item.get("platform"),
                "condition": item.get("condition"),
            }
            for item in chunk
            if item.get("url")
        ]
        if not chunk_payload:
            continue

        prompt = (
            f"User query: {raw_query}\n"
            "Evaluate the following listing summaries:\n"
            f"{json.dumps(chunk_payload, ensure_ascii=True)}"
        )

        parsed_data: Optional[Dict[str, Any]] = None
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=EVALUATION_SYSTEM_PROMPT,
                )
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=2048,
                    ),
                )
                parsed_data = _extract_json_block(response.text.strip())
                break
            except Exception as e:
                logger.warning(f"Gemini evaluation model '{model_name}' failed: {e}")

        if not parsed_data:
            fallback_chunk = _fallback_evaluate_items(raw_query, chunk)
            evaluations.update(fallback_chunk)
            continue

        for row in parsed_data.get("results", []):
            url = (row.get("url") or "").strip()
            if not url:
                continue
            fit_score = row.get("fit_score", 0)
            try:
                fit_score = int(fit_score)
            except Exception:
                fit_score = 0
            fit_score = max(0, min(100, fit_score))
            evaluations[url] = {
                "is_likely_fit": bool(row.get("is_likely_fit", False)),
                "fit_score": fit_score,
                "fit_reason": (row.get("fit_reason") or "").strip() or "No reason provided.",
                "price_assessment": _normalize_price_assessment(row.get("price_assessment")),
                "price_reason": (row.get("price_reason") or "").strip() or "No pricing context provided.",
            }

        missing = [item for item in chunk if item.get("url") and item.get("url") not in evaluations]
        if missing:
            evaluations.update(_fallback_evaluate_items(raw_query, missing))

    return evaluations
