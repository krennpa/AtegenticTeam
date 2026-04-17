from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, timedelta
import re

from ...api.deps import get_current_user, get_db_session
from ...db.models import Restaurant, User, RestaurantDocument, CacheStrategy
from ...schemas import RestaurantCreate, RestaurantRead, RestaurantDocumentRead
from ...scraping.scraper import scrape_url

router = APIRouter()


@router.get("/{restaurant_id}/content", response_model=RestaurantDocumentRead)
def get_restaurant_content(
    restaurant_id: str,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get the latest scraped content for a restaurant."""
    restaurant = session.exec(select(Restaurant).where(Restaurant.id == restaurant_id)).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    
    # Get latest document
    latest_doc = session.exec(
        select(RestaurantDocument)
        .where(RestaurantDocument.restaurant_id == restaurant_id)
        .order_by(RestaurantDocument.created_at.desc())
    ).first()
    
    if not latest_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No content available for this restaurant")
    
    return RestaurantDocumentRead(
        id=latest_doc.id,
        restaurant_id=latest_doc.restaurant_id,
        content_md=latest_doc.content_md,
        meta=latest_doc.meta,
        created_at=latest_doc.created_at.isoformat() if latest_doc.created_at else None,
    )


# Note: Cache management has been moved to team-specific endpoints.
# See /api/teams/{team_id}/restaurants for cache configuration per team.


@router.post("/", response_model=RestaurantRead)
def create_restaurant(
    payload: RestaurantCreate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    # For now, restaurants are global; later we can scope by owner
    existing = session.exec(select(Restaurant).where(Restaurant.url == payload.url)).first()
    if existing:
        # Update display name if provided
        if payload.display_name and payload.display_name != existing.display_name:
            existing.display_name = payload.display_name
            session.add(existing)
            session.commit()
            session.refresh(existing)
        return existing

    r = Restaurant(url=payload.url, display_name=payload.display_name)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


@router.get("/", response_model=List[RestaurantRead])
def list_restaurants(
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """List all restaurants (global registry). Cache settings are per-team."""
    restaurants = session.exec(select(Restaurant)).all()
    return restaurants


@router.get("/{restaurant_id}", response_model=RestaurantRead)
def get_restaurant(
    restaurant_id: str,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get a restaurant by ID. Cache settings are managed per-team."""
    r = session.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    return r


# Menu endpoint removed - use /documents/latest to get raw text content instead


# Note: Scraping and cache management is now handled via team-specific endpoints:
# - POST /decision/ingest-restaurants (with team_id) for scraping with cache
# - GET /api/teams/{team_id}/restaurants for cache status per team


@router.get("/{restaurant_id}/documents", response_model=List[RestaurantDocumentRead])
def list_restaurant_documents(
    restaurant_id: str,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    if not session.get(Restaurant, restaurant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    docs = session.exec(
        select(RestaurantDocument).where(RestaurantDocument.restaurant_id == restaurant_id)
    ).all()
    return [
        RestaurantDocumentRead(
            id=doc.id,
            restaurant_id=doc.restaurant_id,
            content_md=doc.content_md,
            meta=doc.meta,
            created_at=doc.created_at.isoformat() if doc.created_at else None,
        )
        for doc in docs
    ]


@router.get("/{restaurant_id}/documents/latest", response_model=RestaurantDocumentRead)
def get_latest_restaurant_document(
    restaurant_id: str,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    if not session.get(Restaurant, restaurant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    doc = session.exec(
        select(RestaurantDocument)
        .where(RestaurantDocument.restaurant_id == restaurant_id)
        .order_by(RestaurantDocument.created_at.desc())
    ).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No document found")
    return RestaurantDocumentRead(
        id=doc.id,
        restaurant_id=doc.restaurant_id,
        content_md=doc.content_md,
        meta=doc.meta,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
    )


# Cache update endpoint removed - use PUT /api/teams/{team_id}/restaurants/{restaurant_id}/cache instead


@router.delete("/{restaurant_id}")
def delete_restaurant(
    restaurant_id: str,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a restaurant and all its associated documents."""
    r = session.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    
    # Delete all associated documents first
    docs = session.exec(
        select(RestaurantDocument).where(RestaurantDocument.restaurant_id == restaurant_id)
    ).all()
    for doc in docs:
        session.delete(doc)
    
    # Delete the restaurant
    session.delete(r)
    session.commit()
    
    return {"status": "ok", "message": "Restaurant deleted successfully"}
