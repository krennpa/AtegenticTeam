'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../../../lib/auth-context'
import { TeamWithMembers, AgentDecisionResponse, IngestRestaurantInput, IngestRestaurantsResponse, ExistingRestaurantsResponse, RestaurantDocument, DiscoverRestaurantsResponse } from '../../../../lib/types'
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

type RestaurantSort = 'default' | 'nearest' | 'freshest'

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
  
  // Raw content viewing state
  const [viewingContent, setViewingContent] = useState<{[key: string]: RestaurantDocument | null}>({})
  const [expandedContent, setExpandedContent] = useState<{[key: string]: boolean}>({})
  
  // Restaurant action states
  const [rescrapingIds, setRescrapingIds] = useState<Set<string>>(new Set())
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())
  const [restaurantSort, setRestaurantSort] = useState<RestaurantSort>('default')

  useEffect(() => {
    if (api && teamId) {
      loadTeam()
      loadExistingRestaurants()
    }
  }, [api, teamId])

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
    setRestaurants([{ url: '', name: '' }])
  }

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
    if (!api || !team) return

    // Get restaurant IDs from either processed results or existing restaurants
    let restaurantIds: string[] = []
    
    if (processResult && processResult.restaurantIds && processResult.restaurantIds.length > 0) {
      // Use newly processed restaurants
      restaurantIds = processResult.restaurantIds
    } else if (existingRestaurants && existingRestaurants.restaurants.length > 0) {
      // Use existing restaurants that have content
      restaurantIds = existingRestaurants.restaurants
        .filter(r => r.hasContent)
        .map(r => r.id)
    }

    if (restaurantIds.length === 0) {
      setAgentError('No restaurant data available. Please process restaurant information first or ensure existing restaurants have content.')
      return
    }

    try {
      setAgentDeciding(true)
      setAgentError(null)
      setAgentResult(null)

      // Run agent with the restaurant IDs
      const result = await api.post<AgentDecisionResponse>('/decision/agent-decision', {
        teamId: teamId,
        restaurantIds: restaurantIds,
        userQuestion: 'Use your tools to retrieve team needs and the restaurant menu. Recommend one restaurant and one dish.'
      })
      setAgentResult(result)
    } catch (err) {
      setAgentError(err instanceof Error ? err.message : 'Failed to run agent decision')
    } finally {
      setAgentDeciding(false)
    }
  }

  const hasTeamBase = Boolean(team?.location && team.location.trim())
  const hasDistanceReadyBase =
    typeof team?.locationLat === 'number' && typeof team?.locationLng === 'number'

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
        radiusMeters: 1500,
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
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">
          Team Decision: {team.name}
        </h1>
        <p className="text-slate-600">
          Make a collaborative lunch decision for your team. Individual preferences remain private.
        </p>
      </div>

      <Card className={hasDistanceReadyBase ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'}>
        <CardHeader>
          <CardTitle className={hasDistanceReadyBase ? 'text-emerald-900' : 'text-amber-900'}>
            Team Base Context
          </CardTitle>
          <CardDescription className={hasDistanceReadyBase ? 'text-emerald-800' : 'text-amber-800'}>
            Distance is used as a soft tie-breaker when context is available.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <BaseStatusBadge hasBase={hasTeamBase} />
            {team.location && <span className="text-sm text-slate-700">{team.location}</span>}
          </div>
          {!hasDistanceReadyBase && (
            <p className="text-sm text-amber-800">
              Save a resolvable team base to unlock consistent distance context in ranking.
            </p>
          )}
        </CardContent>
      </Card>

      <PrivacyCallout />

      {/* Team Members Summary */}
      <Card className="border-blue-200 bg-blue-50">
        <CardHeader>
          <CardTitle className="text-blue-900">Decision Participants ({team.members.length} members)</CardTitle>
          <CardDescription className="text-blue-800">Individual preferences stay private.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {team.members.map((member) => (
              <span
                key={member.id}
                className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
              >
                {member.displayName || 'Anonymous'}
                {member.userId === user.id && ' (You)'}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Restaurant Management & Available Data */}
      <Card className="border-green-200 bg-green-50">
        <CardHeader>
          <CardTitle className="text-green-900">Restaurant Data Setup</CardTitle>
          <CardDescription className="text-green-800">Refresh menu sources and keep recommendation context ready.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Add New Restaurants Section */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-green-900">Add or Refresh Restaurants</h3>
            <p className="text-sm text-green-700">Enter restaurant URLs to fetch current menu context.</p>
            
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
          </div>

          <div className="space-y-4 pt-6 border-t border-green-300">
            <div>
              <h3 className="text-lg font-medium text-green-900">Nearby Discovery</h3>
              <p className="text-sm text-green-700">
                Find candidate restaurants near {team.location || 'the team location'} and rank them by compatibility.
              </p>
            </div>

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
              {discoveryLoading ? 'Discovering Restaurants…' : 'Discover Restaurants'}
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

                <div className="space-y-3">
                  {discoveryResult.results.map((restaurant, index) => (
                    <div key={`${restaurant.displayName}-${restaurant.formattedAddress}-${index}`} className="rounded-lg border border-green-200 bg-white p-4 space-y-3">
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
                        <div className="text-right">
                          <div className="text-lg font-semibold text-emerald-700">
                            {restaurant.compatibilityScore.toFixed(1)}
                          </div>
                          <div className="text-xs text-slate-500">compatibility</div>
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
            <div className="space-y-4 pt-6 border-t border-green-300">
              <div>
                <h3 className="text-lg font-medium text-green-900">Available Restaurant Data ({existingRestaurants.totalCount})</h3>
                <p className="text-sm text-green-700">Previously processed restaurants ready for decision making</p>
              </div>

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
                    <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-green-200">
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
            </div>
          )}
        </CardContent>
      </Card>

      {/* AI Decision */}
      <Card className="border-purple-200 bg-purple-50">
        <CardHeader>
          <CardTitle className="text-purple-900">Decision Recommendation</CardTitle>
          <CardDescription className="text-purple-800">Get a ranked recommendation based on masked team preferences and available restaurant data.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-purple-700">
            Use the processed restaurant data to get an AI recommendation for today ({new Date().toLocaleDateString('en-US', { weekday: 'long' })})
          </p>
          <div className="bg-blue-50 border border-blue-200 text-blue-700 px-3 py-2 rounded text-xs">
            The AI considers current day context when selecting from weekly menus.
          </div>
          <div className="bg-slate-50 border border-slate-200 text-slate-700 px-3 py-2 rounded text-xs">
            {hasDistanceReadyBase
              ? 'Distance is used as a soft tie-breaker, not a hard filter.'
              : 'Set a resolvable team base for stronger distance-aware tie-breaks.'}
          </div>
          
          {agentError && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {agentError}
            </div>
          )}

          <Button 
            onClick={handleMakeAgentDecision} 
            disabled={agentDeciding || (
              (!processResult || processResult.restaurantIds.length === 0) && 
              (!existingRestaurants || existingRestaurants.restaurants.filter(r => r.hasContent).length === 0)
            )} 
            className="rounded-2xl bg-purple-600 hover:bg-purple-700"
          >
            {agentDeciding ? 'Making Decision...' : 'Make AI Decision'}
          </Button>

          {agentDeciding && (
            <div className="bg-white border border-purple-200 rounded-lg p-6">
              <LoadingSpinner message="AI is analyzing team preferences and menus..." size="md" />
            </div>
          )}

          {agentResult && !agentDeciding && (
            <Card className="mt-4 border-purple-200">
              <CardHeader>
                <CardTitle className="text-purple-900">Agent Recommendation</CardTitle>
                <CardDescription>AI-selected restaurant and dish</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
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
                  {agentResult.recommendationRestaurantUrl ? (
                    <a href={agentResult.recommendationRestaurantUrl} target="_blank" rel="noreferrer">
                      <Button className="rounded-2xl w-full md:w-auto">Let's Go!</Button>
                    </a>
                  ) : (
                    <Button className="rounded-2xl w-full md:w-auto" asChild>
                      <Link href={`/teams/${teamId}`}>Let's Go!</Link>
                    </Button>
                  )}
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
  )
}
