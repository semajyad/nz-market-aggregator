import logging
import json
import re
from typing import Optional
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


async def parse_query(raw_query: str) -> ParsedQuery:
    """Use Gemini to parse a natural language query into structured search parameters."""
    if not settings.GEMINI_API_KEY:
        logger.warning("Using fallback NLP parser (no Gemini API key).")
        return _fallback_parse(raw_query)

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
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

        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(text)

        return ParsedQuery(
            keywords=data.get("keywords", [raw_query]),
            max_price=data.get("max_price"),
            min_specs=data.get("min_specs", []),
            raw_query=raw_query,
        )

    except Exception as e:
        logger.error(f"Gemini NLP parsing failed: {e}. Falling back to keyword extraction.")
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
