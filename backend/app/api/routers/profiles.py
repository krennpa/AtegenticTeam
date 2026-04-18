from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, and_
from datetime import datetime

from ...api.deps import get_current_user, get_db_session
from ...db.models import Profile, User, TeamMembership
from ...schemas import (
    ProfileRead,
    ProfileUpdate,
    ProfilePreferenceEventCreate,
    ProfilePreferenceEventRead,
    ProfilePreferenceProgressRead,
    PreferenceQuestionCatalogResponse,
)
from ...preferences.service import (
    compute_profile_progress,
    get_preference_question_catalog,
    normalize_other_preferences,
    rebuild_user_team_preferences,
    record_profile_preference_event,
)

router = APIRouter()


@router.get("/me", response_model=ProfileRead)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    profile = session.exec(select(Profile).where(Profile.user_id == current_user.id)).first()
    if not profile:
        profile = Profile(user_id=current_user.id, display_name=current_user.display_name)
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


@router.put("/me", response_model=ProfileRead)
def update_my_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    profile = session.exec(select(Profile).where(Profile.user_id == current_user.id)).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    if payload.display_name is not None:
        profile.display_name = payload.display_name
    if payload.budget_preference is not None:
        profile.budget_preference = payload.budget_preference
    if payload.allergies is not None:
        profile.allergies = payload.allergies
    if payload.dietary_restrictions is not None:
        profile.dietary_restrictions = payload.dietary_restrictions
    if payload.other_preferences is not None:
        profile.other_preferences = normalize_other_preferences(payload.other_preferences)

    profile.updated_at = datetime.utcnow()

    session.add(profile)
    session.commit()
    session.refresh(profile)
    rebuild_user_team_preferences(session, current_user.id)
    return profile


@router.post("/me/preference-events", response_model=ProfilePreferenceEventRead)
def submit_profile_preference_event(
    payload: ProfilePreferenceEventCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    if payload.team_id:
        membership = session.exec(
            select(TeamMembership).where(
                and_(
                    TeamMembership.team_id == payload.team_id,
                    TeamMembership.user_id == current_user.id,
                    TeamMembership.is_active == True,
                )
            )
        ).first()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not an active member of this team",
            )

    event, _ = record_profile_preference_event(
        session,
        user_id=current_user.id,
        event_type=payload.event_type,
        question_key=payload.question_key,
        answer=payload.answer,
        weight=payload.weight,
        source=payload.source,
        team_id=payload.team_id,
    )
    rebuild_user_team_preferences(session, current_user.id)

    return ProfilePreferenceEventRead(
        id=event.id,
        user_id=event.user_id,
        team_id=event.team_id,
        event_type=event.event_type,
        question_key=event.question_key,
        answer=event.answer,
        weight=event.weight,
        source=event.source,
        created_at=event.created_at.isoformat(),
    )


@router.get("/me/preference-progress", response_model=ProfilePreferenceProgressRead)
def get_my_preference_progress(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    profile = session.exec(select(Profile).where(Profile.user_id == current_user.id)).first()
    if not profile:
        profile = Profile(user_id=current_user.id, display_name=current_user.display_name)
        session.add(profile)
        session.commit()
        session.refresh(profile)

    progress = compute_profile_progress(profile)
    return ProfilePreferenceProgressRead(**progress)


@router.get("/me/preference-questions", response_model=PreferenceQuestionCatalogResponse)
def get_my_preference_questions(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    profile = session.exec(select(Profile).where(Profile.user_id == current_user.id)).first()
    if not profile:
        profile = Profile(user_id=current_user.id, display_name=current_user.display_name)
        session.add(profile)
        session.commit()
        session.refresh(profile)

    catalog = get_preference_question_catalog(profile, limit=limit)
    return PreferenceQuestionCatalogResponse(**catalog)
