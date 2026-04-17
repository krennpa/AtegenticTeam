from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from ..schemas import CamelModel

class AgentDecisionRequest(CamelModel):
    team_id: str
    restaurant_ids: List[str]
    user_question: Optional[str] = "Based on the team's needs and the restaurant menus, what is the best lunch option? Please provide one restaurant and one specific dish recommendation, along with a brief explanation."


class AgentDecisionResponse(CamelModel):
    """Structured response returned by the agent endpoint for frontend rendering."""
    recommendation_restaurant_name: str
    recommendation_restaurant_url: Optional[str] = None
    recommended_dish: str
    explanation_md: str
    raw_text: str


class IngestRestaurantsRequest(CamelModel):
    team_id: str
    restaurant_urls: List[str]
    force_rescrape: Optional[bool] = False


class ProcessingDetail(CamelModel):
    url: str
    action: str  # 'scraped', 'cached', or 'failed'
    reason: str
    menu_type: Optional[str] = None


class IngestRestaurantsResponse(CamelModel):
    restaurant_ids: List[str]
    processed_count: int
    created_count: int
    scraped_count: int
    cached_count: int
    processing_details: List[ProcessingDetail]


class ExistingRestaurant(CamelModel):
    id: str
    url: str
    display_name: Optional[str] = None
    last_scraped_at: Optional[str] = None
    menu_type: Optional[str] = None
    content_age_days: Optional[int] = None
    has_content: bool = False


class ExistingRestaurantsResponse(CamelModel):
    restaurants: List[ExistingRestaurant]
    total_count: int
