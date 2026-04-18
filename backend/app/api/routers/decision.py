from __future__ import annotations

from typing import List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse
import math
import httpx
from bs4 import BeautifulSoup

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ...api.deps import get_current_user, get_db_session
from ...db.models import User, Restaurant, RestaurantDocument, Team, TeamMembership, DecisionRun, CacheStrategy, TeamRestaurant, Notification
from ...scraping.scraper import scrape_url
from ...scraping.simple_scraper import scrape_url_simple
import logging
from ...decision.agent import run_decision_agent
from ...decision.menu_analyzer import extract_menu_metadata
from ...core.config import settings
from ...decision.schemas import (
    AgentDecisionRequest,
    AgentDecisionResponse,
    IngestRestaurantInput,
    IngestRestaurantsRequest,
    IngestRestaurantsResponse,
    ExistingRestaurantsResponse,
    ExistingRestaurant,
)
from ...integrations.google_places import (
    GooglePlacesAPIError,
    GooglePlacesConfigError,
    search_places_by_text,
)
from ...integrations.openai_menu_extractor import (
    OpenAIMenuExtractorConfigError,
    OpenAIMenuExtractorError,
    extract_menu_with_openai,
)
from ...schemas import DecisionRunRead

logger = logging.getLogger(__name__)

router = APIRouter()


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _straight_line_distance_km(
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
) -> float:
    radius_km = 6371.0
    lat1 = math.radians(origin_lat)
    lng1 = math.radians(origin_lng)
    lat2 = math.radians(destination_lat)
    lng2 = math.radians(destination_lng)
    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def _use_legacy_menu_scraper() -> bool:
    return (settings.MENU_SCRAPER or "").strip().upper() == "LEGACY"


def _url_looks_like_pdf(url: str) -> bool:
    return url.lower().endswith(".pdf")


async def _url_returns_pdf_content_type(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            async with client.stream(
                "GET",
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/pdf,text/html,*/*",
                },
            ) as response:
                content_type = (response.headers.get("content-type") or "").lower()
                return "application/pdf" in content_type
    except Exception:
        return False


async def _fetch_openai_source_for_html(url: str) -> dict[str, Any]:
    simple_result = await scrape_url_simple(url)
    if not simple_result.get("success"):
        return await scrape_url(url)

    pdf_urls: list[str] = []
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup.find_all(["a", "iframe", "embed", "object"]):
                candidate = (
                    tag.get("href")
                    or tag.get("src")
                    or tag.get("data")
                )
                if not candidate:
                    continue
                candidate = candidate.strip()
                if ".pdf" in candidate.lower() and candidate not in pdf_urls:
                    pdf_urls.append(candidate)
    except Exception:
        pdf_urls = []

    if simple_result.get("content_length", 0) < 400 and not pdf_urls:
        browser_result = await scrape_url(url)
        if browser_result.get("success"):
            return browser_result

    simple_result["pdf_urls"] = pdf_urls
    return simple_result


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


def _guess_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    hostname = (parsed.netloc or parsed.path).lower()
    hostname = hostname.split(":")[0]
    if hostname.startswith("www."):
        hostname = hostname[4:]

    parts = [part for part in hostname.split(".") if part]
    if len(parts) >= 2:
        candidate = parts[-2]
    elif parts:
        candidate = parts[0]
    else:
        candidate = hostname

    return candidate.replace("-", " ").replace("_", " ").strip().title()


def _guess_name_from_content(content: str | None) -> str | None:
    if not content:
        return None

    for line in content.splitlines():
        candidate = line.strip()
        if len(candidate) < 4 or len(candidate) > 80:
            continue
        if candidate.lower().startswith(("http://", "https://", "www.")):
            continue
        if sum(ch.isalpha() for ch in candidate) < 6:
            continue
        return candidate

    return None


def _build_places_query(
    *,
    team: Team | None,
    restaurant: Restaurant,
    latest_doc: RestaurantDocument | None,
    scraped_content: str | None = None,
) -> str:
    name_candidate = (
        restaurant.display_name
        or _guess_name_from_content(scraped_content)
        or _guess_name_from_content(latest_doc.content_md if latest_doc else None)
        or _guess_name_from_url(restaurant.url)
    )
    location_hint = (team.location or "").strip() if team else ""
    return " ".join(
        part for part in [name_candidate, "restaurant", location_hint] if part
    ).strip()


async def _enrich_restaurant_with_google_maps(
    *,
    session: Session,
    team: Team | None,
    restaurant: Restaurant,
    latest_doc: RestaurantDocument | None,
    scraped_content: str | None = None,
    force_refresh: bool = False,
) -> None:
    existing_google_maps = (restaurant.meta or {}).get("google_maps")
    if existing_google_maps and not force_refresh:
        return

    query = _build_places_query(
        team=team,
        restaurant=restaurant,
        latest_doc=latest_doc,
        scraped_content=scraped_content,
    )
    if not query:
        return

    try:
        candidates = await search_places_by_text(query, max_results=1)
    except GooglePlacesConfigError as exc:
        logger.info("[ingest] Google Maps enrichment skipped: %s", exc)
        return
    except GooglePlacesAPIError as exc:
        logger.warning("[ingest] Google Maps search failed for %s: %s", restaurant.url, exc)
        return
    except Exception as exc:
        logger.warning("[ingest] Unexpected Google Maps enrichment error for %s: %r", restaurant.url, exc)
        return

    if not candidates:
        logger.info("[ingest] No Google Maps match found for query=%r", query)
        return

    restaurant.meta = {**(restaurant.meta or {}), **candidates[0]}
    google_maps = restaurant.meta.get("google_maps") or {}

    if not restaurant.display_name and google_maps.get("display_name"):
        restaurant.display_name = google_maps["display_name"]

    session.add(restaurant)


def _build_legacy_menu_document(text_content: str) -> tuple[str, dict[str, Any]]:
    menu_metadata = extract_menu_metadata(text_content)
    structured_menu_text = menu_metadata.get("structured_menu_text") or text_content
    meta = {
        "menu_extractor": menu_metadata.get("extractor", "legacy"),
        "content_length": len(structured_menu_text),
        "raw_content_length": len(text_content),
        "menu_type": menu_metadata.get("menu_type", "unknown"),
        "detected_days": menu_metadata.get("detected_days", []),
        "menu_confidence": menu_metadata.get("confidence", 0.0),
        "day_sections": menu_metadata.get("day_sections", {}),
        "static_menu_lines": menu_metadata.get("static_menu_lines", []),
        "structured_line_count": menu_metadata.get("structured_line_count", 0),
        "has_prices": menu_metadata.get("has_prices", False),
        "price_count": menu_metadata.get("price_count", 0),
    }
    return structured_menu_text, meta


async def _build_menu_document_content(
    *,
    restaurant: Restaurant,
    provided_name: str | None,
    scrape_result: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    raw_text = scrape_result.get("content", "") or ""
    if _use_legacy_menu_scraper():
        return _build_legacy_menu_document(raw_text)

    try:
        openai_result = await extract_menu_with_openai(
            restaurant_url=restaurant.url,
            restaurant_name=provided_name or restaurant.display_name,
            scraped_text=raw_text,
            pdf_urls=scrape_result.get("pdf_urls") or [],
        )
        structured_text = openai_result.get("structured_menu_text") or raw_text
        meta = {
            "menu_extractor": openai_result.get("extractor", "openai"),
            "content_length": len(structured_text),
            "raw_content_length": len(raw_text),
            "menu_type": openai_result.get("menu_type", "unknown"),
            "detected_days": openai_result.get("detected_days", []),
            "menu_confidence": openai_result.get("confidence", 0.0),
            "day_sections": openai_result.get("day_sections", {}),
            "static_menu_lines": openai_result.get("static_menu_lines", []),
            "structured_line_count": openai_result.get("structured_line_count", 0),
        }
        has_prices = "€" in structured_text or bool(meta["static_menu_lines"])
        meta["has_prices"] = has_prices
        meta["price_count"] = structured_text.count("€")
        return structured_text, meta
    except (OpenAIMenuExtractorConfigError, OpenAIMenuExtractorError) as exc:
        logger.warning("[ingest] OpenAI menu extraction failed for %s: %s", restaurant.url, exc)
        return _build_legacy_menu_document(raw_text)


async def _build_menu_document_from_pdf_url(
    *,
    restaurant: Restaurant,
    provided_name: str | None,
    pdf_url: str,
) -> tuple[str, dict[str, Any]]:
    openai_result = await extract_menu_with_openai(
        restaurant_url=restaurant.url,
        restaurant_name=provided_name or restaurant.display_name,
        scraped_text="",
        pdf_urls=[pdf_url],
    )
    structured_text = openai_result.get("structured_menu_text") or ""
    meta = {
        "menu_extractor": openai_result.get("extractor", "openai"),
        "content_length": len(structured_text),
        "raw_content_length": 0,
        "menu_type": openai_result.get("menu_type", "unknown"),
        "detected_days": openai_result.get("detected_days", []),
        "menu_confidence": openai_result.get("confidence", 0.0),
        "day_sections": openai_result.get("day_sections", {}),
        "static_menu_lines": openai_result.get("static_menu_lines", []),
        "structured_line_count": openai_result.get("structured_line_count", 0),
        "has_prices": "€" in structured_text or bool(openai_result.get("static_menu_lines", [])),
        "price_count": structured_text.count("€"),
    }
    return structured_text, meta


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
    ingest_entries: List[IngestRestaurantInput] = []

    if payload.restaurants:
        ingest_entries.extend(payload.restaurants)
    elif payload.restaurant_urls:
        ingest_entries.extend(IngestRestaurantInput(url=url) for url in payload.restaurant_urls)

    if not ingest_entries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one restaurant URL",
        )

    for entry in ingest_entries:
        url = entry.url
        provided_name = (entry.name or "").strip() or None
        scraped_content: str | None = None

        # 1. Get or create Restaurant
        r = session.exec(select(Restaurant).where(Restaurant.url == url)).first()
        if not r:
            r = Restaurant(url=url, display_name=provided_name)
            session.add(r)
            session.commit()
            session.refresh(r)
            created_count += 1
        elif provided_name and not r.display_name:
            r.display_name = provided_name
            session.add(r)
            session.commit()
            session.refresh(r)

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
                cache_strategy=CacheStrategy.auto,
                display_name=provided_name,
            )
            session.add(team_restaurant)
            session.commit()
            session.refresh(team_restaurant)
            logger.info("[ingest] Created TeamRestaurant for team=%s, restaurant=%s", payload.team_id, r.id)
        elif provided_name and team_restaurant.display_name != provided_name:
            team_restaurant.display_name = provided_name
            session.add(team_restaurant)
            session.commit()
            session.refresh(team_restaurant)

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
                result: dict[str, Any] | None = None
                direct_pdf_url: str | None = None

                if not _use_legacy_menu_scraper():
                    if _url_looks_like_pdf(r.url) or await _url_returns_pdf_content_type(r.url):
                        direct_pdf_url = r.url

                if direct_pdf_url:
                    structured_menu_text, menu_meta = await _build_menu_document_from_pdf_url(
                        restaurant=r,
                        provided_name=provided_name,
                        pdf_url=direct_pdf_url,
                    )
                    meta = {
                        'duration': None,
                        'content_length': len(structured_menu_text),
                        'raw_content_length': 0,
                        'timestamp': datetime.utcnow().isoformat(),
                        'status_code': None,
                        'pdf_count': 1,
                        'pdf_urls': [direct_pdf_url],
                        'word_count': len(structured_menu_text.split()) if structured_menu_text else 0,
                        **menu_meta,
                    }
                    scraped_content = structured_menu_text
                else:
                    result = await (
                        scrape_url(r.url)
                        if _use_legacy_menu_scraper()
                        else _fetch_openai_source_for_html(r.url)
                    )
                    if not result['success']:
                        processing_details.append({
                            'url': url,
                            'action': 'failed',
                            'reason': f"Scraping failed: {result.get('error', 'Unknown error')}"
                        })
                        logger.warning("[ingest] Scraping failed for %s: %s", r.url, result.get('error', 'Unknown error'))
                        continue

                    text_content = result['content']
                    scraped_content = text_content
                    structured_menu_text, menu_meta = await _build_menu_document_content(
                        restaurant=r,
                        provided_name=provided_name,
                        scrape_result=result,
                    )
                    meta = {
                        'duration': result.get('duration'),
                        'content_length': len(structured_menu_text),
                        'raw_content_length': len(text_content),
                        'timestamp': result.get('timestamp'),
                        'status_code': result.get('status_code'),
                        'pdf_count': result.get('pdf_count', 0),
                        'pdf_urls': result.get('pdf_urls', []),
                        'word_count': result.get('word_count', 0),
                        **menu_meta,
                    }

                doc = RestaurantDocument(
                    restaurant_id=r.id,
                    content_md=structured_menu_text,
                    meta=meta,
                )
                session.add(doc)
                
                # Update team-specific cache tracking
                team_restaurant.last_scraped_at = datetime.utcnow()
                session.add(team_restaurant)

                await _enrich_restaurant_with_google_maps(
                    session=session,
                    team=team,
                    restaurant=r,
                    latest_doc=latest_doc,
                    scraped_content=scraped_content,
                    force_refresh=payload.force_rescrape,
                )
                
                session.commit()
                scraped_count += 1
                processing_details.append({
                    'url': url,
                    'action': 'scraped',
                    'reason': reason,
                    'cache_strategy': team_restaurant.cache_strategy,
                    'menu_type': meta.get('menu_type', 'unknown')
                })
                logger.info("[ingest] Stored new RestaurantDocument id=%s for restaurant id=%s (reason: %s, menu_type: %s)", 
                           doc.id, r.id, reason, meta.get('menu_type', 'unknown'))
            except Exception as e:
                processing_details.append({
                    'url': url,
                    'action': 'failed',
                    'reason': f"Exception: {str(e)}"
                })
                logger.warning("[ingest] Scraping failed for %s: %r", r.url, e)
        else:
            await _enrich_restaurant_with_google_maps(
                session=session,
                team=team,
                restaurant=r,
                latest_doc=latest_doc,
                force_refresh=payload.force_rescrape,
            )
            session.commit()

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
        processed_count=len(ingest_entries),
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
    team_lat = _coerce_float(team.location_lat)
    team_lng = _coerce_float(team.location_lng)
    restaurant_map = {}
    for team_restaurant, restaurant, doc in team_restaurants_with_docs:
        if restaurant.id not in restaurant_map:
            # Calculate content age
            now = datetime.utcnow()
            content_age_days = (now - doc.created_at).days if doc.created_at else None
            
            # Use team-specific display name if available, otherwise use restaurant's
            display_name = team_restaurant.display_name or restaurant.display_name
            google_maps = (restaurant.meta or {}).get("google_maps") or {}
            restaurant_lat = _coerce_float(google_maps.get("lat"))
            restaurant_lng = _coerce_float(google_maps.get("lng"))
            distance_km = None
            if None not in (team_lat, team_lng, restaurant_lat, restaurant_lng):
                distance_km = round(
                    _straight_line_distance_km(team_lat, team_lng, restaurant_lat, restaurant_lng),
                    2,
                )
            
            restaurant_map[restaurant.id] = ExistingRestaurant(
                id=restaurant.id,
                url=restaurant.url,
                display_name=display_name,
                formatted_address=google_maps.get("formatted_address"),
                straight_line_distance_km=distance_km,
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
