from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ..core.config import settings


RESPONSES_URL = "https://api.openai.com/v1/responses"


class OpenAIMenuExtractorConfigError(RuntimeError):
    """Raised when OpenAI menu extraction is misconfigured."""


class OpenAIMenuExtractorError(RuntimeError):
    """Raised when OpenAI menu extraction fails."""


class OpenAIMenuExtractorGenericResultError(OpenAIMenuExtractorError):
    """Raised when OpenAI returns a generic, non-actionable menu result."""


class OpenAIMenuExtractorStructureError(OpenAIMenuExtractorError):
    """Raised when OpenAI drops required weekday structure from the source."""


def _require_api_key() -> str:
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise OpenAIMenuExtractorConfigError("OPENAI_API_KEY is not configured")
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
            raise OpenAIMenuExtractorError("OpenAI menu extraction did not return JSON")
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise OpenAIMenuExtractorError(f"OpenAI menu extraction returned invalid JSON: {exc}") from exc


def _normalize_day_sections(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for key, items in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(items, list):
            cleaned = [str(item).strip() for item in items if str(item).strip()]
            if cleaned:
                normalized[key.lower()] = cleaned
    return normalized


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


DAY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("monday", (r"\bmonday\b", r"\bmontag\b", r"(?<![a-z])mo(?![a-z])")),
    ("tuesday", (r"\btuesday\b", r"\bdienstag\b", r"(?<![a-z])di(?![a-z])", r"\btue\b")),
    ("wednesday", (r"\bwednesday\b", r"\bmittwoch\b", r"(?<![a-z])mi(?![a-z])", r"\bwed\b")),
    ("thursday", (r"\bthursday\b", r"\bdonnerstag\b", r"(?<![a-z])do(?![a-z])", r"\bthu\b")),
    ("friday", (r"\bfriday\b", r"\bfreitag\b", r"(?<![a-z])fr(?![a-z])", r"\bfri\b")),
    ("saturday", (r"\bsaturday\b", r"\bsamstag\b", r"(?<![a-z])sa(?![a-z])", r"\bsat\b")),
    ("sunday", (r"\bsunday\b", r"\bsonntag\b", r"(?<![a-z])so(?![a-z])", r"\bsun\b")),
]


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _detect_days_in_source(text: str) -> list[str]:
    content = (text or "").strip().lower()
    if not content:
        return []

    detected: list[str] = []
    for day, patterns in DAY_PATTERNS:
        if any(re.search(pattern, content) for pattern in patterns):
            detected.append(day)
    return detected


def _build_structured_menu_text(
    *,
    day_sections: dict[str, list[str]],
    static_menu_lines: list[str],
) -> str:
    parts: list[str] = []
    for day, items in day_sections.items():
        parts.append(f"{day.capitalize()}:")
        parts.extend(f"- {item}" for item in items)
    if static_menu_lines:
        if parts:
            parts.append("")
        parts.append("Regular menu:")
        parts.extend(f"- {item}" for item in static_menu_lines)
    return "\n".join(parts).strip()


GENERIC_SUMMARY_PATTERNS = [
    r"\bvariety of\b",
    r"\bselection of\b",
    r"\bincluding\b",
    r"\bmain dishes\b",
    r"\bgrilled meats\b",
    r"\bdesserts\b",
    r"\bsoups\b",
    r"\bsalads\b",
]


def _looks_too_generic(
    *,
    structured_menu_text: str,
    day_sections: dict[str, list[str]],
    static_menu_lines: list[str],
) -> bool:
    concrete_items = sum(len(items) for items in day_sections.values()) + len(static_menu_lines)
    if concrete_items >= 2:
        return False

    lower = structured_menu_text.lower()
    if any(re.search(pattern, lower) for pattern in GENERIC_SUMMARY_PATTERNS):
        return True

    non_empty_lines = [line.strip() for line in structured_menu_text.splitlines() if line.strip()]
    if len(non_empty_lines) <= 2 and concrete_items == 0:
        return True

    return False


def normalize_menu_extraction(
    value: dict[str, Any],
    *,
    allow_generic: bool = False,
    source_detected_days: list[str] | None = None,
) -> dict[str, Any]:
    menu_type = str(value.get("menu_type") or "unknown").strip().lower()
    if menu_type not in {"daily", "weekly", "static", "mixed", "unknown"}:
        menu_type = "unknown"

    detected_days = _unique_preserve_order(_normalize_string_list(value.get("detected_days")))
    day_sections = _normalize_day_sections(value.get("day_sections"))
    static_menu_lines = _normalize_string_list(value.get("static_menu_lines"))
    source_detected_days = _unique_preserve_order(source_detected_days or [])

    if source_detected_days and menu_type in {"daily", "weekly", "mixed"}:
        detected_days = _unique_preserve_order(detected_days + source_detected_days)

    structured_menu_text = str(value.get("structured_menu_text") or "").strip()
    rebuilt_structured_menu_text = _build_structured_menu_text(
        day_sections=day_sections,
        static_menu_lines=static_menu_lines,
    )
    if rebuilt_structured_menu_text:
        structured_menu_text = rebuilt_structured_menu_text

    if not structured_menu_text:
        structured_menu_text = rebuilt_structured_menu_text

    if source_detected_days:
        matched_days = [day for day in source_detected_days if day in day_sections]
        missing_days = [day for day in source_detected_days if day not in day_sections]
        if menu_type == "static" and not day_sections:
            raise OpenAIMenuExtractorStructureError(
                "OpenAI menu extraction dropped visible weekday structure and mislabeled the source as static"
            )
        if menu_type in {"daily", "weekly", "mixed"} and not day_sections:
            raise OpenAIMenuExtractorStructureError(
                "OpenAI menu extraction did not preserve weekday sections from the source"
            )
        if len(source_detected_days) >= 2 and len(matched_days) < min(2, len(source_detected_days)):
            raise OpenAIMenuExtractorStructureError(
                "OpenAI menu extraction did not map visible weekday headings into day_sections"
            )
        if menu_type == "weekly" and missing_days and len(matched_days) < len(source_detected_days) - 1:
            raise OpenAIMenuExtractorStructureError(
                "OpenAI menu extraction preserved too few weekday sections for a weekly menu"
            )
    elif menu_type == "weekly" and detected_days and not day_sections:
        raise OpenAIMenuExtractorStructureError(
            "OpenAI menu extraction labeled the source as weekly but did not provide day_sections"
        )

    if not allow_generic and _looks_too_generic(
        structured_menu_text=structured_menu_text,
        day_sections=day_sections,
        static_menu_lines=static_menu_lines,
    ):
        raise OpenAIMenuExtractorGenericResultError(
            "OpenAI menu extraction returned an overly generic summary without concrete dishes"
        )

    confidence = value.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    return {
        "menu_type": menu_type,
        "detected_days": detected_days,
        "confidence": round(confidence, 2),
        "day_sections": day_sections,
        "static_menu_lines": static_menu_lines,
        "structured_menu_text": structured_menu_text,
        "structured_line_count": len(structured_menu_text.splitlines()) if structured_menu_text else 0,
        "extractor": "openai",
    }


async def _request_menu_extraction(
    *,
    prompt: str,
    scraped_text: str,
    pdf_urls: list[str],
    allow_generic: bool,
) -> dict[str, Any]:
    api_key = _require_api_key()
    model = settings.OPENAI_MENU_MODEL or settings.OPENAI_MODEL

    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]

    if pdf_urls:
        for pdf_url in pdf_urls[:3]:
            content.append({"type": "input_file", "file_url": pdf_url})
    else:
        text_excerpt = (scraped_text or "").strip()
        if len(text_excerpt) > 20000:
            text_excerpt = text_excerpt[:20000]
        content.append(
            {
                "type": "input_text",
                "text": f"Scraped page/menu text:\n\n{text_excerpt}",
            }
        )

    payload = {
        "model": model,
        "input": [{"role": "user", "content": content}],
        "max_output_tokens": 2000,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(RESPONSES_URL, headers=headers, json=payload)

    if response.status_code >= 400:
        raise OpenAIMenuExtractorError(
            f"OpenAI menu extraction failed with status {response.status_code}: {response.text}"
        )

    response_json = response.json()
    output_text = _extract_output_text(response_json)
    if not output_text:
        raise OpenAIMenuExtractorError("OpenAI menu extraction returned no text output")

    parsed = _extract_json_object(output_text)
    return normalize_menu_extraction(
        parsed,
        allow_generic=allow_generic,
        source_detected_days=_detect_days_in_source(scraped_text),
    )


async def extract_menu_with_openai(
    *,
    restaurant_url: str,
    restaurant_name: str | None,
    scraped_text: str,
    pdf_urls: list[str] | None = None,
) -> dict[str, Any]:
    pdf_urls = [url for url in (pdf_urls or []) if url]

    base_prompt = f"""
You extract lunch menu items information.

Restaurant URL: {restaurant_url}
Restaurant name: {restaurant_name or "unknown"}

Return exactly one JSON object with this shape:
{{
  "menu_type": "daily|weekly|static|mixed|unknown",
  "detected_days": ["monday", "tuesday"],
  "confidence": 0.0,
  "day_sections": {{
    "monday": ["Dish 1 - 12,90 EUR", "Dish 2 - 10,50 EUR"],
    "tuesday": ["Dish 3 - 11,90 EUR"]
  }},
  "static_menu_lines": ["Dish A - 9,50 EUR", "Dish B"],
  "structured_menu_text": "Compact readable menu text listing dish items and prices when visible"
}}

Rules:
- Focus only on actual menu items.
- If the source is a weekly lunch menu or daily lunch menu, populate day_sections by day. NEVER SKIP DAY INFORMATION.
- If the source is regular menu, set menu_type to "static" and populate static_menu_lines.
- If both daily/weekly specials and a regular menu exist, set menu_type to "mixed".
- structured_menu_text must list actual menu items line by line.
- If weekday headings are visible in the source, detected_days and day_sections must preserve them explicitly.
- Do not flatten Monday/Tuesday/etc. into one undifferentiated list.
- When day_sections is present, structured_menu_text must be grouped under weekday headings in the same order.
- Include prices directly in item lines whenever a price is visible.
- Prefer the exact visible wording from the source over paraphrases.
- Avoid vague summaries like "variety of soups, salads, main dishes, and desserts".
- Always include concrete examples of visible dishes whenever the source shows them.
- day_sections and static_menu_lines must contain actual dish names, not category labels only.
- If you can only see categories and no actual dishes, set menu_type to "unknown" and confidence low.
- If information is unclear, use "unknown" and low confidence instead of hallucinating.
""".strip()

    try:
        return await _request_menu_extraction(
            prompt=base_prompt,
            scraped_text=scraped_text,
            pdf_urls=pdf_urls,
            allow_generic=False,
        )
    except (OpenAIMenuExtractorGenericResultError, OpenAIMenuExtractorStructureError):
        retry_prompt = base_prompt + """

Your previous extraction was not specific enough or it dropped weekday structure.
Retry now and be materially more specific:
- extract actual visible dish names
- include at least 3 concrete examples when the source provides them
- include prices when visible
- do not summarize only categories
- prefer imperfect concrete dish examples over broad menu category descriptions
- if weekday labels exist, map dishes to those exact weekdays in day_sections
- never return a flattened weekly list when weekday headings are visible
""".strip()
        return await _request_menu_extraction(
            prompt=retry_prompt,
            scraped_text=scraped_text,
            pdf_urls=pdf_urls,
            allow_generic=True,
        )
