from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from datetime import datetime

from ...api.deps import get_current_user, get_db_session
from ...db.models import Profile, User
from ...schemas import ProfileRead, ProfileUpdate

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
        profile.other_preferences = payload.other_preferences

    profile.updated_at = datetime.utcnow()

    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile
