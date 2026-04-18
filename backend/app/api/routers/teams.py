from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, and_
from datetime import datetime
from typing import List

from ...api.deps import get_current_user, get_db_session
from ...db.models import Team, TeamMembership, User, Profile, TeamPreference
from ...integrations.google_places import (
    GooglePlacesAPIError,
    GooglePlacesConfigError,
    extract_google_maps_fields,
    resolve_place_by_text,
)
from ...schemas import (
    TeamCreate, TeamRead, TeamUpdate, TeamWithMembersRead, 
    TeamMemberRead, JoinTeamRequest, UserRead, TeamPreferenceRead
)
from ...preferences.service import aggregate_team_preferences

router = APIRouter()


def _require_active_membership(session: Session, team_id: str, user_id: str) -> TeamMembership:
    membership = session.exec(
        select(TeamMembership).where(
            and_(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == user_id,
                TeamMembership.is_active == True,
            )
        )
    ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )
    return membership


async def _resolve_team_location(location: str | None) -> dict:
    normalized_location = (location or "").strip()
    if not normalized_location:
        return {
            "location": None,
            "location_place_id": None,
            "location_lat": None,
            "location_lng": None,
        }

    try:
        result = await resolve_place_by_text(normalized_location)
    except (GooglePlacesConfigError, GooglePlacesAPIError):
        return {
            "location": normalized_location,
            "location_place_id": None,
            "location_lat": None,
            "location_lng": None,
        }

    google_maps = extract_google_maps_fields(result or {})
    if not google_maps:
        return {
            "location": normalized_location,
            "location_place_id": None,
            "location_lat": None,
            "location_lng": None,
        }

    return {
        "location": google_maps.get("formatted_address") or google_maps.get("display_name") or normalized_location,
        "location_place_id": google_maps.get("place_id"),
        "location_lat": google_maps.get("lat"),
        "location_lng": google_maps.get("lng"),
    }


@router.get("/{team_id}/preferences", response_model=TeamPreferenceRead)
def get_team_preferences(
    team_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    team = session.exec(select(Team).where(Team.id == team_id)).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    _require_active_membership(session, team_id, current_user.id)

    team_preference = session.exec(
        select(TeamPreference).where(TeamPreference.team_id == team_id)
    ).first()
    if not team_preference:
        team_preference = aggregate_team_preferences(session, team_id)

    return TeamPreferenceRead(
        id=team_preference.id,
        team_id=team_preference.team_id,
        budget_preference=team_preference.budget_preference,
        allergies=team_preference.allergies,
        dietary_restrictions=team_preference.dietary_restrictions,
        other_preferences=team_preference.other_preferences,
        member_count=team_preference.member_count,
        created_at=team_preference.created_at.isoformat(),
        updated_at=team_preference.updated_at.isoformat(),
    )


@router.post("/{team_id}/preferences/rebuild", response_model=TeamPreferenceRead)
def rebuild_team_preferences(
    team_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    team = session.exec(select(Team).where(Team.id == team_id)).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    _require_active_membership(session, team_id, current_user.id)

    team_preference = aggregate_team_preferences(session, team_id)
    return TeamPreferenceRead(
        id=team_preference.id,
        team_id=team_preference.team_id,
        budget_preference=team_preference.budget_preference,
        allergies=team_preference.allergies,
        dietary_restrictions=team_preference.dietary_restrictions,
        other_preferences=team_preference.other_preferences,
        member_count=team_preference.member_count,
        created_at=team_preference.created_at.isoformat(),
        updated_at=team_preference.updated_at.isoformat(),
    )


@router.post("/", response_model=TeamRead)
async def create_team(
    payload: TeamCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Create a new team"""
    location_fields = await _resolve_team_location(payload.location)
    team = Team(
        name=payload.name,
        description=payload.description,
        location=location_fields["location"],
        location_place_id=location_fields["location_place_id"],
        location_lat=location_fields["location_lat"],
        location_lng=location_fields["location_lng"],
        creator_user_id=current_user.id,
        max_members=payload.max_members,
    )
    session.add(team)
    session.commit()
    session.refresh(team)
    
    # Automatically add creator as first member
    membership = TeamMembership(
        team_id=team.id,
        user_id=current_user.id,
    )
    session.add(membership)
    session.commit()
    aggregate_team_preferences(session, team.id)
    
    return TeamRead(
        id=team.id,
        name=team.name,
        description=team.description,
        location=team.location,
        location_place_id=team.location_place_id,
        location_lat=team.location_lat,
        location_lng=team.location_lng,
        creator_user_id=team.creator_user_id,
        is_active=team.is_active,
        max_members=team.max_members,
        member_count=1,
        created_at=team.created_at.isoformat(),
    )


@router.get("/", response_model=List[TeamRead])
def list_my_teams(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """List all teams the current user is a member of"""
    # Get teams where user is a member
    memberships = session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True
        ))
    ).all()
    
    teams = []
    for membership in memberships:
        team = session.exec(select(Team).where(Team.id == membership.team_id)).first()
        if team and team.is_active:
            # Count active members
            member_count = session.exec(
                select(TeamMembership)
                .where(and_(
                    TeamMembership.team_id == team.id,
                    TeamMembership.is_active == True
                ))
            ).all()
            
            teams.append(TeamRead(
                id=team.id,
                name=team.name,
                description=team.description,
                location=team.location,
                location_place_id=team.location_place_id,
                location_lat=team.location_lat,
                location_lng=team.location_lng,
                creator_user_id=team.creator_user_id,
                is_active=team.is_active,
                max_members=team.max_members,
                member_count=len(member_count),
                created_at=team.created_at.isoformat(),
            ))
    
    return teams


@router.get("/{team_id}", response_model=TeamWithMembersRead)
def get_team_details(
    team_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Get detailed team information including members (only if user is a member)"""
    # Check if user is a member of this team
    membership = session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True
        ))
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this team"
        )
    
    team = session.exec(select(Team).where(Team.id == team_id)).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Get all active members with their display names
    memberships = session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.team_id == team_id,
            TeamMembership.is_active == True
        ))
    ).all()
    
    members = []
    for member in memberships:
        user = session.exec(select(User).where(User.id == member.user_id)).first()
        profile = session.exec(select(Profile).where(Profile.user_id == member.user_id)).first()
        
        display_name = None
        if profile and profile.display_name:
            display_name = profile.display_name
        elif user and user.display_name:
            display_name = user.display_name
        
        members.append(TeamMemberRead(
            id=member.id,
            user_id=member.user_id,
            display_name=display_name,
            joined_at=member.joined_at.isoformat(),
        ))
    
    return TeamWithMembersRead(
        id=team.id,
        name=team.name,
        description=team.description,
        location=team.location,
        location_place_id=team.location_place_id,
        location_lat=team.location_lat,
        location_lng=team.location_lng,
        creator_user_id=team.creator_user_id,
        is_active=team.is_active,
        max_members=team.max_members,
        members=members,
        created_at=team.created_at.isoformat(),
    )


@router.post("/join", response_model=TeamRead)
def join_team(
    payload: JoinTeamRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Join an existing team"""
    team = session.exec(select(Team).where(Team.id == payload.team_id)).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    if not team.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team is not active"
        )
    
    # Check if user is already a member
    existing_membership = session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.team_id == payload.team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True
        ))
    ).first()
    
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this team"
        )
    
    # Check max members limit
    if team.max_members:
        current_member_count = len(session.exec(
            select(TeamMembership)
            .where(and_(
                TeamMembership.team_id == payload.team_id,
                TeamMembership.is_active == True
            ))
        ).all())
        
        if current_member_count >= team.max_members:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team is full"
            )
    
    # Create membership
    membership = TeamMembership(
        team_id=payload.team_id,
        user_id=current_user.id,
    )
    session.add(membership)
    session.commit()
    aggregate_team_preferences(session, payload.team_id)
    
    # Return updated team info
    member_count = len(session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.team_id == payload.team_id,
            TeamMembership.is_active == True
        ))
    ).all())
    
    return TeamRead(
        id=team.id,
        name=team.name,
        description=team.description,
        location=team.location,
        location_place_id=team.location_place_id,
        location_lat=team.location_lat,
        location_lng=team.location_lng,
        creator_user_id=team.creator_user_id,
        is_active=team.is_active,
        max_members=team.max_members,
        member_count=member_count,
        created_at=team.created_at.isoformat(),
    )


@router.delete("/{team_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_team(
    team_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Leave a team"""
    membership = session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True
        ))
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this team"
        )
    
    # Mark membership as inactive instead of deleting
    membership.is_active = False
    session.add(membership)
    session.commit()
    aggregate_team_preferences(session, team_id)
    
    return None


@router.put("/{team_id}", response_model=TeamRead)
async def update_team(
    team_id: str,
    payload: TeamUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Update team details (only team creator can do this)"""
    team = session.exec(select(Team).where(Team.id == team_id)).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    if team.creator_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team creator can update team details"
        )
    
    # Update fields
    if payload.name is not None:
        team.name = payload.name
    if payload.description is not None:
        team.description = payload.description
    if payload.location is not None:
        location_fields = await _resolve_team_location(payload.location)
        team.location = location_fields["location"]
        team.location_place_id = location_fields["location_place_id"]
        team.location_lat = location_fields["location_lat"]
        team.location_lng = location_fields["location_lng"]
    if payload.max_members is not None:
        team.max_members = payload.max_members
    if payload.is_active is not None:
        team.is_active = payload.is_active
    
    team.updated_at = datetime.utcnow()
    
    session.add(team)
    session.commit()
    session.refresh(team)
    
    # Get member count
    member_count = len(session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.team_id == team_id,
            TeamMembership.is_active == True
        ))
    ).all())
    
    return TeamRead(
        id=team.id,
        name=team.name,
        description=team.description,
        location=team.location,
        location_place_id=team.location_place_id,
        location_lat=team.location_lat,
        location_lng=team.location_lng,
        creator_user_id=team.creator_user_id,
        is_active=team.is_active,
        max_members=team.max_members,
        member_count=member_count,
        created_at=team.created_at.isoformat(),
    )


@router.get("/search/{team_name}", response_model=List[TeamRead])
def search_teams_by_name(
    team_name: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Search for active teams by name (for joining)"""
    teams = session.exec(
        select(Team)
        .where(and_(
            Team.name.contains(team_name),
            Team.is_active == True
        ))
    ).all()
    
    result = []
    for team in teams:
        # Count active members
        member_count = len(session.exec(
            select(TeamMembership)
            .where(and_(
                TeamMembership.team_id == team.id,
                TeamMembership.is_active == True
            ))
        ).all())
        
        result.append(TeamRead(
            id=team.id,
            name=team.name,
            description=team.description,
            location=team.location,
            location_place_id=team.location_place_id,
            location_lat=team.location_lat,
            location_lng=team.location_lng,
            creator_user_id=team.creator_user_id,
            is_active=team.is_active,
            max_members=team.max_members,
            member_count=member_count,
            created_at=team.created_at.isoformat(),
        ))
    
    return result


@router.get("/{team_id}/search-users/{search_term}", response_model=List[UserRead])
def search_users_for_team_invitation(
    team_id: str,
    search_term: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Search for users by display name or email to invite to team (only team members can do this)"""
    # Check if current user is a member of this team
    membership = session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True
        ))
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a team member to search for users"
        )
    
    # Get users already in this team to exclude them
    existing_memberships = session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.team_id == team_id,
            TeamMembership.is_active == True
        ))
    ).all()
    existing_user_ids = {m.user_id for m in existing_memberships}
    
    # Search for users by display name or email
    users = session.exec(
        select(User)
        .where(
            (User.display_name.contains(search_term)) |
            (User.email.contains(search_term))
        )
    ).all()
    
    # Filter out users already in the team and limit results
    result = []
    for user in users:
        if user.id not in existing_user_ids and len(result) < 10:
            result.append(UserRead(
                id=user.id,
                email=user.email,
                display_name=user.display_name
            ))
    
    return result


@router.post("/{team_id}/invite/{user_id}", response_model=TeamRead)
def invite_user_to_team(
    team_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Invite a user to join the team (only team members can do this)"""
    # Check if current user is a member of this team
    membership = session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True
        ))
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a team member to invite users"
        )
    
    # Check if team exists
    team = session.exec(select(Team).where(Team.id == team_id)).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check if user exists
    user_to_invite = session.exec(select(User).where(User.id == user_id)).first()
    if not user_to_invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user is already a member
    existing_membership = session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
            TeamMembership.is_active == True
        ))
    ).first()
    
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this team"
        )
    
    # Check max members limit
    if team.max_members:
        current_member_count = len(session.exec(
            select(TeamMembership)
            .where(and_(
                TeamMembership.team_id == team_id,
                TeamMembership.is_active == True
            ))
        ).all())
        
        if current_member_count >= team.max_members:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team is full"
            )
    
    # Create membership
    new_membership = TeamMembership(
        team_id=team_id,
        user_id=user_id,
    )
    session.add(new_membership)
    session.commit()
    aggregate_team_preferences(session, team_id)
    
    # Return updated team info
    member_count = len(session.exec(
        select(TeamMembership)
        .where(and_(
            TeamMembership.team_id == team_id,
            TeamMembership.is_active == True
        ))
    ).all())
    
    return TeamRead(
        id=team.id,
        name=team.name,
        description=team.description,
        location=team.location,
        location_place_id=team.location_place_id,
        location_lat=team.location_lat,
        location_lng=team.location_lng,
        creator_user_id=team.creator_user_id,
        is_active=team.is_active,
        max_members=team.max_members,
        member_count=member_count,
        created_at=team.created_at.isoformat(),
    )
