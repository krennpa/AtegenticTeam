from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from pydantic import ConfigDict

from .db.models import BudgetPreference, CacheStrategy


def to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class UserRead(CamelModel):
    id: str
    email: str
    display_name: Optional[str] = None


class UserCreate(CamelModel):
    email: str
    password: str
    display_name: Optional[str] = None


class LoginRequest(CamelModel):
    email: str
    password: str


class TokenResponse(CamelModel):
    user: UserRead
    token: str


class ProfileRead(CamelModel):
    id: str
    user_id: str
    display_name: Optional[str] = None
    budget_preference: BudgetPreference
    allergies: List[str] = []
    dietary_restrictions: List[str] = []
    other_preferences: Dict[str, Any] = {}


class ProfileUpdate(CamelModel):
    display_name: Optional[str] = None
    budget_preference: Optional[BudgetPreference] = None
    allergies: Optional[List[str]] = None
    dietary_restrictions: Optional[List[str]] = None
    other_preferences: Optional[Dict[str, Any]] = None


# Restaurant and Menu
class RestaurantCreate(CamelModel):
    url: str
    display_name: Optional[str] = None


class RestaurantRead(CamelModel):
    id: str
    url: str
    display_name: Optional[str] = None
    meta: Dict[str, Any] = {}


class TeamRestaurantRead(CamelModel):
    id: str
    team_id: str
    restaurant_id: str
    display_name: Optional[str] = None
    cache_strategy: CacheStrategy = CacheStrategy.auto
    cache_duration_hours: Optional[int] = None
    next_scrape_at: Optional[str] = None
    last_scraped_at: Optional[str] = None
    is_active: bool = True
    added_by_user_id: str
    restaurant_url: str = ""
    is_cache_valid: bool = False


class TeamRestaurantCacheUpdate(CamelModel):
    cache_strategy: Optional[CacheStrategy] = None
    cache_duration_hours: Optional[int] = None


# MenuItemRead schema removed - we work with raw text documents instead


class RestaurantDocumentRead(CamelModel):
    id: str
    restaurant_id: str
    content_md: str  # Raw scraped text content (field name kept for backward compatibility)
    meta: Dict[str, Any] = {}
    created_at: str


# Team Management
class TeamCreate(CamelModel):
    name: str
    description: Optional[str] = None
    max_members: Optional[int] = None


class TeamRead(CamelModel):
    id: str
    name: str
    description: Optional[str] = None
    creator_user_id: str
    is_active: bool
    max_members: Optional[int] = None
    member_count: int = 0
    created_at: str


class TeamUpdate(CamelModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_members: Optional[int] = None
    is_active: Optional[bool] = None


class TeamMemberRead(CamelModel):
    id: str
    user_id: str
    display_name: Optional[str] = None
    joined_at: str


class TeamWithMembersRead(CamelModel):
    id: str
    name: str
    description: Optional[str] = None
    creator_user_id: str
    is_active: bool
    max_members: Optional[int] = None
    members: List[TeamMemberRead] = []
    created_at: str


class JoinTeamRequest(CamelModel):
    team_id: str


# Classic decision models removed. The application now uses only the agent-based
# decision flow via /decision/agent-decision returning AgentDecisionResponse.


class DecisionRunRead(CamelModel):
    id: str
    organizer_user_id: str
    team_id: Optional[str] = None
    restaurant_ids: List[str] = []
    result: Dict[str, Any] = {}
    created_at: str


# Notifications
class NotificationRead(CamelModel):
    id: str
    user_id: str
    type: str
    title: str
    message: str
    team_id: Optional[str] = None
    decision_run_id: Optional[str] = None
    is_read: bool
    created_at: str


class NotificationCountResponse(CamelModel):
    unread_count: int
