from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlmodel import Session, select

from ..db.models import Profile, Team, TeamDecisionContext, TeamMembership
from ..preferences.service import normalize_other_preferences


SCHEMA_VERSION = "v1"


def _normalize_text_list(values: list[Any] | None) -> list[str]:
    if not isinstance(values, list):
        return []

    seen = set()
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip().lower()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def _coerce_float(value: Any, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_member_soft_preferences(profile: Profile) -> dict[str, Any]:
    preferences = normalize_other_preferences(profile.other_preferences)
    raw_signals = preferences.get("signals", {})
    signals: dict[str, dict[str, Any]] = {}

    if isinstance(raw_signals, dict):
        for key, raw_value in raw_signals.items():
            if not isinstance(key, str) or not isinstance(raw_value, dict):
                continue
            signal_value = raw_value.get("value")
            if signal_value is None:
                continue
            signals[key] = {
                "value": str(signal_value).strip().lower(),
                "weight": _coerce_float(raw_value.get("weight"), default=1.0),
                "updated_at": raw_value.get("updated_at"),
                "source": raw_value.get("source"),
            }

    return {
        "budget_preference": profile.budget_preference.value if profile.budget_preference else None,
        "signals": signals,
        "dislikes": _normalize_text_list(preferences.get("dislikes")),
        "recent_moods": _normalize_text_list(preferences.get("recent_moods")),
    }


def build_team_decision_context_payload(session: Session, team_id: str) -> dict[str, Any]:
    team = session.exec(select(Team).where(Team.id == team_id)).first()
    if not team:
        raise ValueError("Team not found")

    memberships = session.exec(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.is_active == True,
        )
    ).all()

    user_ids = [membership.user_id for membership in memberships]
    profiles: list[Profile] = []
    if user_ids:
        profiles = session.exec(select(Profile).where(Profile.user_id.in_(user_ids))).all()
    profile_by_user_id = {profile.user_id: profile for profile in profiles}

    members: list[dict[str, Any]] = []
    missing_member_refs: list[str] = []
    budget_distribution: Counter[str] = Counter()
    signal_frequencies: dict[str, Counter[str]] = defaultdict(Counter)
    dislike_frequencies: Counter[str] = Counter()
    mood_frequencies: Counter[str] = Counter()
    allergy_frequencies: Counter[str] = Counter()
    dietary_frequencies: Counter[str] = Counter()

    for membership in memberships:
        profile = profile_by_user_id.get(membership.user_id)
        if not profile:
            missing_member_refs.append(membership.id)
            members.append(
                {
                    "member_ref": membership.id,
                    "has_profile": False,
                    "hard_constraints": {
                        "allergies": [],
                        "dietary_restrictions": [],
                    },
                    "soft_preferences": {
                        "budget_preference": None,
                        "signals": {},
                        "dislikes": [],
                        "recent_moods": [],
                    },
                }
            )
            continue

        allergies = _normalize_text_list(profile.allergies)
        dietary_restrictions = _normalize_text_list(profile.dietary_restrictions)
        soft_preferences = _extract_member_soft_preferences(profile)

        for allergy in allergies:
            allergy_frequencies[allergy] += 1
        for dietary in dietary_restrictions:
            dietary_frequencies[dietary] += 1

        budget = soft_preferences.get("budget_preference")
        if isinstance(budget, str) and budget:
            budget_distribution[budget] += 1

        for signal_key, signal_data in (soft_preferences.get("signals") or {}).items():
            signal_value = str(signal_data.get("value") or "").strip().lower()
            if signal_value:
                signal_frequencies[signal_key][signal_value] += 1

        for dislike in soft_preferences.get("dislikes") or []:
            dislike_frequencies[dislike] += 1

        for mood in soft_preferences.get("recent_moods") or []:
            mood_frequencies[mood] += 1

        members.append(
            {
                "member_ref": membership.id,
                "has_profile": True,
                "hard_constraints": {
                    "allergies": allergies,
                    "dietary_restrictions": dietary_restrictions,
                },
                "soft_preferences": soft_preferences,
            }
        )

    now = datetime.utcnow().isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "team_id": team_id,
        "team_base": {
            "location": team.location,
            "place_id": team.location_place_id,
            "lat": team.location_lat,
            "lng": team.location_lng,
        },
        "policy": "max_min_fairness",
        "coverage": {
            "active_member_count": len(memberships),
            "profiled_member_count": len(memberships) - len(missing_member_refs),
            "missing_member_refs": missing_member_refs,
            "is_partial": len(missing_member_refs) > 0,
        },
        "members": members,
        "aggregates": {
            "budget_distribution": {
                "low": budget_distribution.get("low", 0),
                "medium": budget_distribution.get("medium", 0),
                "high": budget_distribution.get("high", 0),
            },
            "signal_frequencies": {
                signal_key: dict(counter)
                for signal_key, counter in signal_frequencies.items()
            },
            "dislike_frequencies": dict(dislike_frequencies),
            "mood_frequencies": dict(mood_frequencies),
            "hard_constraint_summary": {
                "allergy_frequencies": dict(allergy_frequencies),
                "dietary_restriction_frequencies": dict(dietary_frequencies),
            },
        },
        "generated_at": now,
    }


def rebuild_team_decision_context(session: Session, team_id: str) -> TeamDecisionContext:
    payload = build_team_decision_context_payload(session, team_id)
    now = datetime.utcnow()

    snapshot = session.exec(
        select(TeamDecisionContext).where(TeamDecisionContext.team_id == team_id)
    ).first()
    if not snapshot:
        snapshot = TeamDecisionContext(team_id=team_id)

    snapshot.schema_version = SCHEMA_VERSION
    snapshot.context_json = payload
    snapshot.updated_at = now

    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


def get_or_rebuild_team_decision_context(
    session: Session,
    team_id: str,
    *,
    stale_after_seconds: int = 300,
) -> TeamDecisionContext:
    snapshot = session.exec(
        select(TeamDecisionContext).where(TeamDecisionContext.team_id == team_id)
    ).first()
    if not snapshot:
        return rebuild_team_decision_context(session, team_id)

    stale_cutoff = datetime.utcnow() - timedelta(seconds=max(0, stale_after_seconds))
    if snapshot.updated_at < stale_cutoff or not snapshot.context_json:
        return rebuild_team_decision_context(session, team_id)

    return snapshot


def rebuild_user_team_decision_contexts(session: Session, user_id: str) -> None:
    memberships = session.exec(
        select(TeamMembership).where(
            TeamMembership.user_id == user_id,
            TeamMembership.is_active == True,
        )
    ).all()
    team_ids = {membership.team_id for membership in memberships}
    for team_id in team_ids:
        rebuild_team_decision_context(session, team_id)

