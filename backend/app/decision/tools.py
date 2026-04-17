from typing import List, Dict, Any, Type
from datetime import datetime
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db.models import Team, TeamMembership, Profile, Restaurant, RestaurantDocument
from ..api.deps import get_db_session

# Pydantic models for tool inputs
class RetrieveNeedsInput(BaseModel):
    team_id: str = Field(description="The ID of the team to retrieve needs for.")

class RetrieveMenuMarkdownsInput(BaseModel):
    restaurant_ids: List[str] = Field(description="A list of restaurant IDs to retrieve menus for.")

# Base tool for database access
class BaseDBTool:
    def __init__(self, db_session: Session):
        self.db = db_session

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
    description = "Use this tool to get the menu markdown and metadata for one or more restaurants. Returns menu content, menu type (daily/weekly/static/mixed), detected days mentioned in menu, scraped timestamp, content age in hours, and freshness status."
    args_schema: Type[BaseModel] = RetrieveMenuMarkdownsInput

    def _run(self, restaurant_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Use the tool."""
        menus = []
        now = datetime.now()
        
        for rid in restaurant_ids:
            restaurant = self.db.get(Restaurant, rid)
            if not restaurant:
                menus.append({"restaurant_id": rid, "error": "Restaurant not found."})
                continue

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
                    "menu_markdown": "",
                    "warning": "No menu content found for this restaurant."
                })
        
        return {"menus": menus}

def get_tools(db_session: Session):
    """Factory function to get all tools with a db session."""
    return [RetrieveNeedsTool(db_session), RetrieveMenuMarkdownsTool(db_session)]
