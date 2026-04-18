from __future__ import annotations

import asyncio
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
from ...preferences.service import aggregate_team_preferences
from ...decision.schemas import (
    AgentDecisionRequest,
    AgentDecisionResponse,
    DiscoverRestaurantsRequest,
    DiscoverRestaurantsResponse,
    IngestRestaurantInput,
    IngestRestaurantsRequest,
    IngestRestaurantsResponse,
    DiscoveredRestaurant,
    ExistingRestaurantsResponse,
    ExistingRestaurant,
)
from ...integrations.google_places import (
    GooglePlacesAPIError,
    GooglePlacesConfigError,
    search_nearby_places,
    search_places_by_text,
)
from ...integrations.openai_menu_extractor import (
    OpenAIMenuExtractorConfigError,
    OpenAIMenuExtractorError,
    extract_menu_with_openai,
)
from ...integrations.openai_restaurant_research import (
    OpenAIRestaurantResearchConfigError,
    OpenAIRestaurantResearchError,
    research_restaurant_with_openai,
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


def _normalize_keyword(value: str) -> str:
    return (value or "").strip().lower().replace("-", " ").replace("_", " ")


def _price_level_to_numeric(price_level: Any) -> int | None:
    if price_level is None:
        return None
    normalized = str(price_level).strip().lower()
    mapping = {
        "free": 0,
        "price_level_free": 0,
        "inexpensive": 1,
        "price_level_inexpensive": 1,
        "moderate": 2,
        "price_level_moderate": 2,
        "expensive": 3,
        "price_level_expensive": 3,
        "very_expensive": 4,
        "price_level_very_expensive": 4,
    }
    return mapping.get(normalized)


def _budget_target(budget_value: Any) -> int:
    normalized = str(budget_value or "medium").strip().lower()
    if normalized == "low":
        return 1
    if normalized == "high":
        return 3
    return 2


def _extract_team_preference_keywords(other_preferences: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    data = other_preferences or {}
    positive: list[str] = []
    negative: list[str] = []

    signals = data.get("signals")
    if isinstance(signals, dict):
        for payload in signals.values():
            if isinstance(payload, dict) and payload.get("value"):
                positive.append(str(payload["value"]))

    for mood in data.get("recent_moods", []) or []:
        if isinstance(mood, str):
            positive.append(mood)

    for dislike in data.get("dislikes", []) or []:
        if isinstance(dislike, str):
            negative.append(dislike)

    seen_positive: set[str] = set()
    seen_negative: set[str] = set()
    cleaned_positive: list[str] = []
    cleaned_negative: list[str] = []

    for raw in positive:
        normalized = _normalize_keyword(raw)
        if normalized and normalized not in seen_positive:
            seen_positive.add(normalized)
            cleaned_positive.append(normalized)

    for raw in negative:
        normalized = _normalize_keyword(raw)
        if normalized and normalized not in seen_negative:
            seen_negative.add(normalized)
            cleaned_negative.append(normalized)

    return cleaned_positive, cleaned_negative


def _derive_cuisine_tags_from_google(google_maps: dict[str, Any]) -> list[str]:
    raw_tags = [google_maps.get("primary_type")] + list(google_maps.get("types") or [])
    tags: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags:
        normalized = _normalize_keyword(str(tag or ""))
        if not normalized:
            continue
        normalized = normalized.replace(" restaurant", "").replace(" food", "").strip()
        if not normalized or normalized in {"point of interest", "establishment"}:
            continue
        if normalized not in seen:
            seen.add(normalized)
            tags.append(normalized)
    return tags[:6]


def _build_vibe_fallback(google_maps: dict[str, Any]) -> dict[str, Any]:
    cuisine_tags = _derive_cuisine_tags_from_google(google_maps)
    display_name = google_maps.get("display_name") or "This restaurant"
    primary_type = _normalize_keyword(google_maps.get("primary_type") or "restaurant")
    rating = google_maps.get("rating")
    summary_parts = [f"{display_name} looks like a {primary_type} option"]
    if cuisine_tags:
        summary_parts.append(f"with a {', '.join(cuisine_tags[:3])} profile")
    if rating:
        summary_parts.append(f"rated {rating}")
    return {
        "result_type": "vibe",
        "summary": " ".join(summary_parts).strip() + ".",
        "menu_items": [],
        "cuisine_tags": cuisine_tags,
        "dietary_signals": [],
        "confidence": 0.2,
        "source_urls": [],
    }


def _compose_candidate_corpus(
    *,
    google_maps: dict[str, Any],
    research_result: dict[str, Any] | None,
) -> str:
    parts: list[str] = [
        google_maps.get("display_name") or "",
        google_maps.get("formatted_address") or "",
        google_maps.get("primary_type") or "",
        " ".join(google_maps.get("types") or []),
    ]
    if research_result:
        parts.append(research_result.get("summary") or "")
        parts.extend(research_result.get("menu_items") or [])
        parts.extend(research_result.get("cuisine_tags") or [])
        parts.extend(research_result.get("dietary_signals") or [])
    return _normalize_keyword(" ".join(part for part in parts if part))


def _keyword_hits(corpus: str, keywords: list[str]) -> int:
    hits = 0
    for keyword in keywords:
        normalized = _normalize_keyword(keyword)
        if normalized and normalized in corpus:
            hits += 1
    return hits


def _score_distance(distance_km: float | None) -> float:
    if distance_km is None:
        return 8.0
    if distance_km <= 0.5:
        return 30.0
    if distance_km <= 1.0:
        return 26.0
    if distance_km <= 2.0:
        return 20.0
    if distance_km <= 3.0:
        return 14.0
    if distance_km <= 5.0:
        return 8.0
    return 3.0


def _score_rating(rating: Any, user_rating_count: Any) -> float:
    rating_value = _coerce_float(rating) or 0.0
    rating_component = min(16.0, max(0.0, (rating_value / 5.0) * 16.0))
    try:
        count_value = int(user_rating_count or 0)
    except (TypeError, ValueError):
        count_value = 0
    count_component = min(4.0, count_value / 50.0)
    return round(rating_component + count_component, 2)


def _score_budget_fit(team_budget: Any, price_level: Any) -> float:
    numeric_price = _price_level_to_numeric(price_level)
    if numeric_price is None:
        return 5.0
    diff = abs(_budget_target(team_budget) - numeric_price)
    if diff == 0:
        return 10.0
    if diff == 1:
        return 7.0
    if diff == 2:
        return 4.0
    return 1.0


def _score_preference_fit(
    *,
    corpus: str,
    positive_keywords: list[str],
    negative_keywords: list[str],
) -> float:
    positive_hits = _keyword_hits(corpus, positive_keywords)
    negative_hits = _keyword_hits(corpus, negative_keywords)
    base = 8.0 if positive_keywords else 10.0
    score = base + (positive_hits * 4.0) - (negative_hits * 6.0)
    return round(max(0.0, min(score, 20.0)), 2)


def _score_dietary_fit(
    *,
    corpus: str,
    dietary_restrictions: list[str],
    allergies: list[str],
    research_result_type: str | None,
) -> float:
    normalized_restrictions = [_normalize_keyword(item) for item in dietary_restrictions if item]
    normalized_allergies = [_normalize_keyword(item) for item in allergies if item]
    if not normalized_restrictions and not normalized_allergies:
        return 12.0

    support_map = {
        "vegetarian": ["vegetarian", "veggie", "vegetarisch", "vegetarian options"],
        "vegan": ["vegan", "plant based", "pflanzlich"],
        "pescatarian": ["fish", "seafood", "pescatarian"],
        "gluten free": ["gluten free", "gluten-free", "gf"],
        "halal": ["halal"],
        "kosher": ["kosher"],
    }

    matched = 0
    for restriction in normalized_restrictions:
        candidates = support_map.get(restriction, [restriction])
        if any(candidate in corpus for candidate in candidates):
            matched += 1

    if normalized_restrictions:
        if matched == len(normalized_restrictions):
            score = 15.0
        elif matched > 0:
            score = 10.0
        else:
            score = 4.0 if research_result_type == "menu" else 2.0
    else:
        score = 8.0

    if normalized_allergies and research_result_type != "menu":
        score -= 3.0

    return round(max(0.0, min(score, 15.0)), 2)


def _score_menu_evidence(research_result: dict[str, Any]) -> float:
    result_type = research_result.get("result_type")
    menu_items = research_result.get("menu_items") or []
    confidence = _coerce_float(research_result.get("confidence")) or 0.0
    if result_type == "menu" and menu_items:
        return round(min(5.0, 3.5 + confidence * 1.5), 2)
    if result_type == "vibe":
        return round(min(3.0, 1.5 + confidence), 2)
    return 0.5


def _build_recommendation_reasons(
    *,
    google_maps: dict[str, Any],
    score_breakdown: dict[str, float],
    research_result: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if score_breakdown.get("distance", 0.0) >= 20.0 and google_maps.get("formatted_address"):
        reasons.append("Close to the team's location.")
    if score_breakdown.get("rating", 0.0) >= 15.0 and google_maps.get("rating"):
        reasons.append(f"Strong public rating ({google_maps.get('rating')}).")
    if research_result.get("result_type") == "menu" and research_result.get("menu_items"):
        reasons.append("Current menu evidence was found.")
    elif research_result.get("result_type") == "vibe":
        reasons.append("Ranked using cuisine and vibe signals when no current menu was available.")
    if score_breakdown.get("preference_fit", 0.0) >= 12.0:
        reasons.append("Matches the team's stated cuisine or mood preferences.")
    return reasons[:4]


def _score_discovered_candidate(
    *,
    google_maps: dict[str, Any],
    team: Team,
    team_preference: Any,
    research_result: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    distance_km: float | None = None
    lat = _coerce_float(google_maps.get("lat"))
    lng = _coerce_float(google_maps.get("lng"))
    if team.location_lat is not None and team.location_lng is not None and lat is not None and lng is not None:
        distance_km = _straight_line_distance_km(team.location_lat, team.location_lng, lat, lng)

    positive_keywords, negative_keywords = _extract_team_preference_keywords(
        getattr(team_preference, "other_preferences", {}) or {}
    )
    corpus = _compose_candidate_corpus(google_maps=google_maps, research_result=research_result)
    score_breakdown = {
        "distance": _score_distance(distance_km),
        "rating": _score_rating(google_maps.get("rating"), google_maps.get("user_rating_count")),
        "budget_fit": _score_budget_fit(
            getattr(getattr(team_preference, "budget_preference", None), "value", getattr(team_preference, "budget_preference", "medium")),
            google_maps.get("price_level"),
        ),
        "preference_fit": _score_preference_fit(
            corpus=corpus,
            positive_keywords=positive_keywords,
            negative_keywords=negative_keywords,
        ),
        "dietary_fit": _score_dietary_fit(
            corpus=corpus,
            dietary_restrictions=getattr(team_preference, "dietary_restrictions", []) or [],
            allergies=getattr(team_preference, "allergies", []) or [],
            research_result_type=research_result.get("result_type"),
        ),
        "menu_evidence": _score_menu_evidence(research_result),
    }
    total = round(sum(score_breakdown.values()), 2)
    return total, score_breakdown


def _find_existing_restaurant_id(
    restaurants: list[Restaurant],
    google_maps: dict[str, Any],
) -> str | None:
    place_id = str(google_maps.get("place_id") or "").strip()
    website_uri = str(google_maps.get("website_uri") or "").strip().lower()
    maps_uri = str(google_maps.get("maps_uri") or "").strip().lower()

    for restaurant in restaurants:
        meta_google = (restaurant.meta or {}).get("google_maps") or {}
        meta_place_id = str(meta_google.get("place_id") or "").strip()
        meta_website_uri = str(meta_google.get("website_uri") or "").strip().lower()
        if place_id and meta_place_id == place_id:
            return restaurant.id
        if website_uri and restaurant.url.lower() == website_uri:
            return restaurant.id
        if website_uri and meta_website_uri == website_uri:
            return restaurant.id
        if maps_uri and restaurant.url.lower() == maps_uri:
            return restaurant.id
    return None


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


@router.post("/discover-restaurants", response_model=DiscoverRestaurantsResponse)
async def discover_restaurants(
    payload: DiscoverRestaurantsRequest,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Discover nearby restaurants for a team and rank them deterministically."""
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

    if team.location_lat is None or team.location_lng is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team location with coordinates is required for discovery",
        )

    safe_radius = max(200, min(int(payload.radius_meters or 1500), 5000))
    safe_candidate_limit = max(10, min(int(payload.candidate_limit or 15), 20))
    safe_result_limit = max(1, min(int(payload.result_limit or 5), 5))

    team_preference = aggregate_team_preferences(session, team.id)

    try:
        nearby_candidates = await search_nearby_places(
            latitude=team.location_lat,
            longitude=team.location_lng,
            radius_meters=float(safe_radius),
            max_results=safe_candidate_limit,
        )
    except GooglePlacesConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except GooglePlacesAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Nearby restaurant search failed: {exc}",
        )

    unique_candidates: list[dict[str, Any]] = []
    seen_place_ids: set[str] = set()
    for candidate in nearby_candidates:
        google_maps = candidate.get("google_maps") or {}
        place_id = str(google_maps.get("place_id") or "").strip()
        if place_id and place_id in seen_place_ids:
            continue
        if place_id:
            seen_place_ids.add(place_id)
        unique_candidates.append(google_maps)

    all_restaurants = session.exec(select(Restaurant)).all()

    base_ranked: list[dict[str, Any]] = []
    for google_maps in unique_candidates:
        base_research = _build_vibe_fallback(google_maps)
        base_score, base_breakdown = _score_discovered_candidate(
            google_maps=google_maps,
            team=team,
            team_preference=team_preference,
            research_result=base_research,
        )
        base_ranked.append(
            {
                "google_maps": google_maps,
                "base_score": base_score,
                "base_breakdown": base_breakdown,
                "existing_restaurant_id": _find_existing_restaurant_id(all_restaurants, google_maps),
            }
        )

    base_ranked.sort(key=lambda item: item["base_score"], reverse=True)
    shortlist = base_ranked[:safe_result_limit]
    semaphore = asyncio.Semaphore(5)

    async def _research_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        google_maps = candidate["google_maps"]
        async with semaphore:
            try:
                research = await research_restaurant_with_openai(
                    restaurant_name=google_maps.get("display_name") or "Unknown restaurant",
                    restaurant_address=google_maps.get("formatted_address"),
                    website_uri=google_maps.get("website_uri"),
                    primary_type=google_maps.get("primary_type"),
                )
            except (OpenAIRestaurantResearchConfigError, OpenAIRestaurantResearchError) as exc:
                logger.warning(
                    "[discover] OpenAI research failed for %s: %s",
                    google_maps.get("display_name") or google_maps.get("place_id"),
                    exc,
                )
                research = _build_vibe_fallback(google_maps)

        final_score, score_breakdown = _score_discovered_candidate(
            google_maps=google_maps,
            team=team,
            team_preference=team_preference,
            research_result=research,
        )
        lat = _coerce_float(google_maps.get("lat"))
        lng = _coerce_float(google_maps.get("lng"))
        distance_km = None
        if lat is not None and lng is not None:
            distance_km = _straight_line_distance_km(team.location_lat, team.location_lng, lat, lng)

        user_rating_count = google_maps.get("user_rating_count")
        try:
            user_rating_count_value = int(user_rating_count) if user_rating_count is not None else None
        except (TypeError, ValueError):
            user_rating_count_value = None

        return {
            "display_name": google_maps.get("display_name") or "Unknown restaurant",
            "formatted_address": google_maps.get("formatted_address"),
            "website_uri": google_maps.get("website_uri"),
            "maps_uri": google_maps.get("maps_uri"),
            "primary_type": google_maps.get("primary_type"),
            "price_level": google_maps.get("price_level"),
            "rating": _coerce_float(google_maps.get("rating")),
            "user_rating_count": user_rating_count_value,
            "straight_line_distance_km": round(distance_km, 2) if distance_km is not None else None,
            "compatibility_score": final_score,
            "score_breakdown": score_breakdown,
            "recommendation_reasons": _build_recommendation_reasons(
                google_maps=google_maps,
                score_breakdown=score_breakdown,
                research_result=research,
            ),
            "research_result_type": research.get("result_type"),
            "menu_summary": research.get("summary"),
            "menu_items": research.get("menu_items") or [],
            "cuisine_tags": research.get("cuisine_tags") or [],
            "dietary_signals": research.get("dietary_signals") or [],
            "source_urls": research.get("source_urls") or [],
            "existing_restaurant_id": candidate.get("existing_restaurant_id"),
        }

    researched_results = await asyncio.gather(*[_research_candidate(candidate) for candidate in shortlist])
    researched_results.sort(key=lambda item: item["compatibility_score"], reverse=True)

    return DiscoverRestaurantsResponse(
        team_id=team.id,
        team_location=team.location or "",
        candidate_count=len(unique_candidates),
        results=[DiscoveredRestaurant(**item) for item in researched_results[:safe_result_limit]],
    )


@router.post("/agent-decision", response_model=AgentDecisionResponse)
async def agent_decide(
    payload: AgentDecisionRequest,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Runs the backend decision engine to make a team recommendation."""
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
        public_result = {
            "recommendation_restaurant_name": result.get("recommendation_restaurant_name", ""),
            "recommendation_restaurant_url": result.get("recommendation_restaurant_url"),
            "recommended_dish": result.get("recommended_dish", ""),
            "explanation_md": result.get("explanation_md", ""),
            "raw_text": result.get("raw_text", ""),
        }
        internal_diagnostics = result.get("internal_diagnostics") or {}
        logger.info("Agent decision completed for team_id=%s.", payload.team_id)
        
        # 4. Enhance result with restaurant name if missing
        if not public_result.get("recommendation_restaurant_name") or public_result.get("recommendation_restaurant_name") == "":
            # Try to extract from URL if present
            if public_result.get("recommendation_restaurant_url"):
                from urllib.parse import urlparse
                try:
                    parsed = urlparse(public_result["recommendation_restaurant_url"])
                    domain = parsed.netloc or parsed.path
                    if domain.startswith("www."):
                        domain = domain[4:]
                    domain = domain.split(":")[0]
                    public_result["recommendation_restaurant_name"] = domain
                except Exception:
                    pass
            
            # If still empty, try to match against restaurant URLs
            if not public_result.get("recommendation_restaurant_name") or public_result.get("recommendation_restaurant_name") == "":
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
                        public_result["recommendation_restaurant_name"] = domain
                    except Exception:
                        public_result["recommendation_restaurant_name"] = restaurants[0].url
        
        # 5. Save the decision to history
        persisted_result = {
            **public_result,
            "internal_diagnostics": internal_diagnostics,
        }
        decision_run = DecisionRun(
            organizer_user_id=current_user.id,
            team_id=payload.team_id,
            participant_profile_ids=[],  # Could be populated with team member profile IDs if needed
            restaurant_ids=restaurant_ids,
            result=persisted_result,
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
        
        restaurant_name = public_result.get("recommendation_restaurant_name", "a restaurant")
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
        
        return public_result
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
        
        # Convert result keys to camelCase for frontend and keep internal diagnostics backend-only
        public_result = {
            key: value
            for key, value in result.items()
            if key != "internal_diagnostics"
        }
        camel_result = {_snake_to_camel(k): v for k, v in public_result.items()}
        
        result_list.append(DecisionRunRead(
            id=d.id,
            organizer_user_id=d.organizer_user_id,
            team_id=d.team_id,
            restaurant_ids=d.restaurant_ids,
            result=camel_result,
            created_at=d.created_at.isoformat(),
        ))
    
    return result_list
