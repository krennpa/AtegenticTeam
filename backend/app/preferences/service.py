from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List

from sqlmodel import Session, select

from ..db.models import (
    BudgetPreference,
    Profile,
    ProfilePreferenceEvent,
    TeamMembership,
    TeamPreference,
)


SUPPORTED_EVENT_TYPES = {
    "this_or_that",
    "veto_card",
    "mood_pick",
    "choice",
    "slider",
}

CANONICAL_AREAS = ["cuisine", "diet", "budget", "spice", "mood", "pace"]

PREFERENCE_QUESTION_CATALOG: List[Dict[str, Any]] = [
    {
        "question_key": "cuisine:pairing",
        "event_type": "this_or_that",
        "area": "cuisine",
        "prompt": "What sounds better for your next team lunch?",
        "options": [
            {"label": "Asian", "value": "asian"},
            {"label": "Mediterranean", "value": "mediterranean"},
        ],
    },
    {
        "question_key": "diet:flexibility",
        "event_type": "choice",
        "area": "diet",
        "prompt": "How strict are your dietary preferences this week?",
        "options": [
            {"label": "Very strict", "value": "strict"},
            {"label": "Flexible", "value": "flexible"},
            {"label": "No special diet", "value": "none"},
        ],
    },
    {
        "question_key": "budget:comfort",
        "event_type": "choice",
        "area": "budget",
        "prompt": "What price vibe fits your normal lunch best?",
        "options": [
            {"label": "Budget", "value": "low"},
            {"label": "Balanced", "value": "medium"},
            {"label": "Premium", "value": "high"},
        ],
    },
    {
        "question_key": "spice:tolerance",
        "event_type": "slider",
        "area": "spice",
        "prompt": "How much spice do you enjoy?",
        "options": [
            {"label": "Mild", "value": "low"},
            {"label": "Medium", "value": "medium"},
            {"label": "Hot", "value": "high"},
        ],
    },
    {
        "question_key": "mood:today",
        "event_type": "mood_pick",
        "area": "mood",
        "prompt": "Pick your current lunch mood.",
        "options": [
            {"label": "Comfort", "value": "comfort"},
            {"label": "Light", "value": "light"},
            {"label": "Adventurous", "value": "adventurous"},
        ],
    },
    {
        "question_key": "pace:lunch_break",
        "event_type": "choice",
        "area": "pace",
        "prompt": "How much time do you usually have for lunch?",
        "options": [
            {"label": "Quick 20 min", "value": "quick"},
            {"label": "30-45 min", "value": "moderate"},
            {"label": "Long relaxed", "value": "slow"},
        ],
    },
    {
        "question_key": "cuisine:no_go",
        "event_type": "veto_card",
        "area": "cuisine",
        "prompt": "Any cuisine you want to avoid right now?",
        "options": [
            {"label": "Fast food", "value": "fast_food"},
            {"label": "Heavy fried", "value": "fried"},
            {"label": "No veto", "value": "none"},
        ],
    },
]


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def _normalize_text_list(values: List[Any]) -> List[str]:
    seen = set()
    normalized: List[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        text = _normalize_text(item)
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def normalize_other_preferences(data: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = data if isinstance(data, dict) else {}

    normalized: Dict[str, Any] = {}
    for key, value in raw.items():
        key_norm = _normalize_text(str(key)).replace(" ", "_")
        if isinstance(value, str):
            normalized[key_norm] = _normalize_text(value)
        elif isinstance(value, list):
            normalized[key_norm] = _normalize_text_list(value)
        else:
            normalized[key_norm] = value

    signals = normalized.get("signals")
    if not isinstance(signals, dict):
        normalized["signals"] = {}

    dislikes = normalized.get("dislikes")
    if not isinstance(dislikes, list):
        normalized["dislikes"] = []
    normalized["dislikes"] = _normalize_text_list(normalized["dislikes"])

    moods = normalized.get("recent_moods")
    if not isinstance(moods, list):
        normalized["recent_moods"] = []
    normalized["recent_moods"] = _normalize_text_list(normalized["recent_moods"])[:8]

    areas_seen = normalized.get("areas_seen")
    if not isinstance(areas_seen, list):
        normalized["areas_seen"] = []
    normalized["areas_seen"] = _normalize_text_list(normalized["areas_seen"])

    gamification = normalized.get("gamification")
    if not isinstance(gamification, dict):
        gamification = {}
    gamification.setdefault("points", 0)
    gamification.setdefault("level", 1)
    gamification.setdefault("total_events", 0)
    gamification.setdefault("last_event_at", None)
    normalized["gamification"] = gamification

    return normalized


def _extract_area(question_key: str) -> str:
    key = _normalize_text(question_key)
    if ":" in key:
        key = key.split(":", 1)[0]
    if key in CANONICAL_AREAS:
        return key
    return "custom"


def _ensure_profile(session: Session, user_id: str) -> Profile:
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if profile:
        return profile

    profile = Profile(user_id=user_id)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def compute_profile_progress(profile: Profile) -> Dict[str, Any]:
    preferences = normalize_other_preferences(profile.other_preferences)
    game = preferences.get("gamification", {})
    areas_seen = preferences.get("areas_seen", [])

    covered = [area for area in CANONICAL_AREAS if area in areas_seen]
    completion = int((len(covered) / len(CANONICAL_AREAS)) * 100)
    suggested_next = [area for area in CANONICAL_AREAS if area not in covered]

    return {
        "total_events": int(game.get("total_events", 0)),
        "points": int(game.get("points", 0)),
        "level": int(game.get("level", 1)),
        "completion_percent": completion,
        "last_event_at": game.get("last_event_at"),
        "covered_areas": covered,
        "suggested_next_areas": suggested_next,
    }


def get_preference_question_catalog(profile: Profile, limit: int = 5) -> Dict[str, Any]:
    safe_limit = max(1, min(12, int(limit)))
    progress = compute_profile_progress(profile)
    recommended_areas: List[str] = progress.get("suggested_next_areas", [])

    if not recommended_areas:
        recommended_areas = CANONICAL_AREAS

    questions_by_area: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for question in PREFERENCE_QUESTION_CATALOG:
        questions_by_area[question["area"]].append(question)

    selected: List[Dict[str, Any]] = []
    seen_keys = set()

    for area in recommended_areas:
        for question in questions_by_area.get(area, []):
            key = question["question_key"]
            if key in seen_keys:
                continue
            selected.append(question)
            seen_keys.add(key)
            break
        if len(selected) >= safe_limit:
            break

    if len(selected) < safe_limit:
        for question in PREFERENCE_QUESTION_CATALOG:
            key = question["question_key"]
            if key in seen_keys:
                continue
            selected.append(question)
            seen_keys.add(key)
            if len(selected) >= safe_limit:
                break

    return {
        "recommended_areas": recommended_areas,
        "questions": selected,
    }


def record_profile_preference_event(
    session: Session,
    *,
    user_id: str,
    event_type: str,
    question_key: str,
    answer: Any,
    weight: float = 1.0,
    source: str = "user_gameplay",
    team_id: str | None = None,
) -> tuple[ProfilePreferenceEvent, Profile]:
    normalized_event_type = _normalize_text(event_type)
    if normalized_event_type not in SUPPORTED_EVENT_TYPES:
        normalized_event_type = "choice"

    profile = _ensure_profile(session, user_id)
    preferences = normalize_other_preferences(profile.other_preferences)
    now = datetime.utcnow()

    event = ProfilePreferenceEvent(
        user_id=user_id,
        team_id=team_id,
        event_type=normalized_event_type,
        question_key=_normalize_text(question_key),
        answer=answer,
        weight=max(0.1, float(weight)),
        source=_normalize_text(source) if source else "user_gameplay",
    )

    if normalized_event_type in {"this_or_that", "choice", "slider"}:
        preferences["signals"][event.question_key] = {
            "value": answer,
            "weight": event.weight,
            "source": event.source,
            "updated_at": now.isoformat(),
        }
    elif normalized_event_type == "veto_card":
        if isinstance(answer, list):
            preferences["dislikes"].extend(_normalize_text_list(answer))
        elif isinstance(answer, str):
            preferences["dislikes"].append(_normalize_text(answer))
        preferences["dislikes"] = _normalize_text_list(preferences["dislikes"])
    elif normalized_event_type == "mood_pick":
        mood_value = _normalize_text(str(answer)) if answer is not None else ""
        if mood_value:
            preferences["recent_moods"] = [
                mood for mood in preferences["recent_moods"] if mood != mood_value
            ]
            preferences["recent_moods"].insert(0, mood_value)
            preferences["recent_moods"] = preferences["recent_moods"][:8]

    area = _extract_area(event.question_key)
    if area not in preferences["areas_seen"]:
        preferences["areas_seen"].append(area)

    points_delta = max(1, round(event.weight * 10))
    game = preferences["gamification"]
    game["points"] = int(game.get("points", 0)) + points_delta
    game["total_events"] = int(game.get("total_events", 0)) + 1
    game["level"] = 1 + game["points"] // 120
    game["last_event_at"] = now.isoformat()

    profile.other_preferences = preferences
    profile.updated_at = now

    session.add(event)
    session.add(profile)
    session.commit()
    session.refresh(event)
    session.refresh(profile)
    return event, profile


def _choose_budget(budgets: List[BudgetPreference]) -> BudgetPreference:
    if not budgets:
        return BudgetPreference.medium

    budget_counter = Counter([budget.value for budget in budgets])
    most_common = budget_counter.most_common()
    top_count = most_common[0][1]
    top_values = [value for value, count in most_common if count == top_count]
    if BudgetPreference.medium.value in top_values:
        return BudgetPreference.medium
    return BudgetPreference(top_values[0])


def _aggregate_other_preferences(profiles: List[Profile]) -> Dict[str, Any]:
    signals_by_key: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    dislikes: List[str] = []
    moods: List[str] = []
    areas_seen: List[str] = []

    for profile in profiles:
        preferences = normalize_other_preferences(profile.other_preferences)
        signals = preferences.get("signals", {})
        if isinstance(signals, dict):
            for key, value in signals.items():
                if isinstance(value, dict):
                    signals_by_key[key].append(value)
        dislikes.extend(preferences.get("dislikes", []))
        moods.extend(preferences.get("recent_moods", []))
        areas_seen.extend(preferences.get("areas_seen", []))

    aggregated_signals: Dict[str, Dict[str, Any]] = {}
    for key, values in signals_by_key.items():
        value_counter = Counter()
        for entry in values:
            value = entry.get("value")
            value_counter[str(value)] += 1
        if not value_counter:
            continue
        selected_value, support = value_counter.most_common(1)[0]
        aggregated_signals[key] = {
            "value": selected_value,
            "support": support,
            "member_count": len(values),
        }

    mood_counter = Counter(moods)
    top_moods = [mood for mood, _ in mood_counter.most_common(5)]

    return {
        "signals": aggregated_signals,
        "dislikes": _normalize_text_list(dislikes),
        "recent_moods": top_moods,
        "areas_seen": _normalize_text_list(areas_seen),
        "aggregation": {
            "profile_count": len(profiles),
            "updated_at": datetime.utcnow().isoformat(),
        },
    }


def aggregate_team_preferences(session: Session, team_id: str) -> TeamPreference:
    memberships = session.exec(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.is_active == True,
        )
    ).all()

    profiles: List[Profile] = []
    for membership in memberships:
        profile = session.exec(
            select(Profile).where(Profile.user_id == membership.user_id)
        ).first()
        if profile:
            profiles.append(profile)

    budget = _choose_budget([profile.budget_preference for profile in profiles])
    allergies: List[str] = []
    dietary: List[str] = []
    for profile in profiles:
        allergies.extend(profile.allergies)
        dietary.extend(profile.dietary_restrictions)

    team_preference = session.exec(
        select(TeamPreference).where(TeamPreference.team_id == team_id)
    ).first()
    if not team_preference:
        team_preference = TeamPreference(team_id=team_id)

    team_preference.budget_preference = budget
    team_preference.allergies = _normalize_text_list(allergies)
    team_preference.dietary_restrictions = _normalize_text_list(dietary)
    team_preference.other_preferences = _aggregate_other_preferences(profiles)
    team_preference.member_count = len(memberships)
    team_preference.updated_at = datetime.utcnow()

    session.add(team_preference)
    session.commit()
    session.refresh(team_preference)
    return team_preference


def rebuild_user_team_preferences(session: Session, user_id: str) -> None:
    memberships = session.exec(
        select(TeamMembership).where(
            TeamMembership.user_id == user_id,
            TeamMembership.is_active == True,
        )
    ).all()

    for membership in memberships:
        aggregate_team_preferences(session, membership.team_id)
