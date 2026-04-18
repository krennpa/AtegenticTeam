from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from ..core.config import settings


TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
DEFAULT_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.googleMapsUri",
        "places.websiteUri",
        "places.primaryType",
        "places.types",
        "places.priceLevel",
        "places.rating",
        "places.userRatingCount",
    ]
)


class GooglePlacesConfigError(RuntimeError):
    """Raised when Google Maps configuration is missing."""


class GooglePlacesAPIError(RuntimeError):
    """Raised when a Google Places request fails."""


def _require_api_key() -> str:
    api_key = settings.GOOGLE_MAPS_SERVER_API_KEY
    if not api_key:
        raise GooglePlacesConfigError("GOOGLE_MAPS_SERVER_API_KEY is not configured")
    return api_key


def _normalize_place(place: dict[str, Any]) -> dict[str, Any]:
    display_name = place.get("displayName") or {}
    location = place.get("location") or {}

    return {
        "google_maps": {
            "place_id": place.get("id"),
            "display_name": display_name.get("text"),
            "formatted_address": place.get("formattedAddress"),
            "lat": location.get("latitude"),
            "lng": location.get("longitude"),
            "maps_uri": place.get("googleMapsUri"),
            "website_uri": place.get("websiteUri"),
            "primary_type": place.get("primaryType"),
            "types": place.get("types") or [],
            "price_level": place.get("priceLevel"),
            "rating": place.get("rating"),
            "user_rating_count": place.get("userRatingCount"),
            "last_enriched_at": datetime.now(timezone.utc).isoformat(),
        }
    }


def extract_google_maps_fields(place_result: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized google_maps payload from a Places search result."""
    return (place_result or {}).get("google_maps") or {}


async def search_places_by_text(
    text_query: str,
    *,
    field_mask: str = DEFAULT_FIELD_MASK,
    max_results: int = 5,
    language_code: str = "en",
) -> list[dict[str, Any]]:
    """Run Places Text Search (New) and return normalized restaurant candidates."""
    api_key = _require_api_key()

    payload = {
        "textQuery": text_query,
        "languageCode": language_code,
        "pageSize": max_results,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(TEXT_SEARCH_URL, headers=headers, json=payload)

    if response.status_code >= 400:
        raise GooglePlacesAPIError(
            f"Places Text Search failed with status {response.status_code}: {response.text}"
        )

    data = response.json()
    places = data.get("places", [])
    return [_normalize_place(place) for place in places]


async def resolve_place_by_text(text_query: str) -> dict[str, Any] | None:
    """Return the best normalized Places match for a free-text location query."""
    candidates = await search_places_by_text(text_query, max_results=1)
    if not candidates:
        return None
    return candidates[0]


async def search_nearby_places(
    *,
    latitude: float,
    longitude: float,
    radius_meters: float = 1500.0,
    included_types: list[str] | None = None,
    field_mask: str = DEFAULT_FIELD_MASK,
    max_results: int = 20,
    rank_preference: str = "DISTANCE",
    language_code: str = "en",
) -> list[dict[str, Any]]:
    """Run Places Nearby Search (New) and return normalized place candidates."""
    api_key = _require_api_key()

    payload = {
        "includedTypes": included_types or ["restaurant"],
        "maxResultCount": max_results,
        "rankPreference": rank_preference,
        "languageCode": language_code,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": radius_meters,
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(NEARBY_SEARCH_URL, headers=headers, json=payload)

    if response.status_code >= 400:
        raise GooglePlacesAPIError(
            f"Places Nearby Search failed with status {response.status_code}: {response.text}"
        )

    data = response.json()
    places = data.get("places", [])
    return [_normalize_place(place) for place in places]
