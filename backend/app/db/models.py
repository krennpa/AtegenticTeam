from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlmodel import Field, SQLModel
from enum import Enum


class BudgetPreference(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class CacheStrategy(str, Enum):
    auto = "auto"  # System determines based on content analysis
    daily = "daily"  # Cache for ~6-12 hours (daily menus)
    weekly = "weekly"  # Cache for ~24-48 hours (weekly menus)
    static = "static"  # Cache for ~7 days (rarely changing menus)
    no_cache = "no_cache"  # Always scrape fresh


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    display_name: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RestaurantDocument(SQLModel, table=True):
    __tablename__ = "restaurant_documents"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    restaurant_id: str = Field(foreign_key="restaurants.id", index=True)

    # Raw scraped text content (not markdown, despite field name for backward compatibility)
    content_md: str
    meta: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(SQLITE_JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, unique=True)

    display_name: Optional[str] = None
    budget_preference: BudgetPreference = Field(default=BudgetPreference.medium)
    allergies: List[str] = Field(
        default_factory=list,
        sa_column=Column(SQLITE_JSON),
    )
    dietary_restrictions: List[str] = Field(
        default_factory=list,
        sa_column=Column(SQLITE_JSON),
    )
    other_preferences: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SQLITE_JSON),
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TeamPreference(SQLModel, table=True):
    __tablename__ = "team_preferences"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    team_id: str = Field(foreign_key="teams.id", index=True, unique=True)

    budget_preference: BudgetPreference = Field(default=BudgetPreference.medium)
    allergies: List[str] = Field(
        default_factory=list,
        sa_column=Column(SQLITE_JSON),
    )
    dietary_restrictions: List[str] = Field(
        default_factory=list,
        sa_column=Column(SQLITE_JSON),
    )
    other_preferences: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SQLITE_JSON),
    )
    member_count: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProfilePreferenceEvent(SQLModel, table=True):
    __tablename__ = "profile_preference_events"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    team_id: Optional[str] = Field(foreign_key="teams.id", index=True, default=None)

    event_type: str = Field(index=True)
    question_key: str = Field(index=True)
    answer: Any = Field(default=None, sa_column=Column(SQLITE_JSON))
    weight: float = Field(default=1.0)
    source: str = Field(default="user_gameplay", index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class Restaurant(SQLModel, table=True):
    __tablename__ = "restaurants"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    url: str = Field(unique=True, index=True)
    display_name: Optional[str] = None

    meta: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(SQLITE_JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# MenuItem model removed - we store raw markdown in RestaurantDocument instead


class TeamRestaurant(SQLModel, table=True):
    __tablename__ = "team_restaurants"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    team_id: str = Field(foreign_key="teams.id", index=True)
    restaurant_id: str = Field(foreign_key="restaurants.id", index=True)
    
    # Team-specific restaurant settings
    display_name: Optional[str] = None  # Team can override restaurant display name
    
    # Intelligent caching fields (per team)
    cache_strategy: CacheStrategy = Field(default=CacheStrategy.auto)
    cache_duration_hours: Optional[int] = None  # Override default duration
    next_scrape_at: Optional[datetime] = None  # When cache expires
    last_scraped_at: Optional[datetime] = None  # Last scrape time for this team
    
    is_active: bool = Field(default=True)
    added_by_user_id: str = Field(foreign_key="users.id", index=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Unique constraint on team_id + restaurant_id to prevent duplicates
    __table_args__ = {"sqlite_autoincrement": True}


class Team(SQLModel, table=True):
    __tablename__ = "teams"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    location: Optional[str] = None
    location_place_id: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    creator_user_id: str = Field(foreign_key="users.id", index=True)
    
    # Team settings
    is_active: bool = Field(default=True)
    max_members: Optional[int] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TeamMembership(SQLModel, table=True):
    __tablename__ = "team_memberships"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    team_id: str = Field(foreign_key="teams.id", index=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    
    # Membership status
    is_active: bool = Field(default=True)
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Unique constraint on team_id + user_id to prevent duplicate memberships
    __table_args__ = {"sqlite_autoincrement": True}


class DecisionRun(SQLModel, table=True):
    __tablename__ = "decision_runs"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    organizer_user_id: str = Field(foreign_key="users.id", index=True)
    team_id: Optional[str] = Field(foreign_key="teams.id", index=True, default=None)

    participant_profile_ids: List[str] = Field(
        default_factory=list, sa_column=Column(SQLITE_JSON)
    )
    restaurant_ids: List[str] = Field(default_factory=list, sa_column=Column(SQLITE_JSON))
    result: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(SQLITE_JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    
    # Notification content
    type: str = Field(index=True)  # e.g., "team_decision", "team_invite", etc.
    title: str
    message: str
    
    # Related entities
    team_id: Optional[str] = Field(foreign_key="teams.id", index=True, default=None)
    decision_run_id: Optional[str] = Field(foreign_key="decision_runs.id", index=True, default=None)
    
    # Status
    is_read: bool = Field(default=False, index=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
