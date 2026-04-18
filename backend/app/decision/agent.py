from datetime import datetime
from typing import Any

from sqlmodel import Session

from .context_service import get_or_rebuild_team_decision_context
from .tools import RetrieveMenuMarkdownsTool
from ..integrations.openai_decision_judge import (
    OpenAIDecisionJudgeConfigError,
    OpenAIDecisionJudgeError,
    run_openai_decision_judge,
)


def _extract_first_dish(menu_markdown: str) -> str:
    for raw_line in (menu_markdown or "").splitlines():
        line = raw_line.replace("\u2022", " ").strip().lstrip("-* ").strip()
        if not line:
            continue
        if line.endswith(":"):
            continue
        if len(line) < 4:
            continue
        return line
    return "Chef's recommendation"


def _build_raw_text(result: dict[str, Any]) -> str:
    return (
        f"**Recommendation**: {result.get('recommendation_restaurant_name', '')}\n"
        f"**Dish**: {result.get('recommended_dish', '')}\n"
        f"**Reasoning**: {result.get('explanation_md', '')}"
    )


def _build_fallback_result(menus: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    candidate = next((menu for menu in menus if menu.get("menu_markdown")), None)
    if not candidate and menus:
        candidate = menus[0]

    restaurant_name = ""
    restaurant_url = None
    dish = "Chef's recommendation"
    explanation = (
        "Selected using available team and menu context while keeping preference constraints balanced."
    )
    if candidate:
        restaurant_name = str(
            candidate.get("restaurant_name") or candidate.get("restaurant_url") or ""
        ).strip()
        candidate_url = candidate.get("restaurant_url")
        restaurant_url = (
            str(candidate_url).strip() if isinstance(candidate_url, str) else None
        )
        dish = _extract_first_dish(str(candidate.get("menu_markdown") or ""))

    result: dict[str, Any] = {
        "recommendation_restaurant_name": restaurant_name,
        "recommendation_restaurant_url": restaurant_url,
        "recommended_dish": dish,
        "explanation_md": explanation,
    }
    result["raw_text"] = _build_raw_text(result)
    result["internal_diagnostics"] = {
        "fallback_used": True,
        "fallback_reason": reason,
    }
    return result


async def run_decision_agent(request: dict[str, Any], db_session: Session) -> dict[str, Any]:
    """
    Runs the OpenAI-backed team decision judge.

    Returns the frontend response shape plus internal diagnostics for persistence.
    """
    team_id = str(request.get("team_id") or "")
    restaurant_ids = request.get("restaurant_ids") or []
    user_question = str(
        request.get("user_question")
        or "Based on the team's needs and the restaurant menus, what is the best lunch option? Please provide one restaurant and one specific dish recommendation, along with a brief explanation."
    )

    snapshot = get_or_rebuild_team_decision_context(
        db_session,
        team_id,
        stale_after_seconds=300,
    )
    team_decision_context = snapshot.context_json or {}

    menu_tool = RetrieveMenuMarkdownsTool(db_session=db_session, team_id=team_id)
    menu_result = menu_tool._run(restaurant_ids=restaurant_ids)
    menus = [
        menu
        for menu in (menu_result.get("menus") or [])
        if isinstance(menu, dict) and not menu.get("error")
    ]
    if not menus:
        return _build_fallback_result(
            [],
            "No menu data available for requested restaurants",
        )

    now = datetime.now()
    current_day = now.strftime("%A")
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    try:
        result = await run_openai_decision_judge(
            team_decision_context=team_decision_context,
            menus=menus,
            user_question=user_question,
            current_day=current_day,
            current_date=current_date,
            current_time=current_time,
        )
        return result
    except OpenAIDecisionJudgeConfigError as exc:
        return _build_fallback_result(menus, f"Decision judge misconfigured: {exc}")
    except OpenAIDecisionJudgeError as exc:
        return _build_fallback_result(menus, f"Decision judge failed: {exc}")
    except Exception as exc:
        return _build_fallback_result(menus, f"Unexpected decision judge failure: {exc}")
