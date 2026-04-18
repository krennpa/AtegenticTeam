from typing import List, Dict, Any, Type
from datetime import datetime
import math
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db.models import Team, TeamMembership, Profile, TeamPreference, Restaurant, RestaurantDocument

# Pydantic models for tool inputs
class RetrieveNeedsInput(BaseModel):
    team_id: str = Field(description="The ID of the team to retrieve needs for.")

class RetrieveMenuMarkdownsInput(BaseModel):
    restaurant_ids: List[str] = Field(description="A list of restaurant IDs to retrieve menus for.")

# Base tool for database access
class BaseDBTool:
    def __init__(self, db_session: Session):
        self.db = db_session


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

# Tool Implementations
class RetrieveNeedsTool(BaseDBTool):
    """Tool to retrieve the aggregated needs and preferences of all members in a team."""
    name = "retrieve_team_needs"
    description = "Use this tool to get the complete dietary needs, allergies, budget preferences, and other preferences for all members of a team. Returns team name, member count, budgets, allergies, dietary restrictions, and additional preferences."
    args_schema: Type[BaseModel] = RetrieveNeedsInput

    def _run(self, team_id: str) -> Dict[str, Any]:
        """Use the tool."""
        team = self.db.exec(select(Team).where(Team.id == team_id)).first()
        if not team:
            return {"error": "Team not found."}

        team_preference = self.db.exec(
            select(TeamPreference).where(TeamPreference.team_id == team_id)
        ).first()
        if team_preference:
            other_preferences = []
            for key, value in (team_preference.other_preferences or {}).items():
                if value:
                    other_preferences.append(f"{key}: {value}")
            return {
                "team_id": team_id,
                "team_name": team.name,
                "member_count": team_preference.member_count,
                "budgets": [team_preference.budget_preference.value],
                "allergies": team_preference.allergies,
                "dietary_restrictions": team_preference.dietary_restrictions,
                "other_preferences": other_preferences,
            }

        memberships = self.db.exec(
            select(TeamMembership).where(
                TeamMembership.team_id == team_id, TeamMembership.is_active == True
            )
        ).all()

        if not memberships:
            return {"error": "No active members found in this team."}

        aggregated_preferences = {
            "team_id": team_id,
            "team_name": team.name,
            "member_count": len(memberships),
            "budgets": [],
            "allergies": [],
            "dietary_restrictions": [],
            "other_preferences": [],
        }

        for member in memberships:
            profile = self.db.exec(select(Profile).where(Profile.user_id == member.user_id)).first()
            if profile:
                aggregated_preferences["budgets"].append(profile.budget_preference.value)
                aggregated_preferences["allergies"].extend(profile.allergies)
                aggregated_preferences["dietary_restrictions"].extend(profile.dietary_restrictions)
                
                if profile.other_preferences:
                    for key, value in profile.other_preferences.items():
                        if value:
                            aggregated_preferences["other_preferences"].append(f"{key}: {value}")

        # Deduplicate lists
        aggregated_preferences["allergies"] = list(set(aggregated_preferences["allergies"]))
        aggregated_preferences["dietary_restrictions"] = list(set(aggregated_preferences["dietary_restrictions"]))
        aggregated_preferences["other_preferences"] = list(set(aggregated_preferences["other_preferences"]))

        return aggregated_preferences

class RetrieveMenuMarkdownsTool(BaseDBTool):
    """Tool to retrieve the markdown content of menus for a list of restaurants."""
    name = "retrieve_restaurant_menus"
    description = "Use this tool to get the menu markdown and metadata for one or more restaurants. Returns menu content, menu type (daily/weekly/static/mixed), detected days mentioned in menu, scraped timestamp, content age in hours, freshness status, Google Maps restaurant metadata, and straight-line distance from the team's saved location when available."
    args_schema: Type[BaseModel] = RetrieveMenuMarkdownsInput

    def __init__(self, db_session: Session, team_id: str | None = None):
        super().__init__(db_session)
        self.team_id = team_id

    def _run(self, restaurant_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Use the tool."""
        menus = []
        now = datetime.now()
        team = self.db.get(Team, self.team_id) if self.team_id else None
        team_location = {
            "location": team.location if team else None,
            "place_id": team.location_place_id if team else None,
            "lat": team.location_lat if team else None,
            "lng": team.location_lng if team else None,
        }
        
        for rid in restaurant_ids:
            restaurant = self.db.get(Restaurant, rid)
            if not restaurant:
                menus.append({"restaurant_id": rid, "error": "Restaurant not found."})
                continue

            restaurant_google_maps = (restaurant.meta or {}).get("google_maps") or {}
            restaurant_lat = _coerce_float(restaurant_google_maps.get("lat"))
            restaurant_lng = _coerce_float(restaurant_google_maps.get("lng"))
            team_lat = _coerce_float(team_location.get("lat"))
            team_lng = _coerce_float(team_location.get("lng"))
            distance_km = None
            if None not in (team_lat, team_lng, restaurant_lat, restaurant_lng):
                distance_km = round(
                    _straight_line_distance_km(team_lat, team_lng, restaurant_lat, restaurant_lng),
                    2,
                )

            # Get the latest document for this restaurant
            doc = self.db.exec(
                select(RestaurantDocument)
                .where(RestaurantDocument.restaurant_id == rid)
                .order_by(RestaurantDocument.created_at.desc())
            ).first()

            if doc and doc.content_md:
                # Calculate content age
                content_age_hours = (now - doc.created_at).total_seconds() / 3600
                
                # Extract metadata
                menu_type = doc.meta.get("menu_type", "unknown")
                detected_days = doc.meta.get("detected_days", [])
                
                # Determine freshness status
                freshness = "fresh"
                if content_age_hours > 168:  # 7 days
                    freshness = "stale"
                elif content_age_hours > 48:  # 2 days
                    freshness = "aging"
                
                menus.append({
                    "restaurant_id": rid,
                    "restaurant_name": restaurant.display_name or restaurant.url,
                    "restaurant_url": restaurant.url,
                    "team_location": team_location,
                    "restaurant_location": {
                        "place_id": restaurant_google_maps.get("place_id"),
                        "formatted_address": restaurant_google_maps.get("formatted_address"),
                        "lat": restaurant_lat,
                        "lng": restaurant_lng,
                        "rating": restaurant_google_maps.get("rating"),
                        "user_rating_count": restaurant_google_maps.get("user_rating_count"),
                    },
                    "straight_line_distance_km": distance_km,
                    "menu_markdown": doc.content_md,
                    "menu_type": menu_type,
                    "detected_days": detected_days,
                    "scraped_at": doc.created_at.isoformat(),
                    "content_age_hours": round(content_age_hours, 1),
                    "freshness": freshness,
                })
            else:
                menus.append({
                    "restaurant_id": rid,
                    "restaurant_name": restaurant.display_name or restaurant.url,
                    "restaurant_url": restaurant.url,
                    "team_location": team_location,
                    "restaurant_location": {
                        "place_id": restaurant_google_maps.get("place_id"),
                        "formatted_address": restaurant_google_maps.get("formatted_address"),
                        "lat": restaurant_lat,
                        "lng": restaurant_lng,
                        "rating": restaurant_google_maps.get("rating"),
                        "user_rating_count": restaurant_google_maps.get("user_rating_count"),
                    },
                    "straight_line_distance_km": distance_km,
                    "menu_markdown": "",
                    "warning": "No menu content found for this restaurant."
                })
        
        return {"menus": menus}

def get_tools(db_session: Session, team_id: str | None = None):
    """Factory function to get all tools with a db session."""
    return [RetrieveNeedsTool(db_session), RetrieveMenuMarkdownsTool(db_session, team_id=team_id)]
