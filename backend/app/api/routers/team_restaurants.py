"""
API endpoints for managing team-specific restaurant sources and cache settings.
"""
from __future__ import annotations

from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ...api.deps import get_current_user, get_db_session
from ...db.models import User, Restaurant, TeamRestaurant, Team, TeamMembership, CacheStrategy
from ...schemas import TeamRestaurantRead, TeamRestaurantCacheUpdate
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/teams/{team_id}/restaurants", response_model=List[TeamRestaurantRead])
async def get_team_restaurants(
    team_id: str,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get all restaurant sources for a specific team."""
    # Validate team membership
    team = session.exec(select(Team).where(Team.id == team_id)).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    membership = session.exec(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True,
        )
    ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    # Get all team restaurants with their restaurant data
    team_restaurants = session.exec(
        select(TeamRestaurant, Restaurant)
        .join(Restaurant, TeamRestaurant.restaurant_id == Restaurant.id)
        .where(TeamRestaurant.team_id == team_id)
        .order_by(TeamRestaurant.created_at.desc())
    ).all()

    result = []
    for team_restaurant, restaurant in team_restaurants:
        # Check if cache is valid
        is_cache_valid = False
        if team_restaurant.next_scrape_at:
            is_cache_valid = datetime.utcnow() < team_restaurant.next_scrape_at

        result.append(TeamRestaurantRead(
            id=team_restaurant.id,
            team_id=team_restaurant.team_id,
            restaurant_id=team_restaurant.restaurant_id,
            display_name=team_restaurant.display_name or restaurant.display_name,
            cache_strategy=team_restaurant.cache_strategy,
            cache_duration_hours=team_restaurant.cache_duration_hours,
            next_scrape_at=team_restaurant.next_scrape_at.isoformat() if team_restaurant.next_scrape_at else None,
            last_scraped_at=team_restaurant.last_scraped_at.isoformat() if team_restaurant.last_scraped_at else None,
            is_active=team_restaurant.is_active,
            added_by_user_id=team_restaurant.added_by_user_id,
            restaurant_url=restaurant.url,
            is_cache_valid=is_cache_valid,
        ))

    return result


@router.put("/teams/{team_id}/restaurants/{restaurant_id}/cache", response_model=TeamRestaurantRead)
async def update_team_restaurant_cache(
    team_id: str,
    restaurant_id: str,
    payload: TeamRestaurantCacheUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Update cache settings for a team-specific restaurant."""
    # Validate team membership
    team = session.exec(select(Team).where(Team.id == team_id)).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    membership = session.exec(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True,
        )
    ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    # Get team restaurant
    team_restaurant = session.exec(
        select(TeamRestaurant).where(
            TeamRestaurant.team_id == team_id,
            TeamRestaurant.restaurant_id == restaurant_id
        )
    ).first()
    
    if not team_restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found in this team"
        )

    # Update cache settings
    if payload.cache_strategy is not None:
        team_restaurant.cache_strategy = payload.cache_strategy
    if payload.cache_duration_hours is not None:
        team_restaurant.cache_duration_hours = payload.cache_duration_hours
    
    team_restaurant.updated_at = datetime.utcnow()
    session.add(team_restaurant)
    session.commit()
    session.refresh(team_restaurant)

    # Get restaurant for response
    restaurant = session.get(Restaurant, restaurant_id)
    
    # Check if cache is valid
    is_cache_valid = False
    if team_restaurant.next_scrape_at:
        is_cache_valid = datetime.utcnow() < team_restaurant.next_scrape_at

    return TeamRestaurantRead(
        id=team_restaurant.id,
        team_id=team_restaurant.team_id,
        restaurant_id=team_restaurant.restaurant_id,
        display_name=team_restaurant.display_name or (restaurant.display_name if restaurant else None),
        cache_strategy=team_restaurant.cache_strategy,
        cache_duration_hours=team_restaurant.cache_duration_hours,
        next_scrape_at=team_restaurant.next_scrape_at.isoformat() if team_restaurant.next_scrape_at else None,
        last_scraped_at=team_restaurant.last_scraped_at.isoformat() if team_restaurant.last_scraped_at else None,
        is_active=team_restaurant.is_active,
        added_by_user_id=team_restaurant.added_by_user_id,
        restaurant_url=restaurant.url if restaurant else "",
        is_cache_valid=is_cache_valid,
    )


@router.delete("/teams/{team_id}/restaurants/{restaurant_id}")
async def remove_team_restaurant(
    team_id: str,
    restaurant_id: str,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Remove a restaurant from a team (soft delete by setting is_active=False)."""
    # Validate team membership
    team = session.exec(select(Team).where(Team.id == team_id)).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    membership = session.exec(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True,
        )
    ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    # Get team restaurant
    team_restaurant = session.exec(
        select(TeamRestaurant).where(
            TeamRestaurant.team_id == team_id,
            TeamRestaurant.restaurant_id == restaurant_id
        )
    ).first()
    
    if not team_restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found in this team"
        )

    # Soft delete
    team_restaurant.is_active = False
    team_restaurant.updated_at = datetime.utcnow()
    session.add(team_restaurant)
    session.commit()

    return {"message": "Restaurant removed from team successfully"}
