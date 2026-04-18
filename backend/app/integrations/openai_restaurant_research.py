from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import httpx

from ..core.config import settings


RESPONSES_URL = "https://api.openai.com/v1/responses"
logger = logging.getLogger(__name__)


class OpenAIRestaurantResearchConfigError(RuntimeError):
    """Raised when OpenAI restaurant research is misconfigured."""


class OpenAIRestaurantResearchError(RuntimeError):
    """Raised when OpenAI restaurant research fails."""


def _require_api_key() -> str:
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise OpenAIRestaurantResearchConfigError("OPENAI_API_KEY is not configured")
    return api_key


def _extract_output_text(response_json: dict[str, Any]) -> str:
    fragments: list[str] = []
    for item in response_json.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []) or []:
            if content.get("type") == "output_text" and content.get("text"):
                fragments.append(content["text"])
    return "\n".join(fragment for fragment in fragments if fragment).strip()


def _extract_source_urls(response_json: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for item in response_json.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []) or []:
            for annotation in content.get("annotations", []) or []:
                url = annotation.get("url")
                if url and url not in seen:
                    seen.add(url)
                    urls.append(url)

    return urls


def _extract_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3:
            candidate = "\n".join(lines[1:-1]).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise OpenAIRestaurantResearchError("OpenAI restaurant research did not return JSON")
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise OpenAIRestaurantResearchError(
                f"OpenAI restaurant research returned invalid JSON: {exc}"
            ) from exc


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(text)
    return cleaned


def normalize_restaurant_research(
    value: dict[str, Any],
    *,
    source_urls: list[str] | None = None,
) -> dict[str, Any]:
    result_type = str(value.get("result_type") or "unknown").strip().lower()
    if result_type not in {"menu", "vibe", "unknown"}:
        result_type = "unknown"

    summary = str(value.get("summary") or "").strip()
    menu_items = _normalize_string_list(value.get("menu_items"))
    cuisine_tags = _normalize_string_list(value.get("cuisine_tags"))
    dietary_signals = _normalize_string_list(value.get("dietary_signals"))

    confidence = value.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    if menu_items and result_type == "unknown":
        result_type = "menu"
    if not menu_items and result_type == "menu":
        result_type = "vibe"

    if not summary:
        if menu_items:
            summary = "Menu evidence found for today."
        elif cuisine_tags:
            summary = f"Likely fit for {', '.join(cuisine_tags[:3])} preferences."
        else:
            summary = "Limited current evidence found."

    return {
        "result_type": result_type,
        "summary": summary[:240],
        "menu_items": menu_items[:5],
        "cuisine_tags": cuisine_tags[:4],
        "dietary_signals": dietary_signals[:5],
        "confidence": round(max(0.0, min(confidence, 1.0)), 2),
        "source_urls": _normalize_string_list(source_urls or [])[:5],
        "research_timestamp": datetime.utcnow().isoformat(),
    }


async def research_restaurant_with_openai(
    *,
    restaurant_name: str,
    restaurant_address: str | None,
    website_uri: str | None,
    primary_type: str | None,
) -> dict[str, Any]:
    api_key = _require_api_key()
    model = settings.OPENAI_MODEL
    today = datetime.utcnow().date().isoformat()

    prompt = f"""
You are researching one restaurant for a team lunch decision on {today}.

Restaurant name: {restaurant_name}
Restaurant address: {restaurant_address or "unknown"}
Restaurant website: {website_uri or "unknown"}
Restaurant primary type: {primary_type or "unknown"}

Use web search to find today's lunch menu or the current lunch offering for this restaurant.
If there is a weekly menu, extract only the dishes relevant to today.
If you cannot find a menu for today, return the best available cuisine/vibe summary from reliable current sources.

Rules:
- Prefer current official restaurant sources when possible.
- Only include concrete menu_items if you found evidence for them.
- Do not invent dishes, prices, or dietary claims.
- If no menu is found, set result_type to "vibe" and keep menu_items empty.
- Do not write paragraphs or franchise overviews.
- Keep summary to one short sentence.
- Keep cuisine_tags and dietary_signals short and normalized.
- Return at most 5 menu_items, 4 cuisine_tags, and 5 dietary_signals.
""".strip()

    payload = {
        "model": model,
        "tools": [{"type": "web_search"}],
        "tool_choice": "auto",
        "include": ["web_search_call.action.sources"],
        "parallel_tool_calls": True,
        "max_output_tokens": 500,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "restaurant_research",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "result_type": {
                            "type": "string",
                            "enum": ["menu", "vibe", "unknown"],
                        },
                        "summary": {"type": "string"},
                        "menu_items": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "cuisine_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "dietary_signals": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "confidence": {"type": "number"},
                    },
                    "required": [
                        "result_type",
                        "summary",
                        "menu_items",
                        "cuisine_tags",
                        "dietary_signals",
                        "confidence",
                    ],
                },
            }
        },
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(RESPONSES_URL, headers=headers, json=payload)

    if response.status_code >= 400:
        raise OpenAIRestaurantResearchError(
            f"OpenAI restaurant research failed with status {response.status_code}: {response.text}"
        )

    response_json = response.json()
    output_text = _extract_output_text(response_json)
    if not output_text:
        raise OpenAIRestaurantResearchError("OpenAI restaurant research returned no text output")

    try:
        parsed = _extract_json_object(output_text)
    except OpenAIRestaurantResearchError:
        logger.warning(
            "[discover] OpenAI raw output for %s was not valid JSON: %s",
            restaurant_name,
            output_text[:2000],
        )
        raise
    return normalize_restaurant_research(
        parsed,
        source_urls=_extract_source_urls(response_json),
    )
