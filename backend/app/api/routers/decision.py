from __future__ import annotations

from typing import List, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ...api.deps import get_current_user, get_db_session
from ...db.models import User, Restaurant, RestaurantDocument, Team, TeamMembership, DecisionRun, CacheStrategy, TeamRestaurant, Notification
from ...scraping.scraper import scrape_url
import logging
from ...decision.agent import run_decision_agent
from ...decision.menu_analyzer import extract_menu_metadata
from ...decision.schemas import (
    AgentDecisionRequest,
    AgentDecisionResponse,
    IngestRestaurantsRequest,
    IngestRestaurantsResponse,
    ExistingRestaurantsResponse,
    ExistingRestaurant,
)
from ...schemas import DecisionRunRead

logger = logging.getLogger(__name__)

router = APIRouter()


def _should_rescrape_restaurant(team_restaurant: TeamRestaurant, latest_doc: RestaurantDocument | None) -> tuple[bool, str]:
    """Determine if a restaurant should be re-scraped based on team-specific cache strategy.
    
    Args:
        team_restaurant: TeamRestaurant model with team-specific cache settings
        latest_doc: Latest RestaurantDocument for this restaurant (if any)
        
    Returns:
        Tuple of (should_rescrape: bool, reason: str)
    """
    if not latest_doc:
        return True, "No existing menu data found"
    
    # Use the intelligent caching system
    if team_restaurant.cache_strategy == CacheStrategy.no_cache:
        return True, "Cache disabled for this team-restaurant"
    
    # Check if cache is still valid
    if team_restaurant.next_scrape_at and datetime.utcnow() < team_restaurant.next_scrape_at:
        return False, f"Cache valid until {team_restaurant.next_scrape_at.isoformat()}"
    
    # Cache expired or not set - need to rescrape
    now = datetime.utcnow()
    doc_age = now - latest_doc.created_at
    hours_old = doc_age.total_seconds() / 3600
    
    return True, f"Cache expired ({team_restaurant.cache_strategy}, {hours_old:.1f} hours old)"


@router.post("/ingest-restaurants", response_model=IngestRestaurantsResponse)
async def ingest_restaurants(
    payload: IngestRestaurantsRequest,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Create/resolve restaurants for provided URLs and scrape/store latest text content.
    Returns the list of restaurant IDs created/resolved.
    """
    # Validate team membership
    team = session.exec(select(Team).where(Team.id == payload.team_id)).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    membership = session.exec(
        select(TeamMembership).where(
            TeamMembership.team_id == payload.team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True,
        )
    ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    restaurant_ids: List[str] = []
    created_count = 0
    scraped_count = 0
    cached_count = 0
    processing_details = []

    for url in payload.restaurant_urls:
        # 1. Get or create Restaurant
        r = session.exec(select(Restaurant).where(Restaurant.url == url)).first()
        if not r:
            r = Restaurant(url=url)
            session.add(r)
            session.commit()
            session.refresh(r)
            created_count += 1

        # 2. Get or create TeamRestaurant (team-specific restaurant source)
        team_restaurant = session.exec(
            select(TeamRestaurant).where(
                TeamRestaurant.team_id == payload.team_id,
                TeamRestaurant.restaurant_id == r.id
            )
        ).first()
        
        if not team_restaurant:
            team_restaurant = TeamRestaurant(
                team_id=payload.team_id,
                restaurant_id=r.id,
                added_by_user_id=current_user.id,
                cache_strategy=CacheStrategy.auto
            )
            session.add(team_restaurant)
            session.commit()
            session.refresh(team_restaurant)
            logger.info("[ingest] Created TeamRestaurant for team=%s, restaurant=%s", payload.team_id, r.id)

        # 3. Get latest document for this restaurant
        latest_doc = session.exec(
            select(RestaurantDocument)
            .where(RestaurantDocument.restaurant_id == r.id)
            .order_by(RestaurantDocument.created_at.desc())
        ).first()

        # 4. Check if we should re-scrape (or if forced)
        if payload.force_rescrape:
            should_rescrape, reason = True, "Force re-scrape requested"
        else:
            should_rescrape, reason = _should_rescrape_restaurant(team_restaurant, latest_doc)
        
        if should_rescrape:
            # Attempt to scrape and persist a fresh RestaurantDocument
            try:
                result = await scrape_url(r.url)
                if result['success']:
                    text_content = result['content']
                    
                    # Analyze menu content to detect type and temporal patterns
                    menu_metadata = extract_menu_metadata(text_content)
                    
                    # Combine scraping metadata with menu analysis
                    meta = {
                        'duration': result.get('duration'),
                        'content_length': result.get('content_length'),
                        'timestamp': result.get('timestamp'),
                        'status_code': result.get('status_code'),
                        'pdf_count': result.get('pdf_count', 0),
                        'word_count': result.get('word_count', 0),
                        'menu_type': menu_metadata.get('menu_type', 'unknown'),
                        'detected_days': menu_metadata.get('detected_days', []),
                        'menu_confidence': menu_metadata.get('confidence', 0.0),
                        'has_prices': menu_metadata.get('has_prices', False),
                        'price_count': menu_metadata.get('price_count', 0),
                    }
                    doc = RestaurantDocument(restaurant_id=r.id, content_md=text_content, meta=meta)
                    session.add(doc)
                    
                    # Update team-specific cache tracking
                    team_restaurant.last_scraped_at = datetime.utcnow()
                    session.add(team_restaurant)
                    
                    session.commit()
                    scraped_count += 1
                    processing_details.append({
                        'url': url,
                        'action': 'scraped',
                        'reason': reason,
                        'cache_strategy': team_restaurant.cache_strategy,
                        'menu_type': menu_metadata.get('menu_type', 'unknown')
                    })
                    logger.info("[ingest] Stored new RestaurantDocument id=%s for restaurant id=%s (reason: %s, menu_type: %s)", 
                               doc.id, r.id, reason, menu_metadata.get('menu_type', 'unknown'))
                else:
                    processing_details.append({
                        'url': url,
                        'action': 'failed',
                        'reason': f"Scraping failed: {result.get('error', 'Unknown error')}"
                    })
                    logger.warning("[ingest] Scraping failed for %s: %s", r.url, result.get('error', 'Unknown error'))
            except Exception as e:
                processing_details.append({
                    'url': url,
                    'action': 'failed',
                    'reason': f"Exception: {str(e)}"
                })
                logger.warning("[ingest] Scraping failed for %s: %r", r.url, e)
        else:
            # Use cached data
            cached_count += 1
            processing_details.append({
                'url': url,
                'action': 'cached',
                'reason': reason,
                'cache_strategy': team_restaurant.cache_strategy
            })
            logger.info("[ingest] Using cached data for restaurant id=%s (reason: %s)", r.id, reason)

        restaurant_ids.append(r.id)

    # Deduplicate
    restaurant_ids = list(dict.fromkeys(restaurant_ids))

    return IngestRestaurantsResponse(
        restaurant_ids=restaurant_ids,
        processed_count=len(payload.restaurant_urls),
        created_count=created_count,
        scraped_count=scraped_count,
        cached_count=cached_count,
        processing_details=processing_details,
    )


@router.get("/existing-restaurants/{team_id}", response_model=ExistingRestaurantsResponse)
async def get_existing_restaurants(
    team_id: str,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get all restaurants that this team has added and have content available for decision making."""
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

    # Get all team-specific restaurants that have at least one document
    team_restaurants_with_docs = session.exec(
        select(TeamRestaurant, Restaurant, RestaurantDocument)
        .join(Restaurant, TeamRestaurant.restaurant_id == Restaurant.id)
        .join(RestaurantDocument, Restaurant.id == RestaurantDocument.restaurant_id)
        .where(
            TeamRestaurant.team_id == team_id,
            TeamRestaurant.is_active == True
        )
        .order_by(RestaurantDocument.created_at.desc())
    ).all()

    # Group by restaurant and get the latest document for each
    restaurant_map = {}
    for team_restaurant, restaurant, doc in team_restaurants_with_docs:
        if restaurant.id not in restaurant_map:
            # Calculate content age
            now = datetime.utcnow()
            content_age_days = (now - doc.created_at).days if doc.created_at else None
            
            # Use team-specific display name if available, otherwise use restaurant's
            display_name = team_restaurant.display_name or restaurant.display_name
            
            restaurant_map[restaurant.id] = ExistingRestaurant(
                id=restaurant.id,
                url=restaurant.url,
                display_name=display_name,
                last_scraped_at=team_restaurant.last_scraped_at.isoformat() if team_restaurant.last_scraped_at else None,
                menu_type=doc.meta.get('menu_type', 'unknown') if doc.meta else 'unknown',
                content_age_days=content_age_days,
                has_content=bool(doc.content_md and len(doc.content_md.strip()) > 0)
            )

    existing_restaurants = list(restaurant_map.values())
    
    return ExistingRestaurantsResponse(
        restaurants=existing_restaurants,
        total_count=len(existing_restaurants)
    )


@router.post("/agent-decision", response_model=AgentDecisionResponse)
async def agent_decide(
    payload: AgentDecisionRequest,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Runs the LangGraph agent to make a decision."""
    # 1. Validate team membership
    team = session.exec(select(Team).where(Team.id == payload.team_id)).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    membership = session.exec(
        select(TeamMembership).where(
            TeamMembership.team_id == payload.team_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True,
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    # 2. Require restaurant_ids (must be provided by ingest endpoint beforehand)
    restaurant_ids: List[str] = payload.restaurant_ids or []
    if not restaurant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="restaurant_ids are required; call /decision/ingest-restaurants first")

    # 3. Run the agent
    logger.info(
        "Starting agent decision for team_id=%s with %d restaurants.",
        payload.team_id,
        len(restaurant_ids),
    )
    try:
        payload_dict = payload.model_dump()
        result = await run_decision_agent(request=payload_dict, db_session=session)
        logger.info("Agent decision completed for team_id=%s.", payload.team_id)
        
        # 4. Enhance result with restaurant name if missing
        if not result.get("recommendation_restaurant_name") or result.get("recommendation_restaurant_name") == "":
            # Try to extract from URL if present
            if result.get("recommendation_restaurant_url"):
                from urllib.parse import urlparse
                try:
                    parsed = urlparse(result["recommendation_restaurant_url"])
                    domain = parsed.netloc or parsed.path
                    if domain.startswith("www."):
                        domain = domain[4:]
                    domain = domain.split(":")[0]
                    result["recommendation_restaurant_name"] = domain
                except Exception:
                    pass
            
            # If still empty, try to match against restaurant URLs
            if not result.get("recommendation_restaurant_name") or result.get("recommendation_restaurant_name") == "":
                restaurants = session.exec(
                    select(Restaurant).where(Restaurant.id.in_(restaurant_ids))
                ).all()
                if restaurants:
                    # Use the first restaurant as fallback
                    from urllib.parse import urlparse
                    try:
                        parsed = urlparse(restaurants[0].url)
                        domain = parsed.netloc or parsed.path
                        if domain.startswith("www."):
                            domain = domain[4:]
                        domain = domain.split(":")[0]
                        result["recommendation_restaurant_name"] = domain
                    except Exception:
                        result["recommendation_restaurant_name"] = restaurants[0].url
        
        # 5. Save the decision to history
        decision_run = DecisionRun(
            organizer_user_id=current_user.id,
            team_id=payload.team_id,
            participant_profile_ids=[],  # Could be populated with team member profile IDs if needed
            restaurant_ids=restaurant_ids,
            result=result,
        )
        session.add(decision_run)
        session.commit()
        session.refresh(decision_run)
        
        # 6. Create notifications for all team members (except the organizer)
        team_members = session.exec(
            select(TeamMembership).where(
                TeamMembership.team_id == payload.team_id,
                TeamMembership.is_active == True,
                TeamMembership.user_id != current_user.id,  # Exclude organizer
            )
        ).all()
        
        restaurant_name = result.get("recommendation_restaurant_name", "a restaurant")
        for member in team_members:
            notification = Notification(
                user_id=member.user_id,
                type="team_decision",
                title=f"New decision in {team.name}",
                message=f"{current_user.display_name or current_user.email} made a decision: {restaurant_name}",
                team_id=payload.team_id,
                decision_run_id=decision_run.id,
            )
            session.add(notification)
        
        session.commit()
        
        return result
    except Exception as e:
        logger.error("Agent decision failed for team_id=%s: %s", payload.team_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during the decision-making process: {e}",
        )


def _extract_restaurant_name_from_url(url: str) -> str:
    """Extract clean domain name from URL (without www.)"""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        if domain.startswith("www."):
            domain = domain[4:]
        domain = domain.split(":")[0]
        return domain
    except Exception:
        return url


def _snake_to_camel(s: str) -> str:
    """Convert snake_case to camelCase"""
    parts = s.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])


@router.get("/history", response_model=List[DecisionRunRead])
def get_decision_history(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Get recent decision history for the current user - includes decisions they made and team decisions"""
    # Get user's team IDs
    user_teams = session.exec(
        select(TeamMembership.team_id).where(
            TeamMembership.user_id == current_user.id,
            TeamMembership.is_active == True,
        )
    ).all()
    
    # Get decisions where user is organizer OR decision is from their teams
    decisions = session.exec(
        select(DecisionRun)
        .where(
            (DecisionRun.organizer_user_id == current_user.id) |
            (DecisionRun.team_id.in_(user_teams))
        )
        .order_by(DecisionRun.created_at.desc())
        .limit(limit)
    ).all()
    
    result_list = []
    for d in decisions:
        result = dict(d.result) if d.result else {}
        
        # Fix missing restaurant name by extracting from URL
        if not result.get("recommendation_restaurant_name") or result.get("recommendation_restaurant_name") == "":
            if result.get("recommendation_restaurant_url"):
                result["recommendation_restaurant_name"] = _extract_restaurant_name_from_url(result["recommendation_restaurant_url"])
            elif d.restaurant_ids:
                restaurants = session.exec(
                    select(Restaurant).where(Restaurant.id.in_(d.restaurant_ids))
                ).all()
                if restaurants:
                    result["recommendation_restaurant_name"] = _extract_restaurant_name_from_url(restaurants[0].url)
        
        # Convert result keys to camelCase for frontend
        camel_result = {_snake_to_camel(k): v for k, v in result.items()}
        
        result_list.append(DecisionRunRead(
            id=d.id,
            organizer_user_id=d.organizer_user_id,
            team_id=d.team_id,
            restaurant_ids=d.restaurant_ids,
            result=camel_result,
            created_at=d.created_at.isoformat(),
        ))
    
    return result_list
