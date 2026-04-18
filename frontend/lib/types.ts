export type BudgetPreference = 'low' | 'medium' | 'high'

export interface User {
  id: string
  email: string
  displayName?: string
}

export interface Profile {
  id: string
  userId: string
  displayName?: string
  budgetPreference: BudgetPreference
  allergies: string[]
  dietaryRestrictions: string[]
  otherPreferences: Record<string, any>
}

export type PreferenceEventType = 'this_or_that' | 'choice' | 'slider' | 'mood_pick' | 'veto_card'

export interface ProfilePreferenceEventCreate {
  eventType: PreferenceEventType
  questionKey: string
  answer: unknown
  weight?: number
  source?: string
  teamId?: string
}

export interface ProfilePreferenceEvent {
  id: string
  userId: string
  teamId?: string | null
  eventType: PreferenceEventType
  questionKey: string
  answer: unknown
  weight: number
  source: string
  createdAt: string
}

export interface ProfilePreferenceProgress {
  totalEvents: number
  points: number
  level: number
  completionPercent: number
  lastEventAt?: string | null
  coveredAreas: string[]
  suggestedNextAreas: string[]
}

export interface PreferenceQuestionOption {
  label: string
  value: string
}

export interface PreferenceQuestion {
  questionKey: string
  eventType: PreferenceEventType
  area: string
  prompt: string
  options: PreferenceQuestionOption[]
}

export interface PreferenceQuestionCatalogResponse {
  recommendedAreas: string[]
  questions: PreferenceQuestion[]
}

export interface TeamPreferenceSignal {
  value: string
  support: number
  memberCount: number
}

export interface TeamPreferenceOtherPreferences {
  signals?: Record<string, TeamPreferenceSignal>
  dislikes?: string[]
  recentMoods?: string[]
  areasSeen?: string[]
  aggregation?: {
    profileCount: number
    updatedAt: string
  }
  [key: string]: unknown
}

export interface TeamPreferenceSnapshot {
  id: string
  teamId: string
  budgetPreference: BudgetPreference
  allergies: string[]
  dietaryRestrictions: string[]
  otherPreferences: TeamPreferenceOtherPreferences
  memberCount: number
  createdAt: string
  updatedAt: string
}

export interface Team {
  id: string
  name: string
  description?: string
  location?: string
  locationPlaceId?: string
  locationLat?: number
  locationLng?: number
  creatorUserId: string
  isActive: boolean
  maxMembers?: number
  memberCount: number
  createdAt: string
}

export interface TeamMember {
  id: string
  userId: string
  displayName?: string
  joinedAt: string
}

export interface TeamWithMembers {
  id: string
  name: string
  description?: string
  location?: string
  locationPlaceId?: string
  locationLat?: number
  locationLng?: number
  creatorUserId: string
  isActive: boolean
  maxMembers?: number
  members: TeamMember[]
  memberCount?: number
  createdAt: string
}

export interface Restaurant {
  id: string
  url: string
  displayName?: string
  meta: Record<string, any>
  lastScrapedAt?: string
}

export interface RestaurantDocument {
  id: string
  restaurantId: string
  contentMd: string
  meta: Record<string, any>
  createdAt?: string
}

// Classic decision types removed. Only agent decision mode is supported.

// Agent-based decision result
export interface AgentDecisionCandidate {
  rank: number
  restaurantName: string
  restaurantUrl?: string | null
  recommendedDish?: string | null
  rationaleMd: string
}

export interface AgentDecisionFairnessSummary {
  policy: string
  summaryMd: string
  balanceNote?: string | null
}

export interface AgentDecisionTieBreakTurn {
  speakerLabel: string
  stance: string
  utterance: string
  roundIndex: number
}

export interface AgentDecisionResponse {
  recommendationRestaurantName: string
  recommendationRestaurantUrl?: string | null
  recommendedDish: string
  explanationMd: string
  rawText: string
  topCandidates: AgentDecisionCandidate[]
  fairnessSummary?: AgentDecisionFairnessSummary | null
  tieBreakAvailable: boolean
  tieBreakMode?: string | null
  tieBreakTranscript: AgentDecisionTieBreakTurn[]
}

export interface ConfirmDecisionChoiceRequest {
  teamId: string
  restaurantName: string
  restaurantUrl?: string | null
  recommendedDish?: string | null
  rationaleMd?: string | null
  source?: string
}

export interface ConfirmDecisionChoiceResponse {
  decisionRunId: string
  restaurantName: string
  message: string
}

export interface AgentDecisionRequest {
  teamId: string
  restaurantIds: string[]
  decisionMode?: 'standard' | 'tie_break'
  userQuestion?: string
}

export interface IngestRestaurantInput {
  url: string
  name?: string
}

export interface ProcessingDetail {
  url: string
  action: 'scraped' | 'cached' | 'failed'
  reason: string
  menuType?: string
}

export interface IngestRestaurantsResponse {
  restaurantIds: string[]
  processedCount: number
  createdCount: number
  scrapedCount: number
  cachedCount: number
  processingDetails: ProcessingDetail[]
}

export interface ExistingRestaurant {
  id: string
  url: string
  displayName?: string
  formattedAddress?: string
  locationLat?: number
  locationLng?: number
  straightLineDistanceKm?: number
  lastScrapedAt?: string
  menuType?: string
  contentAgeDays?: number
  hasContent: boolean
}

export interface ExistingRestaurantsResponse {
  restaurants: ExistingRestaurant[]
  totalCount: number
}

export interface DiscoverRestaurantsRequest {
  teamId: string
  radiusMeters?: number
  candidateLimit?: number
  resultLimit?: number
}

export interface DiscoveredRestaurant {
  displayName: string
  formattedAddress?: string
  locationLat?: number
  locationLng?: number
  websiteUri?: string | null
  mapsUri?: string | null
  primaryType?: string | null
  priceLevel?: string | null
  rating?: number | null
  userRatingCount?: number | null
  straightLineDistanceKm?: number | null
  compatibilityScore: number
  scoreBreakdown: Record<string, number>
  recommendationReasons: string[]
  researchResultType?: string | null
  menuSummary?: string | null
  menuItems: string[]
  cuisineTags: string[]
  dietarySignals: string[]
  sourceUrls: string[]
  existingRestaurantId?: string | null
}

export interface DiscoverRestaurantsResponse {
  teamId: string
  teamLocation: string
  candidateCount: number
  results: DiscoveredRestaurant[]
}

export interface DecisionRun {
  id: string
  organizerUserId: string
  teamId?: string
  restaurantIds: string[]
  result: {
    recommendationRestaurantName: string
    recommendationRestaurantUrl?: string | null
    recommendedDish: string
    explanationMd: string
    rawText: string
  }
  createdAt: string
}

export interface Notification {
  id: string
  userId: string
  type: string
  title: string
  message: string
  teamId?: string
  decisionRunId?: string
  isRead: boolean
  createdAt: string
}

export interface NotificationCountResponse {
  unreadCount: number
}
