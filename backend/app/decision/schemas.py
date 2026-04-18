from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from ..schemas import CamelModel

class AgentDecisionRequest(CamelModel):
    team_id: str
    restaurant_ids: List[str]
    decision_mode: Optional[str] = "standard"
    user_question: Optional[str] = "Based on the team's needs and the restaurant menus, what is the best lunch option? Please provide one restaurant and one specific dish recommendation, along with a brief explanation."


class AgentDecisionCandidate(CamelModel):
    rank: int
    restaurant_name: str
    restaurant_url: Optional[str] = None
    recommended_dish: Optional[str] = None
    rationale_md: str


class AgentDecisionFairnessSummary(CamelModel):
    policy: str
    summary_md: str
    balance_note: Optional[str] = None


class AgentDecisionTieBreakTurn(CamelModel):
    speaker_label: str
    stance: str
    utterance: str
    round_index: int


class AgentDecisionResponse(CamelModel):
    """Structured response returned by the agent endpoint for frontend rendering."""
    recommendation_restaurant_name: str
    recommendation_restaurant_url: Optional[str] = None
    recommended_dish: str
    explanation_md: str
    raw_text: str
    top_candidates: List[AgentDecisionCandidate] = []
    fairness_summary: Optional[AgentDecisionFairnessSummary] = None
    tie_break_available: bool = False
    tie_break_mode: Optional[str] = None
    tie_break_transcript: List[AgentDecisionTieBreakTurn] = []


class ConfirmDecisionChoiceRequest(CamelModel):
    team_id: str
    restaurant_name: str
    restaurant_url: Optional[str] = None
    recommended_dish: Optional[str] = None
    rationale_md: Optional[str] = None
    source: Optional[str] = "manual_choice"


class ConfirmDecisionChoiceResponse(CamelModel):
    decision_run_id: str
    restaurant_name: str
    message: str


class IngestRestaurantInput(CamelModel):
    url: str
    name: Optional[str] = None


class IngestRestaurantsRequest(CamelModel):
    team_id: str
    restaurant_urls: Optional[List[str]] = None
    restaurants: Optional[List[IngestRestaurantInput]] = None
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
    formatted_address: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    straight_line_distance_km: Optional[float] = None
    last_scraped_at: Optional[str] = None
    menu_type: Optional[str] = None
    content_age_days: Optional[int] = None
    has_content: bool = False


class ExistingRestaurantsResponse(CamelModel):
    restaurants: List[ExistingRestaurant]
    total_count: int


class DiscoverRestaurantsRequest(CamelModel):
    team_id: str
    radius_meters: Optional[int] = 1500
    candidate_limit: Optional[int] = 15
    result_limit: Optional[int] = 5


class DiscoveredRestaurant(CamelModel):
    display_name: str
    formatted_address: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    website_uri: Optional[str] = None
    maps_uri: Optional[str] = None
    primary_type: Optional[str] = None
    price_level: Optional[str] = None
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    straight_line_distance_km: Optional[float] = None
    compatibility_score: float
    score_breakdown: Dict[str, float] = {}
    recommendation_reasons: List[str] = []
    research_result_type: Optional[str] = None
    menu_summary: Optional[str] = None
    menu_items: List[str] = []
    cuisine_tags: List[str] = []
    dietary_signals: List[str] = []
    source_urls: List[str] = []
    existing_restaurant_id: Optional[str] = None


class DiscoverRestaurantsResponse(CamelModel):
    team_id: str
    team_location: str
    candidate_count: int
    results: List[DiscoveredRestaurant]
