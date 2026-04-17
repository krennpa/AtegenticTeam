export interface User {
  id: string
  email: string
  displayName?: string
}

export interface Profile {
  id: string
  userId: string
  displayName?: string
  budgetPreference: 'low' | 'medium' | 'high'
  allergies: string[]
  dietaryRestrictions: string[]
  otherPreferences: Record<string, any>
}

export interface Team {
  id: string
  name: string
  description?: string
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
export interface AgentDecisionResponse {
  recommendationRestaurantName: string
  recommendationRestaurantUrl?: string | null
  recommendedDish: string
  explanationMd: string
  rawText: string
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
  lastScrapedAt?: string
  menuType?: string
  contentAgeDays?: number
  hasContent: boolean
}

export interface ExistingRestaurantsResponse {
  restaurants: ExistingRestaurant[]
  totalCount: number
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
