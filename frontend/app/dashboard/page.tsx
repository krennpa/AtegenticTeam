'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '../../lib/auth-context'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card'
import { Button } from '../../components/ui/button'
import { Users, Plus, Sparkles, MapPin } from 'lucide-react'
import { Team, DecisionRun } from '../../lib/types'
import { DashboardPreferencePrompt } from '../../components/forms/DashboardPreferencePrompt'
import { TeamRestaurantMap } from '../../components/maps/TeamRestaurantMap'

function extractRestaurantName(decision: DecisionRun): string {
  const name = decision.result?.recommendationRestaurantName
  const url = decision.result?.recommendationRestaurantUrl

  if (name && name.trim() !== '') return name

  if (url) {
    try {
      const parsed = new URL(url)
      let domain = parsed.hostname
      if (domain.startsWith('www.')) domain = domain.slice(4)
      return domain
    } catch {
      // Ignore malformed URLs and fallback below.
    }
  }

  return 'Restaurant'
}

export default function DashboardPage() {
  const { user, api } = useAuth()
  const router = useRouter()
  const [teams, setTeams] = useState<Team[]>([])
  const [decisions, setDecisions] = useState<DecisionRun[]>([])
  const [loadingTeams, setLoadingTeams] = useState(true)
  const [loadingDecisions, setLoadingDecisions] = useState(true)

  useEffect(() => {
    const fetchTeams = async () => {
      try {
        const data = await api.get<Team[]>('/teams/')
        setTeams(data)
      } catch (error) {
        console.error('Failed to fetch teams:', error)
      } finally {
        setLoadingTeams(false)
      }
    }

    void fetchTeams()
  }, [api])

  const dashboardMapPoints = useMemo(
    () =>
      teams
        .filter((team) => typeof team.locationLat === 'number' && typeof team.locationLng === 'number')
        .map((team) => ({
          id: `team-${team.id}`,
          name: team.name,
          lat: team.locationLat as number,
          lng: team.locationLng as number,
          address: team.location,
        })),
    [teams],
  )
  const teamsWithBase = useMemo(
    () => teams.filter((team) => Boolean(team.location && team.location.trim())).length,
    [teams],
  )

  useEffect(() => {
    const fetchDecisions = async () => {
      try {
        const data = await api.get<DecisionRun[]>('/decision/history?limit=5')
        setDecisions(data)
      } catch (error) {
        console.error('Failed to fetch decisions:', error)
      } finally {
        setLoadingDecisions(false)
      }
    }

    void fetchDecisions()
  }, [api])

  return (
    <main className="mx-auto max-w-6xl space-y-4">
      <section className="grid gap-4 xl:grid-cols-2">
        <DashboardPreferencePrompt />

        <Card className="xl:min-h-[15rem]">
          <CardHeader className="pb-2">
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle>Welcome{user?.displayName ? `, ${user.displayName}` : ''}</CardTitle>
                <CardDescription>Quick overview for your current lunch coordination.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid gap-2 sm:grid-cols-3">
              <div className="rounded-lg border bg-slate-50 px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">Teams</p>
                <p className="text-lg font-semibold text-slate-900">{loadingTeams ? '...' : teams.length}</p>
              </div>
              <div className="rounded-lg border bg-slate-50 px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">With Base</p>
                <p className="text-lg font-semibold text-slate-900">{loadingTeams ? '...' : teamsWithBase}</p>
              </div>
              <div className="rounded-lg border bg-slate-50 px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">Recent Decisions</p>
                <p className="text-lg font-semibold text-slate-900">{loadingDecisions ? '...' : decisions.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <Card className="xl:min-h-[24rem]">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle>Team Bases Map</CardTitle>
                <CardDescription>Open teams directly from the map and keep location context in one place.</CardDescription>
              </div>
              <Link href="/teams">
                <Button size="sm" className="rounded-lg bg-[#3a8aca] hover:bg-[#3a8aca]/90">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Team
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <TeamRestaurantMap
              restaurants={dashboardMapPoints}
              mapHeightClassName="h-[320px]"
              emptyMessage="No teams have map-ready coordinates yet. Add a specific location to a team base first."
              onSelectRestaurant={(id) => {
                const teamId = id.replace('team-', '')
                router.push(`/teams/${teamId}`)
              }}
            />
          </CardContent>
        </Card>

        <Card className="xl:min-h-[24rem]">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Recent Decisions</CardTitle>
                <CardDescription>Your latest lunch choices</CardDescription>
              </div>
              <Link href="/teams">
                <Button size="sm" className="rounded-lg bg-[#63308c] hover:bg-[#63308c]/90">
                  <Plus className="mr-2 h-4 w-4" />
                  Make a Decision
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            {loadingDecisions ? (
              <p className="text-sm text-slate-500">Loading decisions...</p>
            ) : decisions.length > 0 ? (
              <div className="max-h-[18rem] space-y-2 overflow-y-auto pr-1">
                {decisions.map((decision) => {
                  const team = teams.find((entry) => entry.id === decision.teamId)
                  const restaurantName = extractRestaurantName(decision)
                  const dish = decision.result.recommendedDish || 'View details for more info'

                  return (
                    <div
                      key={decision.id}
                      className="rounded-lg border p-3 transition-all hover:border-[#63308c] hover:bg-slate-50"
                    >
                      <div className="flex items-start gap-3">
                        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[#63308c]/10">
                          <Sparkles className="h-4 w-4 text-[#63308c]" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Decision made</span>
                          <h3 className="truncate text-base font-semibold text-slate-900">{restaurantName}</h3>
                          <p className="truncate text-sm text-slate-600">{dish}</p>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            {team && (
                              <span className="flex items-center gap-1 text-xs text-slate-500">
                                <Users className="h-3 w-3" />
                                {team.name}
                              </span>
                            )}
                            {team?.location && (
                              <span className="flex items-center gap-1 text-xs text-slate-500">
                                <MapPin className="h-3 w-3" />
                                {team.location}
                              </span>
                            )}
                            <span className="text-xs text-slate-400">
                              {new Date(decision.createdAt).toLocaleDateString('en-US', {
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No decisions yet. Make your first one.</p>
            )}
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
