'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../../../lib/auth-context'
import {
  TeamWithMembers,
  AgentDecisionResponse,
  AgentDecisionRequest,
  ConfirmDecisionChoiceRequest,
  ConfirmDecisionChoiceResponse,
  IngestRestaurantInput,
  IngestRestaurantsResponse,
  ExistingRestaurantsResponse,
  RestaurantDocument,
  DiscoverRestaurantsResponse,
  DiscoveredRestaurant,
} from '../../../../lib/types'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../../../components/ui/card'
import { Button } from '../../../../components/ui/button'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../../../components/ui/accordion'
import { RefreshCw, Trash2, ChevronDown, ChevronUp, Compass } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { LoadingSpinner } from '../../../../components/ui/loading-spinner'
import { BaseStatusBadge } from '../../../../components/ui/base-status-badge'
import { DistanceBadge } from '../../../../components/ui/distance-badge'
import { FreshnessBadge } from '../../../../components/ui/freshness-badge'
import { PrivacyCallout } from '../../../../components/ui/privacy-callout'
import { TeamRestaurantMap } from '../../../../components/maps/TeamRestaurantMap'

type RestaurantSort = 'default' | 'nearest' | 'freshest'
type AgentRunStage = 'idle' | 'discovering' | 'shortlisting' | 'ingesting' | 'reasoning' | 'done' | 'error'

type PromptPreset = {
  id: string
  label: string
  question: string
}

type AgentActivity = {
  id: number
  title: string
  detail?: string
}

const PROMPT_PRESETS: PromptPreset[] = [
  {
    id: 'balanced',
    label: 'Balanced',
    question: 'Use your tools to retrieve masked team needs and menus. Recommend one restaurant and one dish with clear reasoning.',
  },
  {
    id: 'fast',
    label: 'Fast Lunch',
    question: 'Prioritize speed and convenience for today while still fitting masked team needs. Recommend one restaurant and one dish.',
  },
  {
    id: 'healthy',
    label: 'Healthy Focus',
    question: 'Prioritize healthy and dietary-fit options from available menus while respecting masked team preferences. Recommend one restaurant and one dish.',
  },
  {
    id: 'budget',
    label: 'Budget Safe',
    question: 'Prioritize value-for-money choices aligned with team budget profile and masked needs. Recommend one restaurant and one dish.',
  },
]

const DISCOVERY_RADIUS_METERS = 1500

function prettifyPreferenceToken(value: string): string {
  return value
    .replace(/[_:]/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function scoreWeight(score: number): number {
  const safe = Number.isFinite(score) ? Math.max(0, Math.min(score, 30)) : 0
  return Math.round((safe / 30) * 100)
}

export default function TeamDecisionPage() {
  const { api, user } = useAuth()
  const params = useParams()
  const teamId = params.id as string
  
  const [team, setTeam] = useState<TeamWithMembers | null>(null)
  const [restaurants, setRestaurants] = useState<IngestRestaurantInput[]>([{ url: '', name: '' }])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [existingRestaurants, setExistingRestaurants] = useState<ExistingRestaurantsResponse | null>(null)
  const [discoveryResult, setDiscoveryResult] = useState<DiscoverRestaurantsResponse | null>(null)
  const [selectedDiscoveryUrls, setSelectedDiscoveryUrls] = useState<Set<string>>(new Set())
  const [selectedMapRestaurantId, setSelectedMapRestaurantId] = useState<string | null>(null)
  const [discoveryLoading, setDiscoveryLoading] = useState(false)
  const [discoveryError, setDiscoveryError] = useState<string | null>(null)
  // Processing state (for data fetching/scraping)
  const [processing, setProcessing] = useState(false)
  const [processResult, setProcessResult] = useState<IngestRestaurantsResponse | null>(null)
  const [processError, setProcessError] = useState<string | null>(null)
  const [forceRescrape, setForceRescrape] = useState(false)
  
  // Agent state (for decision making)
  const [agentDeciding, setAgentDeciding] = useState(false)
  const [agentResult, setAgentResult] = useState<AgentDecisionResponse | null>(null)
  const [agentError, setAgentError] = useState<string | null>(null)
  const [visibleTieBreakTurns, setVisibleTieBreakTurns] = useState(0)
  const [tieBreakRunning, setTieBreakRunning] = useState(false)
  const [tieBreakPrefetching, setTieBreakPrefetching] = useState(false)
  const [tieBreakActivated, setTieBreakActivated] = useState(false)
  
  // Raw content viewing state
  const [viewingContent, setViewingContent] = useState<{[key: string]: RestaurantDocument | null}>({})
  const [expandedContent, setExpandedContent] = useState<{[key: string]: boolean}>({})
  
  // Restaurant action states
  const [rescrapingIds, setRescrapingIds] = useState<Set<string>>(new Set())
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())
  const [restaurantSort, setRestaurantSort] = useState<RestaurantSort>('default')
  const [isExistingDataOpen, setIsExistingDataOpen] = useState(false)
  const [isAddRefreshOpen, setIsAddRefreshOpen] = useState(false)
  const [selectedPresetId, setSelectedPresetId] = useState<string>(PROMPT_PRESETS[0].id)
  const [agentRunStage, setAgentRunStage] = useState<AgentRunStage>('idle')
  const [agentActivities, setAgentActivities] = useState<AgentActivity[]>([])
  const [agentAutoRunning, setAgentAutoRunning] = useState(false)
  const [confirmingChoiceKey, setConfirmingChoiceKey] = useState<string | null>(null)
  const [choiceConfirmation, setChoiceConfirmation] = useState<string | null>(null)
  const decisionLocked = Boolean(choiceConfirmation)

  useEffect(() => {
    if (api && teamId) {
      loadTeam()
      loadExistingRestaurants()
    }
  }, [api, teamId])

  const addAgentActivity = (title: string, detail?: string) => {
    setAgentActivities((prev) => [...prev, { id: Date.now() + prev.length, title, detail }])
  }

  const loadTeam = async () => {
    try {
      setLoading(true)
      const data = await api.get<TeamWithMembers>(`/teams/${teamId}`)
      setTeam(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load team details')
    } finally {
      setLoading(false)
    }
  }

  const loadExistingRestaurants = async () => {
    try {
      const data = await api.get<ExistingRestaurantsResponse>(`/decision/existing-restaurants/${teamId}`)
      setExistingRestaurants(data)
    } catch (err) {
      console.error('Failed to load existing restaurants:', err)
      // Don't show error to user as this is not critical
    }
  }

  const loadRawContent = async (restaurantId: string) => {
    try {
      const content = await api.get<RestaurantDocument>(`/restaurants/${restaurantId}/content`)
      setViewingContent(prev => ({ ...prev, [restaurantId]: content }))
    } catch (err) {
      console.error('Failed to load restaurant content:', err)
      setViewingContent(prev => ({ ...prev, [restaurantId]: { error: 'Failed to load content' } as any }))
    }
  }

  const toggleContentExpanded = (restaurantId: string) => {
    setExpandedContent(prev => ({ ...prev, [restaurantId]: !prev[restaurantId] }))
    // Load content on first expand if not already loaded
    if (!expandedContent[restaurantId] && !viewingContent[restaurantId]) {
      loadRawContent(restaurantId)
    }
  }

  const handleRescrapeRestaurant = async (restaurant: { id: string; url: string; displayName?: string }) => {
    try {
      setRescrapingIds(prev => new Set(prev).add(restaurant.id))
      await api.post<IngestRestaurantsResponse>('/decision/ingest-restaurants', {
        teamId,
        restaurants: [{ url: restaurant.url, name: restaurant.displayName }],
        forceRescrape: true,
      })
      // Reload content and restaurant list
      await loadRawContent(restaurant.id)
      await loadExistingRestaurants()
    } catch (err) {
      console.error('Failed to refresh restaurant data:', err)
      alert('Failed to refresh restaurant data. Please try again.')
    } finally {
      setRescrapingIds(prev => {
        const newSet = new Set(prev)
        newSet.delete(restaurant.id)
        return newSet
      })
    }
  }

  const handleDeleteRestaurant = async (restaurantId: string) => {
    if (!confirm('Remove this restaurant from the team? The global restaurant record remains unchanged.')) {
      return
    }
    
    try {
      setDeletingIds(prev => new Set(prev).add(restaurantId))
      await api.delete(`/api/teams/${teamId}/restaurants/${restaurantId}`)
      // Reload restaurant list
      await loadExistingRestaurants()
    } catch (err) {
      console.error('Failed to delete restaurant:', err)
      alert('Failed to remove restaurant from this team. Please try again.')
    } finally {
      setDeletingIds(prev => {
        const newSet = new Set(prev)
        newSet.delete(restaurantId)
        return newSet
      })
    }
  }

  // Remove auto-load - content will be loaded on demand when user expands

  const addRestaurantField = () => {
    setRestaurants(prev => [...prev, { url: '', name: '' }])
  }

  const removeRestaurantField = (index: number) => {
    setRestaurants(prev => prev.filter((_, i) => i !== index))
  }

  const updateRestaurant = (index: number, field: keyof IngestRestaurantInput, value: string) => {
    setRestaurants(prev => prev.map((restaurant, i) => (
      i === index ? { ...restaurant, [field]: value } : restaurant
    )))
  }

  const resetAgent = () => {
    setAgentResult(null)
    setProcessResult(null)
    setProcessError(null)
    setAgentError(null)
    setAgentRunStage('idle')
    setAgentActivities([])
    setVisibleTieBreakTurns(0)
    setTieBreakPrefetching(false)
    setTieBreakActivated(false)
    setChoiceConfirmation(null)
    setRestaurants([{ url: '', name: '' }])
  }

  const getDiscoveryRestaurantUrl = (restaurant: DiscoveredRestaurant): string | null =>
    restaurant.websiteUri || restaurant.mapsUri || null

  const getDiscoveredMapCardId = (restaurant: DiscoveredRestaurant, index: number) => {
    if (restaurant.existingRestaurantId) {
      return `discovered-existing-${restaurant.existingRestaurantId}`
    }
    const base = `${restaurant.displayName}-${restaurant.formattedAddress ?? index}`
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
    return `discovered-${base}-${index}`
  }

  const getExistingMapCardId = (restaurantId: string) => `existing-${restaurantId}`

  const toggleDiscoverySelection = (restaurant: DiscoveredRestaurant) => {
    const restaurantUrl = getDiscoveryRestaurantUrl(restaurant)
    if (!restaurantUrl) return
    setSelectedDiscoveryUrls((prev) => {
      const next = new Set(prev)
      if (next.has(restaurantUrl)) {
        next.delete(restaurantUrl)
      } else {
        next.add(restaurantUrl)
      }
      return next
    })
  }

  const currentPromptQuestion =
    PROMPT_PRESETS.find((preset) => preset.id === selectedPresetId)?.question ?? PROMPT_PRESETS[0].question

  const handleProcessInformation = async (e: React.MouseEvent) => {
    e.preventDefault()
    if (!api || !team) return

    const validRestaurants = restaurants
      .map((restaurant) => ({
        url: restaurant.url.trim(),
        name: restaurant.name?.trim() || undefined,
      }))
      .filter((restaurant) => restaurant.url)
    if (validRestaurants.length === 0) {
      setProcessError('Please add at least one restaurant URL to process')
      return
    }

    try {
      setProcessing(true)
      setProcessError(null)
      setProcessResult(null)

      // Call ingest endpoint to fetch and scrape restaurant data
      const result = await api.post<IngestRestaurantsResponse>('/decision/ingest-restaurants', {
        teamId: teamId,
        restaurants: validRestaurants,
        forceRescrape: forceRescrape,
      })
      
      setProcessResult(result)
      if (result.restaurantIds.length === 0) {
        setProcessError('No restaurants were processed successfully. Please check the URLs and try again.')
      } else {
        // Reload existing restaurants to show updated data
        loadExistingRestaurants()
      }
    } catch (err) {
      setProcessError(err instanceof Error ? err.message : 'Failed to process restaurant information')
    } finally {
      setProcessing(false)
    }
  }

  const handleMakeAgentDecision = async (e: React.MouseEvent) => {
    e.preventDefault()
    if (!api || !team || decisionLocked) return

    const restaurantIds = getDecisionRestaurantIds()

    if (restaurantIds.length === 0) {
      setAgentError('No restaurant data available. Please process restaurant information first or ensure existing restaurants have content.')
      return
    }

    try {
      setAgentDeciding(true)
      setAgentError(null)
      setAgentResult(null)
      setAgentRunStage('reasoning')
      addAgentActivity('Reading masked team needs')
      addAgentActivity('Evaluating available menus and fit signals')
      setTieBreakPrefetching(false)
      setTieBreakActivated(false)
      setChoiceConfirmation(null)

      // Run agent with the restaurant IDs
      const result = await api.post<AgentDecisionResponse>('/decision/agent-decision', {
        teamId: teamId,
        restaurantIds: restaurantIds,
        decisionMode: 'standard',
        userQuestion: currentPromptQuestion,
      } satisfies AgentDecisionRequest)
      setAgentResult(result)
      setVisibleTieBreakTurns(0)
      setAgentRunStage('done')
      addAgentActivity('Final recommendation ready')
    } catch (err) {
      setAgentError(err instanceof Error ? err.message : 'Failed to run agent decision')
      setAgentRunStage('error')
    } finally {
      setAgentDeciding(false)
    }
  }

  const getDecisionRestaurantIds = () => {
    if (processResult && processResult.restaurantIds && processResult.restaurantIds.length > 0) {
      return processResult.restaurantIds
    }
    if (existingRestaurants && existingRestaurants.restaurants.length > 0) {
      return existingRestaurants.restaurants
        .filter(r => r.hasContent)
        .map(r => r.id)
    }
    return []
  }

  const handleStartTieBreak = async () => {
    if (!api || !team || tieBreakRunning || decisionLocked) return

    if ((agentResult?.tieBreakTranscript?.length ?? 0) > 0) {
      setTieBreakActivated(true)
      setVisibleTieBreakTurns(0)
      return
    }

    const restaurantIds = getDecisionRestaurantIds()
    if (restaurantIds.length < 2) {
      setAgentError('Need at least two viable restaurant candidates for Tie-Break.')
      return
    }

    try {
      setTieBreakRunning(true)
      setAgentError(null)
      setTieBreakActivated(true)
      const result = await api.post<AgentDecisionResponse>('/decision/agent-decision', {
        teamId,
        restaurantIds,
        decisionMode: 'tie_break',
        userQuestion: 'Run an explicit Tie-Break between the strongest lunch options and resolve with a final choice.'
      } satisfies AgentDecisionRequest)
      setAgentResult(result)
      setVisibleTieBreakTurns(0)
    } catch (err) {
      setAgentError(err instanceof Error ? err.message : 'Failed to run Tie-Break')
    } finally {
      setTieBreakRunning(false)
    }
  }

  const hasTeamBase = Boolean(team?.location && team.location.trim())
  const hasDistanceReadyBase =
    typeof team?.locationLat === 'number' && typeof team?.locationLng === 'number'
  const isAgentBusy = agentDeciding || agentAutoRunning
  const agentStageLabel = ({
    idle: 'Idle',
    discovering: 'Discovering',
    shortlisting: 'Shortlisting',
    ingesting: 'Ingesting',
    reasoning: 'Reasoning',
    done: 'Completed',
    error: 'Error',
  } as Record<AgentRunStage, string>)[agentRunStage]

  const sortedRestaurants = useMemo(() => {
    const source = existingRestaurants?.restaurants ?? []
    const sorted = [...source]

    if (restaurantSort === 'nearest') {
      sorted.sort((a, b) => {
        const aDistance = typeof a.straightLineDistanceKm === 'number' ? a.straightLineDistanceKm : Number.POSITIVE_INFINITY
        const bDistance = typeof b.straightLineDistanceKm === 'number' ? b.straightLineDistanceKm : Number.POSITIVE_INFINITY
        return aDistance - bDistance
      })
      return sorted
    }

    if (restaurantSort === 'freshest') {
      sorted.sort((a, b) => {
        const aFreshness = typeof a.contentAgeDays === 'number' ? a.contentAgeDays : Number.POSITIVE_INFINITY
        const bFreshness = typeof b.contentAgeDays === 'number' ? b.contentAgeDays : Number.POSITIVE_INFINITY
        return aFreshness - bFreshness
      })
      return sorted
    }

    return source
  }, [existingRestaurants, restaurantSort])

  const mapRestaurants = useMemo(() => {
    if (discoveryResult?.results?.length) {
      return discoveryResult.results
        .map((restaurant, index) => {
          if (typeof restaurant.locationLat !== 'number' || typeof restaurant.locationLng !== 'number') {
            return null
          }
          return {
            id: getDiscoveredMapCardId(restaurant, index),
            name: restaurant.displayName,
            lat: restaurant.locationLat,
            lng: restaurant.locationLng,
            address: restaurant.formattedAddress,
            score: restaurant.compatibilityScore,
            distanceKm: restaurant.straightLineDistanceKm ?? null,
            mapsUri: restaurant.mapsUri ?? null,
            isTopPick: index === 0,
          }
        })
        .filter((restaurant): restaurant is NonNullable<typeof restaurant> => Boolean(restaurant))
    }

    return sortedRestaurants
      .map((restaurant) => {
        if (typeof restaurant.locationLat !== 'number' || typeof restaurant.locationLng !== 'number') {
          return null
        }
        return {
          id: getExistingMapCardId(restaurant.id),
          name: restaurant.displayName || restaurant.url,
          lat: restaurant.locationLat,
          lng: restaurant.locationLng,
          address: restaurant.formattedAddress,
          distanceKm: restaurant.straightLineDistanceKm ?? null,
          mapsUri: null,
          isTopPick: false,
        }
      })
      .filter((restaurant): restaurant is NonNullable<typeof restaurant> => Boolean(restaurant))
  }, [discoveryResult, sortedRestaurants])

  const handleSelectMapRestaurant = (restaurantId: string) => {
    setSelectedMapRestaurantId(restaurantId)
    const target = document.getElementById(`restaurant-card-${restaurantId}`)
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }

  const tieBreakSpeakerStyles = useMemo(() => {
    const transcript = agentResult?.tieBreakTranscript ?? []
    const palette = [
      {
        align: 'justify-start',
        bubble: 'bg-rose-100 border-rose-200 text-rose-950',
        badge: 'bg-rose-200 text-rose-900',
        meta: 'text-rose-700',
      },
      {
        align: 'justify-end',
        bubble: 'bg-sky-100 border-sky-200 text-sky-950',
        badge: 'bg-sky-200 text-sky-900',
        meta: 'text-sky-700',
      },
      {
        align: 'justify-start',
        bubble: 'bg-amber-100 border-amber-200 text-amber-950',
        badge: 'bg-amber-200 text-amber-900',
        meta: 'text-amber-700',
      },
    ]
    const mapping: Record<string, typeof palette[number]> = {}
    let speakerIndex = 0
    for (const turn of transcript) {
      const key = turn.speakerLabel
      if (!key || mapping[key]) continue
      if (key.toLowerCase() === 'moderator') {
        mapping[key] = {
          align: 'justify-center',
          bubble: 'bg-violet-100 border-violet-200 text-violet-950',
          badge: 'bg-violet-200 text-violet-900',
          meta: 'text-violet-700',
        }
        continue
      }
      mapping[key] = palette[speakerIndex % palette.length]
      speakerIndex += 1
    }
    return mapping
  }, [agentResult])

  useEffect(() => {
    const shouldPrefetch =
      !!api &&
      !decisionLocked &&
      !agentDeciding &&
      !tieBreakRunning &&
      !tieBreakPrefetching &&
      !!agentResult &&
      (agentResult.topCandidates?.length ?? 0) >= 2 &&
      (agentResult.tieBreakTranscript?.length ?? 0) === 0

    if (!shouldPrefetch) {
      return
    }

    let cancelled = false
    const restaurantIds = getDecisionRestaurantIds()
    if (restaurantIds.length < 2) {
      return
    }

    const runPrefetch = async () => {
      try {
        setTieBreakPrefetching(true)
        const result = await api.post<AgentDecisionResponse>('/decision/agent-decision', {
          teamId,
          restaurantIds,
          decisionMode: 'tie_break',
          userQuestion: 'Run an explicit Tie-Break between the strongest lunch options and resolve with a final choice.'
        } satisfies AgentDecisionRequest)
        if (!cancelled) {
          setAgentResult(result)
        }
      } catch {
        // Ignore prefetch failures; manual Tie-Break remains available.
      } finally {
        if (!cancelled) {
          setTieBreakPrefetching(false)
        }
      }
    }

    void runPrefetch()

    return () => {
      cancelled = true
    }
  }, [api, decisionLocked, agentDeciding, tieBreakPrefetching, tieBreakRunning, agentResult, teamId])

  useEffect(() => {
    const transcript = tieBreakActivated ? (agentResult?.tieBreakTranscript ?? []) : []
    if (!transcript.length) {
      setVisibleTieBreakTurns(0)
      return
    }

    setVisibleTieBreakTurns(1)
    const timer = window.setInterval(() => {
      setVisibleTieBreakTurns((current) => {
        if (current >= transcript.length) {
          window.clearInterval(timer)
          return current
        }
        return current + 1
      })
    }, 1100)

    return () => window.clearInterval(timer)
  }, [agentResult, tieBreakActivated])

  const handleDiscoverRestaurants = async (e: React.MouseEvent) => {
    e.preventDefault()
    if (!api || !team) return

    if (team.locationLat == null || team.locationLng == null) {
      setDiscoveryError('Team location is required before discovery can run.')
      return
    }

    try {
      setDiscoveryLoading(true)
      setDiscoveryError(null)
      const result = await api.post<DiscoverRestaurantsResponse>('/decision/discover-restaurants', {
        teamId,
        radiusMeters: DISCOVERY_RADIUS_METERS,
        candidateLimit: 15,
        resultLimit: 5,
      })
      setDiscoveryResult(result)
    } catch (err) {
      setDiscoveryError(err instanceof Error ? err.message : 'Failed to discover restaurants')
    } finally {
      setDiscoveryLoading(false)
    }
  }

  useEffect(() => {
    if (!discoveryResult || discoveryResult.results.length === 0) return
    const defaults = discoveryResult.results
      .map((restaurant) => restaurant.websiteUri || restaurant.mapsUri || null)
      .filter((url): url is string => Boolean(url))
      .slice(0, 3)
    setSelectedDiscoveryUrls(new Set(defaults))
  }, [discoveryResult])

  useEffect(() => {
    if (!mapRestaurants.length) {
      setSelectedMapRestaurantId(null)
      return
    }

    if (!selectedMapRestaurantId || !mapRestaurants.some((restaurant) => restaurant.id === selectedMapRestaurantId)) {
      setSelectedMapRestaurantId(mapRestaurants[0].id)
    }
  }, [mapRestaurants, selectedMapRestaurantId])

  const handleRunAgentSession = async () => {
    if (!api || !team || decisionLocked) return

    setAgentError(null)
    setDiscoveryError(null)
    setAgentResult(null)
    setAgentActivities([])
    setAgentAutoRunning(true)

    try {
      let discovered: DiscoverRestaurantsResponse | null = discoveryResult
      let restaurantIds: string[] = []

      if (team.locationLat != null && team.locationLng != null) {
        setAgentRunStage('discovering')
        addAgentActivity('Finding nearby candidates')
        discovered = await api.post<DiscoverRestaurantsResponse>('/decision/discover-restaurants', {
          teamId,
          radiusMeters: DISCOVERY_RADIUS_METERS,
          candidateLimit: 15,
          resultLimit: 5,
        })
        setDiscoveryResult(discovered)

        const selectedUrls = Array.from(selectedDiscoveryUrls)
        const fallbackUrls = discovered.results
          .map((restaurant) => getDiscoveryRestaurantUrl(restaurant))
          .filter((url): url is string => Boolean(url))
          .slice(0, 3)
        setAgentRunStage('shortlisting')
        addAgentActivity('Building shortlist from compatibility ranking')

        const urlsToIngest = (selectedUrls.length > 0 ? selectedUrls : fallbackUrls).map((url) => ({
          url,
          name: discovered?.results.find((result) => (result.websiteUri || result.mapsUri) === url)?.displayName,
        }))

        if (urlsToIngest.length > 0) {
          setAgentRunStage('ingesting')
          addAgentActivity('Refreshing menu evidence for shortlist')
          const ingestResult = await api.post<IngestRestaurantsResponse>('/decision/ingest-restaurants', {
            teamId,
            restaurants: urlsToIngest,
            forceRescrape,
          })
          setProcessResult(ingestResult)
          restaurantIds = ingestResult.restaurantIds
          await loadExistingRestaurants()
        }
      } else {
        addAgentActivity('Skipping discovery: team base coordinates missing')
      }

      if (restaurantIds.length === 0) {
        const fallbackProcessed = processResult?.restaurantIds ?? []
        const fallbackExisting = existingRestaurants?.restaurants
          .filter((restaurant) => restaurant.hasContent)
          .map((restaurant) => restaurant.id) ?? []
        restaurantIds = fallbackProcessed.length > 0 ? fallbackProcessed : fallbackExisting
      }

      if (restaurantIds.length === 0) {
        throw new Error('No restaurant data available. Add menu URLs or discover restaurants first.')
      }

      setAgentRunStage('reasoning')
      addAgentActivity('Reasoning over masked team profile and menu context')
      const decision = await api.post<AgentDecisionResponse>('/decision/agent-decision', {
        teamId,
        restaurantIds,
        userQuestion: currentPromptQuestion,
      })
      setAgentResult(decision)
      setChoiceConfirmation(null)
      setAgentRunStage('done')
      addAgentActivity('Decision completed')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to complete agent run'
      setAgentError(message)
      setAgentRunStage('error')
      addAgentActivity('Run failed', message)
    } finally {
      setAgentAutoRunning(false)
    }
  }

  const handleConfirmChoice = async ({
    key,
    restaurantName,
    restaurantUrl,
    recommendedDish,
    rationaleMd,
    source,
  }: {
    key: string
    restaurantName: string
    restaurantUrl?: string | null
    recommendedDish?: string | null
    rationaleMd?: string | null
    source: string
  }) => {
    if (!api) return

    try {
      setConfirmingChoiceKey(key)
      setAgentError(null)
      setChoiceConfirmation(null)
      const result = await api.post<ConfirmDecisionChoiceResponse>('/decision/confirm-choice', {
        teamId,
        restaurantName,
        restaurantUrl,
        recommendedDish,
        rationaleMd,
        source,
      } satisfies ConfirmDecisionChoiceRequest)
      setChoiceConfirmation(result.message)
    } catch (err) {
      setAgentError(err instanceof Error ? err.message : 'Failed to lock in the team decision')
    } finally {
      setConfirmingChoiceKey(null)
    }
  }

  if (!user) {
    return (
      <div className="text-center py-8">
        <p>Please log in to make team decisions.</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="text-center py-8">
        <p>Loading team details...</p>
      </div>
    )
  }

  if (error && !team) {
    return (
      <div className="text-center py-8">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
        <Link href="/teams" className="text-blue-600 hover:text-blue-800 underline">
          Back to Teams
        </Link>
      </div>
    )
  }

  if (!team) {
    return (
      <div className="text-center py-8">
        <p>Team not found</p>
        <Link href="/teams" className="text-blue-600 hover:text-blue-800 underline">
          Back to Teams
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">
          Team Decision: {team.name}
        </h1>
        <p className="text-slate-600">
          Make a collaborative lunch decision for your team. Individual preferences remain private.
        </p>
      </div>

      <Card className="border-slate-200 bg-slate-50">
        <CardHeader>
          <CardTitle className="text-slate-900">Team Overview</CardTitle>
          <CardDescription className="text-slate-600">
            Base context, participants, and privacy in one compact summary.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Team Base Context</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <BaseStatusBadge hasBase={hasTeamBase} />
                {team.location && <span className="text-sm text-slate-700">{team.location}</span>}
              </div>
              {!hasDistanceReadyBase && (
                <p className="mt-2 text-sm text-amber-800">
                  Save a resolvable team base to unlock consistent distance context in ranking.
                </p>
              )}
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">
                Decision Participants ({team.members.length})
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {team.members.map((member) => (
                  <span
                    key={member.id}
                    className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700"
                  >
                    {member.displayName || 'Anonymous'}
                    {member.userId === user.id && ' (You)'}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <PrivacyCallout />
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)] xl:items-start">
      {/* Restaurant Management & Available Data */}
      <Card className="self-start border-green-200 bg-green-50">
        <CardHeader>
          <CardTitle className="text-green-900">Restaurant Data Setup</CardTitle>
          <CardDescription className="text-green-800">Refresh menu sources and keep recommendation context ready.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {/* Add New Restaurants Section */}
          <div className="order-3 space-y-4 border-t border-green-300 pt-6">
            <button
              type="button"
              onClick={() => setIsAddRefreshOpen((prev) => !prev)}
              className="flex w-full items-start justify-between gap-3 rounded-lg border border-green-200 bg-white px-4 py-3 text-left"
            >
              <div>
                <h3 className="text-lg font-medium text-green-900">Add or Refresh Restaurants</h3>
                <p className="text-sm text-green-700">Enter restaurant URLs to fetch current menu context.</p>
              </div>
              {isAddRefreshOpen ? (
                <ChevronUp className="mt-1 h-4 w-4 text-green-700" />
              ) : (
                <ChevronDown className="mt-1 h-4 w-4 text-green-700" />
              )}
            </button>

            {isAddRefreshOpen && (
              <>
            <div className="space-y-3">
              {restaurants.map((restaurant, index) => (
                <div key={index} className="grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]">
                  <input
                    type="text"
                    value={restaurant.name || ''}
                    onChange={(e) => updateRestaurant(index, 'name', e.target.value)}
                    placeholder="Restaurant name (optional)"
                    className="px-3 py-2 border border-green-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 bg-white"
                  />
                  <input
                    type="url"
                    value={restaurant.url}
                    onChange={(e) => updateRestaurant(index, 'url', e.target.value)}
                    placeholder="https://restaurant-menu-url.com"
                    className="px-3 py-2 border border-green-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 bg-white"
                  />
                  {restaurants.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeRestaurantField(index)}
                      className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-md transition-colors"
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={addRestaurantField}
                className="text-green-700 hover:text-green-900 text-sm font-medium underline"
              >
                + Add another restaurant
              </button>
            </div>

            {processError && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                {processError}
              </div>
            )}

            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-green-700">
                <input
                  type="checkbox"
                  checked={forceRescrape}
                  onChange={(e) => setForceRescrape(e.target.checked)}
                  className="rounded border-green-300 text-green-600 focus:ring-green-500"
                />
                Force re-scrape (ignore cache)
              </label>
            </div>

            <Button 
              onClick={handleProcessInformation} 
              disabled={processing || restaurants.filter((restaurant) => restaurant.url.trim()).length === 0} 
              className="rounded-2xl bg-green-600 hover:bg-green-700"
            >
              {processing ? 'Refreshing data...' : 'Refresh Menu Data'}
            </Button>

            {processing && (
              <div className="bg-white border border-green-200 rounded-lg p-6">
                <LoadingSpinner message="Scraping restaurant menus..." size="md" />
              </div>
            )}

            {processResult && !processing && (
              <div className="space-y-3">
                <div className="bg-green-100 border border-green-300 text-green-800 px-4 py-3 rounded">
                  Successfully processed {processResult.processedCount} restaurant(s). 
                  {processResult.createdCount > 0 && ` Created ${processResult.createdCount} new restaurant(s).`}
                  <br />
                  {processResult.scrapedCount || 0} scraped, {processResult.cachedCount || 0} cached
                </div>
                
                {processResult.processingDetails && processResult.processingDetails.length > 0 && (
                  <div className="bg-white border border-green-200 rounded p-3">
                    <h4 className="text-sm font-medium text-slate-700 mb-2">Processing Details:</h4>
                    <div className="space-y-2">
                      {processResult.processingDetails.map((detail, index) => (
                        <div key={index} className="flex items-start gap-2 text-sm">
                          <span className={`inline-block w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                            detail.action === 'scraped' ? 'bg-blue-500' :
                            detail.action === 'cached' ? 'bg-green-500' : 'bg-red-500'
                          }`}></span>
                          <div className="flex-1">
                            <div className="font-medium text-slate-800">
                              {(() => {
                                try {
                                  return new URL(detail.url).hostname
                                } catch {
                                  return detail.url
                                }
                              })()}
                              {detail.menuType && (
                                <span className={`ml-2 px-2 py-0.5 text-xs rounded-full ${
                                  detail.menuType === 'weekly' ? 'bg-blue-100 text-blue-700' :
                                  detail.menuType === 'daily' ? 'bg-orange-100 text-orange-700' :
                                  'bg-gray-100 text-gray-700'
                                }`}>
                                  {detail.menuType}
                                </span>
                              )}
                            </div>
                            <div className="text-slate-600">{detail.reason}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {processResult.processingDetails && processResult.processingDetails.some(d => d.action === 'cached' && d.reason.includes('days old')) && (
                  <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded">
                    Some restaurants are using cached data. Consider re-processing if you need the latest menus.
                  </div>
                )}
              </div>
            )}
              </>
            )}
          </div>

          <div className="order-1 space-y-4">
            <div>
              <h3 className="text-lg font-medium text-green-900">Nearby Discovery</h3>
              <p className="text-sm text-green-700">
                Find candidate restaurants near {team.location || 'the team location'} and rank them by compatibility.
              </p>
            </div>

            <TeamRestaurantMap
              teamBase={
                typeof team.locationLat === 'number' && typeof team.locationLng === 'number'
                  ? {
                      id: team.id,
                      name: team.location || team.name,
                      lat: team.locationLat,
                      lng: team.locationLng,
                    }
                  : null
              }
              restaurants={mapRestaurants}
              selectedRestaurantId={selectedMapRestaurantId}
              onSelectRestaurant={handleSelectMapRestaurant}
              radiusMeters={discoveryResult ? DISCOVERY_RADIUS_METERS : undefined}
              mapHeightClassName="h-[340px]"
              emptyMessage="Run discovery or enrich restaurant data to populate this map."
            />

            {team.locationLat == null || team.locationLng == null ? (
              <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded">
                Add a team location first to use discovery.
              </div>
            ) : null}

            {discoveryError && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                {discoveryError}
              </div>
            )}

            <Button
              onClick={handleDiscoverRestaurants}
              disabled={discoveryLoading || team.locationLat == null || team.locationLng == null}
              className="rounded-2xl bg-emerald-600 hover:bg-emerald-700"
            >
              <Compass className="h-4 w-4 mr-2" />
              {discoveryLoading ? 'Discovering Restaurants...' : 'Discover Restaurants'}
            </Button>

            {discoveryLoading && (
              <div className="bg-white border border-green-200 rounded-lg p-6">
                <LoadingSpinner message="Finding nearby restaurants and checking today's menu..." size="md" />
              </div>
            )}

            {discoveryResult && !discoveryLoading && (
              <div className="space-y-3">
                <div className="bg-emerald-100 border border-emerald-300 text-emerald-800 px-4 py-3 rounded">
                  Found {discoveryResult.results.length} ranked restaurants from {discoveryResult.candidateCount} nearby candidates.
                </div>
                <div className="text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded px-3 py-2">
                  Shortlist {selectedDiscoveryUrls.size} restaurant(s). Agent session uses your shortlist for ingest.
                </div>

                <div className="space-y-3">
                  {discoveryResult.results.map((restaurant, index) => (
                    <div
                      key={`${restaurant.displayName}-${restaurant.formattedAddress}-${index}`}
                      id={`restaurant-card-${getDiscoveredMapCardId(restaurant, index)}`}
                      onMouseEnter={() => setSelectedMapRestaurantId(getDiscoveredMapCardId(restaurant, index))}
                      className={`rounded-lg border bg-white p-4 space-y-3 transition-colors ${
                        selectedMapRestaurantId === getDiscoveredMapCardId(restaurant, index)
                          ? 'border-emerald-400'
                          : 'border-green-200'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="font-medium text-green-900">
                            {index + 1}. {restaurant.websiteUri ? (
                              <a
                                href={restaurant.websiteUri}
                                target="_blank"
                                rel="noreferrer"
                                className="text-green-900 hover:text-green-700 underline"
                              >
                                {restaurant.displayName}
                              </a>
                            ) : (
                              restaurant.displayName
                            )}
                          </div>
                          <div className="text-sm text-slate-600">
                            {restaurant.formattedAddress}
                          </div>
                        </div>
                        <div className="text-right space-y-1">
                          <div className="text-lg font-semibold text-emerald-700">
                            {restaurant.compatibilityScore.toFixed(1)}
                          </div>
                          <div className="text-xs text-slate-500">compatibility</div>
                          {getDiscoveryRestaurantUrl(restaurant) ? (
                            <label className="inline-flex items-center gap-1 text-xs text-slate-700">
                              <input
                                type="checkbox"
                                checked={selectedDiscoveryUrls.has(getDiscoveryRestaurantUrl(restaurant) as string)}
                                onChange={() => toggleDiscoverySelection(restaurant)}
                              />
                              shortlist
                            </label>
                          ) : (
                            <div className="text-xs text-amber-700">No URL to ingest</div>
                          )}
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-2 text-xs">
                        {restaurant.primaryType && (
                          <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">{restaurant.primaryType}</span>
                        )}
                        {restaurant.straightLineDistanceKm !== undefined && restaurant.straightLineDistanceKm !== null && (
                          <span className="rounded-full bg-blue-100 px-2 py-1 text-blue-700">
                            {restaurant.straightLineDistanceKm.toFixed(2)} km
                          </span>
                        )}
                        {restaurant.rating !== undefined && restaurant.rating !== null && (
                          <span className="rounded-full bg-amber-100 px-2 py-1 text-amber-700">
                            Rating {restaurant.rating.toFixed(1)}
                          </span>
                        )}
                        {restaurant.priceLevel && (
                          <span className="rounded-full bg-rose-100 px-2 py-1 text-rose-700">
                            {restaurant.priceLevel}
                          </span>
                        )}
                        {restaurant.researchResultType && (
                          <span className={`rounded-full px-2 py-1 ${restaurant.researchResultType === 'menu' ? 'bg-emerald-100 text-emerald-700' : 'bg-violet-100 text-violet-700'}`}>
                            {restaurant.researchResultType}
                          </span>
                        )}
                      </div>

                      <div className="space-y-1">
                        {Object.entries(restaurant.scoreBreakdown || {}).map(([metric, value]) => (
                          <div key={metric} className="grid grid-cols-[130px_1fr_auto] items-center gap-2 text-xs">
                            <span className="text-slate-600">{prettifyPreferenceToken(metric)}</span>
                            <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                              <div
                                className="h-full bg-emerald-500"
                                style={{ width: `${scoreWeight(value)}%` }}
                              />
                            </div>
                            <span className="font-medium text-slate-700">{value.toFixed(1)}</span>
                          </div>
                        ))}
                      </div>

                      {restaurant.menuSummary && (
                        <p className="text-sm text-slate-700">{restaurant.menuSummary}</p>
                      )}

                      {restaurant.menuItems.length > 0 && (
                        <div>
                          <div className="text-xs font-medium uppercase tracking-wide text-slate-500 mb-1">Menu evidence</div>
                          <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1">
                            {restaurant.menuItems.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {(restaurant.cuisineTags.length > 0 || restaurant.dietarySignals.length > 0) && (
                        <div className="space-y-2">
                          {restaurant.cuisineTags.length > 0 && (
                            <div className="flex flex-wrap gap-2">
                              {restaurant.cuisineTags.map((tag) => (
                                <span key={tag} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                          {restaurant.dietarySignals.length > 0 && (
                            <div className="flex flex-wrap gap-2">
                              {restaurant.dietarySignals.map((tag) => (
                                <span key={tag} className="rounded-full bg-lime-100 px-2 py-1 text-xs text-lime-700">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {restaurant.recommendationReasons.length > 0 && (
                        <ul className="list-disc pl-5 text-sm text-slate-600 space-y-1">
                          {restaurant.recommendationReasons.map((reason) => (
                            <li key={reason}>{reason}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Existing Restaurants List */}
          {existingRestaurants && existingRestaurants.restaurants.length > 0 && (
            <div className="order-2 space-y-4 pt-6 border-t border-green-300">
              <button
                type="button"
                onClick={() => setIsExistingDataOpen((prev) => !prev)}
                className="flex w-full items-start justify-between gap-3 rounded-lg border border-green-200 bg-white px-4 py-3 text-left"
              >
                <div>
                  <h3 className="text-lg font-medium text-green-900">
                    Available Restaurant Data ({existingRestaurants.totalCount})
                  </h3>
                  <p className="text-sm text-green-700">Previously processed restaurants ready for decision making</p>
                </div>
                {isExistingDataOpen ? (
                  <ChevronUp className="mt-1 h-4 w-4 text-green-700" />
                ) : (
                  <ChevronDown className="mt-1 h-4 w-4 text-green-700" />
                )}
              </button>

              {isExistingDataOpen && (
                <>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs uppercase tracking-wide text-slate-500">Sort</span>
                {(['default', 'nearest', 'freshest'] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setRestaurantSort(mode)}
                    className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                      restaurantSort === mode
                        ? 'border-slate-900 bg-slate-900 text-white'
                        : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    {mode === 'default' ? 'Most relevant' : mode === 'nearest' ? 'Nearest' : 'Freshest'}
                  </button>
                ))}
              </div>
               
              <div className="space-y-2">
                {sortedRestaurants.map((restaurant) => (
                  <div key={restaurant.id} className="space-y-2">
                    <div
                      id={`restaurant-card-${getExistingMapCardId(restaurant.id)}`}
                      onMouseEnter={() => setSelectedMapRestaurantId(getExistingMapCardId(restaurant.id))}
                      className={`flex items-center justify-between p-3 bg-white rounded-lg border transition-colors ${
                        selectedMapRestaurantId === getExistingMapCardId(restaurant.id)
                          ? 'border-emerald-400'
                          : 'border-green-200'
                      }`}
                    >
                      <div className="flex-1">
                        <div className="font-medium text-green-900">
                          {restaurant.displayName || (() => {
                            try {
                              return new URL(restaurant.url).hostname
                            } catch {
                              return restaurant.url
                            }
                          })()}
                          {restaurant.menuType && (
                            <span className={`ml-2 px-2 py-0.5 text-xs rounded-full ${
                              restaurant.menuType === 'weekly' ? 'bg-blue-100 text-blue-700' :
                              restaurant.menuType === 'daily' ? 'bg-orange-100 text-orange-700' :
                              'bg-gray-100 text-gray-700'
                            }`}>
                              {restaurant.menuType}
                            </span>
                          )}
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <FreshnessBadge contentAgeDays={restaurant.contentAgeDays} hasContent={restaurant.hasContent} />
                          <DistanceBadge distanceKm={restaurant.straightLineDistanceKm} />
                        </div>
                        {restaurant.formattedAddress && (
                          <div className="text-sm text-slate-600 mt-1">
                            {restaurant.formattedAddress}
                          </div>
                        )}
                      </div>
                      <div className="flex gap-2 ml-3">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRescrapeRestaurant({
                            id: restaurant.id,
                            url: restaurant.url,
                            displayName: restaurant.displayName,
                          })}
                          disabled={rescrapingIds.has(restaurant.id)}
                          className="flex items-center gap-1"
                        >
                          <RefreshCw className={`h-3 w-3 ${rescrapingIds.has(restaurant.id) ? 'animate-spin' : ''}`} />
                          {rescrapingIds.has(restaurant.id) ? 'Refreshing...' : 'Refresh'}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDeleteRestaurant(restaurant.id)}
                          disabled={deletingIds.has(restaurant.id)}
                          className="flex items-center gap-1 text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="h-3 w-3" />
                          {deletingIds.has(restaurant.id) ? 'Deleting...' : 'Remove'}
                        </Button>
                      </div>
                    </div>
                    <div className="mt-2">
                      <button
                        onClick={() => toggleContentExpanded(restaurant.id)}
                        className="flex items-center gap-2 w-full p-3 bg-slate-50 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors text-left"
                      >
                        <span className="text-sm font-medium text-slate-700">Extracted Menu View</span>
                        {expandedContent[restaurant.id] ? (
                          <ChevronUp className="h-4 w-4 text-slate-500 ml-auto" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-slate-500 ml-auto" />
                        )}
                      </button>
                      {expandedContent[restaurant.id] && (
                        <div className="mt-2 p-3 bg-slate-50 rounded-lg border border-slate-200">
                          {viewingContent[restaurant.id] ? (
                            <div className="space-y-3">
                              <div className="flex flex-wrap gap-2 text-xs">
                                {viewingContent[restaurant.id]?.meta?.menu_type && (
                                  <span className="rounded-full bg-slate-200 px-2 py-1 text-slate-700">
                                    Type: {viewingContent[restaurant.id]?.meta?.menu_type}
                                  </span>
                                )}
                                {Array.isArray(viewingContent[restaurant.id]?.meta?.detected_days) &&
                                  viewingContent[restaurant.id]?.meta?.detected_days?.map((day: string) => (
                                    <span key={day} className="rounded-full bg-blue-100 px-2 py-1 text-blue-700">
                                      {day}
                                    </span>
                                  ))}
                              </div>
                              <pre className="whitespace-pre-wrap break-words text-xs text-slate-600 max-h-96 overflow-y-auto">
                                {viewingContent[restaurant.id]?.contentMd || 'No extracted menu available'}
                              </pre>
                            </div>
                          ) : restaurant.hasContent ? (
                            <p className="text-xs text-slate-500 italic">Loading extracted menu...</p>
                          ) : (
                            <p className="text-xs text-red-500 italic">No extracted menu yet. Please process this restaurant.</p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              
              {existingRestaurants.restaurants.filter(r => r.hasContent).length > 0 && (
                <div className="p-3 bg-green-100 rounded-lg">
                  <p className="text-sm text-green-800">
                    You can make AI decisions using these {existingRestaurants.restaurants.filter(r => r.hasContent).length} restaurant(s) without re-processing.
                  </p>
                </div>
              )}
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* AI Decision */}
      <Card className="self-start border-purple-200 bg-purple-50 xl:sticky xl:top-6 xl:max-h-[calc(100vh-3rem)] xl:flex xl:flex-col xl:overflow-hidden">
        <CardHeader>
          <CardTitle className="text-purple-900">Decision Recommendation</CardTitle>
          <CardDescription className="text-purple-800">Get a ranked recommendation based on masked team preferences and available restaurant data.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 xl:min-h-0 xl:overflow-y-auto">
          <p className="text-sm text-purple-700">
            Use the processed restaurant data to get an AI recommendation for today ({new Date().toLocaleDateString('en-US', { weekday: 'long' })})
          </p>
          <div className="rounded-md border border-purple-200 bg-white px-3 py-2 text-sm text-purple-800">
            Agent status: <span className="font-semibold">{agentStageLabel}</span>
          </div>
          <div className="bg-blue-50 border border-blue-200 text-blue-700 px-3 py-2 rounded text-xs">
            The AI considers current day context when selecting from weekly menus.
          </div>
          <div className="bg-slate-50 border border-slate-200 text-slate-700 px-3 py-2 rounded text-xs">
            {hasDistanceReadyBase
              ? 'Distance is used as a soft tie-breaker, not a hard filter.'
              : 'Set a resolvable team base for stronger distance-aware tie-breaks.'}
          </div>

          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-purple-700">Agent Prompt Style</p>
            <div className="flex flex-wrap gap-2">
              {PROMPT_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => setSelectedPresetId(preset.id)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium ${
                    selectedPresetId === preset.id
                      ? 'border-purple-700 bg-purple-700 text-white'
                      : 'border-purple-300 bg-white text-purple-700 hover:bg-purple-50'
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-purple-200 bg-white p-3">
            <p className="text-xs uppercase tracking-wide text-purple-700 mb-2">Agent Activity</p>
            {agentActivities.length === 0 ? (
              <p className="text-sm text-slate-600">No run yet. Start a session to see the reasoning timeline.</p>
            ) : (
              <ul className="space-y-2 text-sm text-slate-700">
                {agentActivities.slice(-8).map((activity) => (
                  <li key={activity.id} className="rounded border border-slate-200 bg-slate-50 px-2 py-1">
                    <span className="font-medium">{activity.title}</span>
                    {activity.detail ? <span className="text-slate-600"> - {activity.detail}</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
          
          {agentError && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {agentError}
            </div>
          )}

          {choiceConfirmation && (
            <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3 rounded">
              {choiceConfirmation}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Button
              onClick={handleRunAgentSession}
              disabled={isAgentBusy || decisionLocked}
              className="rounded-2xl bg-purple-700 hover:bg-purple-800"
            >
              {agentAutoRunning ? 'Running Agent Session...' : 'Run Agent Session'}
            </Button>
            <Button
              onClick={handleMakeAgentDecision}
              disabled={decisionLocked || isAgentBusy || (
                (!processResult || processResult.restaurantIds.length === 0) &&
                (!existingRestaurants || existingRestaurants.restaurants.filter(r => r.hasContent).length === 0)
              )}
              className="rounded-2xl bg-purple-600 hover:bg-purple-700"
            >
              {agentDeciding ? 'Making Decision...' : 'Decision Only (Use Existing Data)'}
            </Button>
          </div>

          {isAgentBusy && (
            <div className="bg-white border border-purple-200 rounded-lg p-6">
              <LoadingSpinner message="Agent session is running across discovery, menu ingest, and reasoning..." size="md" />
            </div>
          )}

          {agentResult && !agentDeciding && (
            <Card className="mt-4 border-purple-200">
              <CardHeader>
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <CardTitle className="text-purple-900">Agent Recommendation</CardTitle>
                    <CardDescription>AI-selected restaurant and dish</CardDescription>
                  </div>
                  {agentResult.topCandidates.length >= 2 && (
                    <div className="flex flex-col items-start gap-2">
                      <Button
                        onClick={handleStartTieBreak}
                        disabled={tieBreakRunning || decisionLocked}
                        className="rounded-2xl bg-violet-600 hover:bg-violet-700"
                      >
                        {tieBreakRunning ? 'Running Tie-Break...' : 'Start Tie-Break'}
                      </Button>
                      <span className="text-xs text-violet-800">
                        {tieBreakPrefetching
                          ? 'Warming up the deliberation in the background...'
                          : agentResult.tieBreakTranscript.length > 0
                            ? 'Tie-Break is ready to play.'
                            : 'Starts a short deliberation round between the strongest finalists.'}
                      </span>
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {tieBreakActivated && (agentResult.tieBreakAvailable || agentResult.tieBreakMode === 'explicit') && agentResult.tieBreakTranscript.length > 0 && (
                  <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-violet-900">Tie-Break Theater</div>
                        <div className="text-xs text-violet-700">
                          Simulated team deliberation based on current context and fairness memory.
                        </div>
                      </div>
                      {visibleTieBreakTurns < agentResult.tieBreakTranscript.length && (
                        <div className="flex items-center gap-1 rounded-full bg-white px-3 py-1 text-xs text-violet-700 shadow-sm">
                          <span className="h-1.5 w-1.5 rounded-full bg-violet-500 animate-bounce [animation-delay:-0.2s]" />
                          <span className="h-1.5 w-1.5 rounded-full bg-violet-500 animate-bounce [animation-delay:-0.1s]" />
                          <span className="h-1.5 w-1.5 rounded-full bg-violet-500 animate-bounce" />
                        </div>
                      )}
                    </div>

                    <div className="space-y-3">
                      {agentResult.tieBreakTranscript.slice(0, visibleTieBreakTurns).map((turn, index) => {
                        const style = tieBreakSpeakerStyles[turn.speakerLabel] || tieBreakSpeakerStyles['Moderator'] || {
                          align: 'justify-start',
                          bubble: 'bg-white border-violet-100 text-slate-900',
                          badge: 'bg-violet-200 text-violet-900',
                          meta: 'text-violet-700',
                        }
                        const isModerator = turn.speakerLabel.toLowerCase() === 'moderator'
                        return (
                          <div key={`${turn.speakerLabel}-${turn.roundIndex}-${index}`} className={`flex ${style.align}`}>
                            <div className={`max-w-[85%] rounded-2xl border p-3 shadow-sm ${style.bubble}`}>
                              <div className="flex items-center justify-between gap-3">
                                <div className={`rounded-full px-2.5 py-1 text-xs font-semibold ${style.badge}`}>
                                  {turn.speakerLabel}
                                </div>
                                <div className={`text-[11px] uppercase tracking-wide ${style.meta}`}>
                                  {isModerator ? 'final call' : `round ${turn.roundIndex}`}
                                </div>
                              </div>
                              <p className="text-sm mt-2 leading-relaxed">{turn.utterance}</p>
                            </div>
                          </div>
                        )
                      })}
                      {visibleTieBreakTurns < agentResult.tieBreakTranscript.length && (
                        <div className="flex justify-start">
                          <div className="rounded-2xl border border-violet-100 bg-white px-4 py-3 shadow-sm">
                            <div className="flex items-center gap-1">
                              <span className="h-2 w-2 rounded-full bg-violet-400 animate-bounce [animation-delay:-0.2s]" />
                              <span className="h-2 w-2 rounded-full bg-violet-400 animate-bounce [animation-delay:-0.1s]" />
                              <span className="h-2 w-2 rounded-full bg-violet-400 animate-bounce" />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {agentResult.topCandidates.length > 0 && (
                  <div className="space-y-3">
                    <div className="text-sm font-medium text-slate-700">Top 3 Candidates</div>
                    <div className="grid gap-3">
                      {agentResult.topCandidates.map((candidate) => (
                        <div key={`${candidate.rank}-${candidate.restaurantName}`} className="rounded-lg border border-purple-100 bg-purple-50/60 p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="font-medium text-purple-900">
                                {candidate.rank}. {candidate.restaurantUrl ? (
                                  <a
                                    href={candidate.restaurantUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-purple-900 hover:text-purple-700 underline"
                                  >
                                    {candidate.restaurantName}
                                  </a>
                                ) : (
                                  candidate.restaurantName
                                )}
                              </div>
                              {candidate.recommendedDish && (
                                <div className="text-sm text-slate-700 mt-1">
                                  Dish: {candidate.recommendedDish}
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="text-sm text-slate-700 mt-2">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {candidate.rationaleMd}
                            </ReactMarkdown>
                          </div>
                          <div className="mt-3">
                            <Button
                              className="rounded-2xl w-full md:w-auto"
                              disabled={decisionLocked || confirmingChoiceKey === `candidate-${candidate.rank}`}
                              onClick={() =>
                                handleConfirmChoice({
                                  key: `candidate-${candidate.rank}`,
                                  restaurantName: candidate.restaurantName,
                                  restaurantUrl: candidate.restaurantUrl,
                                  recommendedDish: candidate.recommendedDish,
                                  rationaleMd: candidate.rationaleMd,
                                  source: 'top_candidate_choice',
                                })
                              }
                            >
                              {confirmingChoiceKey === `candidate-${candidate.rank}` ? 'Locking it in...' : "Let's Go!"}
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {agentResult.fairnessSummary && (
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 space-y-1">
                    <div className="text-sm font-medium text-emerald-900">Fairness Memory</div>
                    <div className="text-sm text-emerald-800">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {agentResult.fairnessSummary.summaryMd}
                      </ReactMarkdown>
                    </div>
                    {agentResult.fairnessSummary.balanceNote && (
                      <div className="text-xs text-emerald-700">
                        {agentResult.fairnessSummary.balanceNote}
                      </div>
                    )}
                  </div>
                )}

                <div>
                  <span className="font-medium">Restaurant:</span>{' '}
                  {agentResult.recommendationRestaurantUrl ? (
                    <a
                      href={agentResult.recommendationRestaurantUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue-600 hover:text-blue-800 underline"
                    >
                      {agentResult.recommendationRestaurantName}
                    </a>
                  ) : (
                    <span>{agentResult.recommendationRestaurantName}</span>
                  )}
                </div>
                <div>
                  <span className="font-medium">Dish:</span> {agentResult.recommendedDish}
                </div>
                <Accordion type="single" collapsible className="w-full">
                  <AccordionItem value="explanation">
                    <AccordionTrigger>See explanation</AccordionTrigger>
                    <AccordionContent>
                      <div className="text-slate-700 text-sm space-y-3">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {agentResult.explanationMd}
                        </ReactMarkdown>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
                <details className="mt-2">
                  <summary className="cursor-pointer text-sm text-slate-600">Raw agent text</summary>
                  <pre className="whitespace-pre-wrap break-words text-sm text-slate-700">{agentResult.rawText}</pre>
                </details>
                <div className="pt-2">
                  <Button
                    className="rounded-2xl w-full md:w-auto"
                    disabled={decisionLocked || confirmingChoiceKey === 'final-recommendation'}
                    onClick={() =>
                      handleConfirmChoice({
                        key: 'final-recommendation',
                        restaurantName: agentResult.recommendationRestaurantName,
                        restaurantUrl: agentResult.recommendationRestaurantUrl,
                        recommendedDish: agentResult.recommendedDish,
                        rationaleMd: agentResult.explanationMd,
                        source: agentResult.tieBreakMode === 'explicit' ? 'tie_break_winner' : 'agent_recommendation',
                      })
                    }
                  >
                    {confirmingChoiceKey === 'final-recommendation' ? 'Locking it in...' : "Let's Go!"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="flex gap-2 mt-4">
            <Button onClick={resetAgent} className="rounded-2xl">Reset</Button>
            <Link href={`/teams/${teamId}`}>
              <Button variant="secondary" className="rounded-2xl">Back to Team</Button>
            </Link>
          </div>
        </CardContent>
      </Card>
      </div>

    </div>
  )
}
