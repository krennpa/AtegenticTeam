from __future__ import annotations

import json
from typing import Any

import httpx

from ..core.config import settings


RESPONSES_URL = "https://api.openai.com/v1/responses"


class OpenAIDecisionJudgeConfigError(RuntimeError):
    """Raised when OpenAI team decision judging is misconfigured."""


class OpenAIDecisionJudgeError(RuntimeError):
    """Raised when OpenAI team decision judging fails."""


DECISION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "recommendation_restaurant_name": {"type": "string"},
        "recommendation_restaurant_url": {"type": "string"},
        "recommended_dish": {"type": "string"},
        "explanation_md": {"type": "string"},
        "top_candidates": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer"},
                    "restaurant_name": {"type": "string"},
                    "restaurant_url": {"type": "string"},
                    "recommended_dish": {"type": "string"},
                    "rationale_md": {"type": "string"},
                },
                "required": [
                    "rank",
                    "restaurant_name",
                    "restaurant_url",
                    "recommended_dish",
                    "rationale_md",
                ],
                "additionalProperties": False,
            },
        },
        "fairness_summary": {
            "type": "object",
            "properties": {
                "policy": {"type": "string"},
                "summary_md": {"type": "string"},
                "balance_note": {"type": "string"},
            },
            "required": ["policy", "summary_md", "balance_note"],
            "additionalProperties": False,
        },
        "tie_break_available": {"type": "boolean"},
        "tie_break_mode": {"type": "string"},
        "tie_break_transcript": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker_label": {"type": "string"},
                    "stance": {"type": "string"},
                    "utterance": {"type": "string"},
                    "round_index": {"type": "integer"},
                },
                "required": ["speaker_label", "stance", "utterance", "round_index"],
                "additionalProperties": False,
            },
        },
        "decision_confidence": {"type": "number"},
        "diagnostics": {
            "type": "object",
            "properties": {
                "policy_applied": {"type": "string"},
                "hard_constraint_summary": {"type": "string"},
                "soft_tradeoff_summary": {"type": "string"},
                "considered_restaurant_count": {"type": "integer"},
            },
            "required": [
                "policy_applied",
                "hard_constraint_summary",
                "soft_tradeoff_summary",
                "considered_restaurant_count",
            ],
            "additionalProperties": False,
        },
    },
    "required": [
        "recommendation_restaurant_name",
        "recommendation_restaurant_url",
        "recommended_dish",
        "explanation_md",
        "top_candidates",
        "fairness_summary",
        "tie_break_available",
        "tie_break_mode",
        "tie_break_transcript",
        "decision_confidence",
        "diagnostics",
    ],
    "additionalProperties": False,
}


def _require_api_key() -> str:
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise OpenAIDecisionJudgeConfigError("OPENAI_API_KEY is not configured")
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
        value = json.loads(candidate)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise OpenAIDecisionJudgeError("OpenAI decision judge did not return JSON")

    try:
        value = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as exc:
        raise OpenAIDecisionJudgeError(
            f"OpenAI decision judge returned invalid JSON: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise OpenAIDecisionJudgeError("OpenAI decision judge returned non-object JSON")
    return value


def _normalize_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or candidate.lower() in {"none", "null", "n/a"}:
        return None
    return candidate


def _truncate_menu(value: Any, max_chars: int = 4500) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated]"


def _build_restaurant_payload(menus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for menu in menus:
        payload.append(
            {
                "restaurant_id": menu.get("restaurant_id"),
                "restaurant_name": menu.get("restaurant_name"),
                "restaurant_url": menu.get("restaurant_url"),
                "menu_type": menu.get("menu_type"),
                "detected_days": menu.get("detected_days") or [],
                "freshness": menu.get("freshness"),
                "content_age_hours": menu.get("content_age_hours"),
                "straight_line_distance_km": menu.get("straight_line_distance_km"),
                "team_location": menu.get("team_location") or {},
                "restaurant_location": menu.get("restaurant_location") or {},
                "menu_markdown_excerpt": _truncate_menu(menu.get("menu_markdown")),
                "warning": menu.get("warning"),
            }
        )
    return payload


def _build_raw_text(result: dict[str, Any]) -> str:
    top_candidates = result.get("top_candidates") or []
    candidate_lines = []
    for candidate in top_candidates[:3]:
        if not isinstance(candidate, dict):
            continue
        candidate_lines.append(
            f"{candidate.get('rank', '?')}. {candidate.get('restaurant_name', '')} - {candidate.get('recommended_dish', '')}"
        )
    return (
        f"**Recommendation**: {result.get('recommendation_restaurant_name', '')}\n"
        f"**Dish**: {result.get('recommended_dish', '')}\n"
        f"**Reasoning**: {result.get('explanation_md', '')}\n"
        + (f"**Top Candidates**:\n" + "\n".join(candidate_lines) if candidate_lines else "")
    )


async def run_openai_decision_judge(
    *,
    team_decision_context: dict[str, Any],
    menus: list[dict[str, Any]],
    user_question: str,
    current_day: str,
    current_date: str,
    current_time: str,
    decision_mode: str = "standard",
) -> dict[str, Any]:
    api_key = _require_api_key()
    model = settings.OPENAI_DECISION_MODEL or settings.OPENAI_MODEL
    restaurant_payload = _build_restaurant_payload(menus)

    if not restaurant_payload:
        raise OpenAIDecisionJudgeError("No restaurant menu data available for decision")

    system_prompt = (
        "You are Umamimatch's neutral team lunch judge.\n"
        "Use the provided team decision context and restaurant menu inputs.\n"
        "Important policy:\n"
        "- Hard constraints from members (allergies and dietary restrictions) are non-negotiable.\n"
        "- For soft preference conflicts, apply max_min_fairness first, then optimize overall fit.\n"
        "- Use fairness_memory explicitly when deciding whether to diversify away from repeated recent winners.\n"
        "- If fairness_memory shows winner concentration or repeat pressure, mention that in fairness_summary.\n"
        "- Consider menu freshness and today's day availability.\n"
        "- Use distance only as a soft tie-breaker.\n"
        "- Return a ranked top 3, then choose one final winner.\n"
        "- Keep output concise and suitable for end-user display.\n"
        "- If decision_mode is tie_break, always set tie_break_available to true whenever at least 2 candidates are viable.\n"
        "- In standard mode, you may still set tie_break_available when the top options remain genuinely debatable.\n"
        "- If tie_break_available is true, generate a short tie-break transcript.\n"
        "- The tie-break transcript should feel like a compact debate between teammate personas.\n"
        "- Use actual teammate display names from team_decision_context.members as speaker_label whenever available.\n"
        "- Do not use generic labels like pro, con, neutral, or speaker 1.\n"
        "- Each named speaker should sound distinct and argue from their own preferences or constraints.\n"
        "- Use at most 2 rounds total and keep the transcript under 8 utterances.\n"
        "- End the transcript with a moderator-style final turn that resolves the tie-break.\n"
    )

    decision_input = {
        "current_datetime": {
            "day": current_day,
            "date": current_date,
            "time": current_time,
        },
        "policy": "max_min_fairness",
        "decision_mode": decision_mode,
        "user_question": user_question,
        "team_decision_context": team_decision_context,
        "restaurants": restaurant_payload,
    }

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Decide the best restaurant and one dish.\n"
                            "Return a top 3 ranking with short rationale per candidate.\n"
                            "Include fairness summary and tie-break metadata.\n"
                            "If tie_break_available is true, include a theatrical but concise tie-break transcript.\n"
                            "If decision_mode is tie_break, treat this as an explicit user-requested Tie-Break round.\n"
                            "Return only JSON matching the required schema.\n\n"
                            f"{json.dumps(decision_input, ensure_ascii=True)}"
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "team_decision_result",
                "schema": DECISION_RESPONSE_SCHEMA,
                "strict": True,
            }
        },
        "temperature": float(settings.OPENAI_DECISION_TEMPERATURE),
        "max_output_tokens": 1200,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(RESPONSES_URL, headers=headers, json=payload)

    if response.status_code >= 400:
        raise OpenAIDecisionJudgeError(
            f"OpenAI decision judge failed with status {response.status_code}: {response.text}"
        )

    response_json = response.json()
    output_text = _extract_output_text(response_json)
    if not output_text:
        raise OpenAIDecisionJudgeError("OpenAI decision judge returned no text output")

    parsed = _extract_json_object(output_text)

    result: dict[str, Any] = {
        "recommendation_restaurant_name": str(
            parsed.get("recommendation_restaurant_name") or ""
        ).strip(),
        "recommendation_restaurant_url": _normalize_url(
            parsed.get("recommendation_restaurant_url")
        ),
        "recommended_dish": str(parsed.get("recommended_dish") or "").strip(),
        "explanation_md": str(parsed.get("explanation_md") or "").strip(),
        "top_candidates": [],
        "fairness_summary": {
            "policy": "max_min_fairness",
            "summary_md": "",
            "balance_note": "",
        },
        "tie_break_available": bool(parsed.get("tie_break_available")),
        "tie_break_mode": str(parsed.get("tie_break_mode") or "").strip() or None,
        "tie_break_transcript": parsed.get("tie_break_transcript") or [],
    }
    for candidate in parsed.get("top_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        result["top_candidates"].append(
            {
                "rank": int(candidate.get("rank") or len(result["top_candidates"]) + 1),
                "restaurant_name": str(candidate.get("restaurant_name") or "").strip(),
                "restaurant_url": _normalize_url(candidate.get("restaurant_url")),
                "recommended_dish": str(candidate.get("recommended_dish") or "").strip() or None,
                "rationale_md": str(candidate.get("rationale_md") or "").strip(),
            }
        )
    fairness_summary = parsed.get("fairness_summary") or {}
    if isinstance(fairness_summary, dict):
        result["fairness_summary"] = {
            "policy": str(fairness_summary.get("policy") or "max_min_fairness").strip(),
            "summary_md": str(fairness_summary.get("summary_md") or "").strip(),
            "balance_note": str(fairness_summary.get("balance_note") or "").strip() or None,
        }
    result["raw_text"] = _build_raw_text(result)
    result["internal_diagnostics"] = {
        "decision_confidence": parsed.get("decision_confidence"),
        "policy_applied": (parsed.get("diagnostics") or {}).get("policy_applied"),
        "hard_constraint_summary": (parsed.get("diagnostics") or {}).get(
            "hard_constraint_summary"
        ),
        "soft_tradeoff_summary": (parsed.get("diagnostics") or {}).get(
            "soft_tradeoff_summary"
        ),
        "considered_restaurant_count": (parsed.get("diagnostics") or {}).get(
            "considered_restaurant_count"
        ),
        "model": model,
    }
    return result
