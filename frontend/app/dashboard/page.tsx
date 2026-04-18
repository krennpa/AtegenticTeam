'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '../../lib/auth-context'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card'
import { Button } from '../../components/ui/button'
import { Users, Plus, ArrowRight, Sparkles } from 'lucide-react'
import { Team, DecisionRun } from '../../lib/types'
import { DashboardPreferencePrompt } from '../../components/forms/DashboardPreferencePrompt'

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
      <section className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.35fr)]">
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle>Welcome{user?.displayName ? `, ${user.displayName}` : ''}</CardTitle>
                <CardDescription>Quick actions to keep your team profile up to date.</CardDescription>
              </div>
              <div className="space-y-1 text-right">
                <p className="text-xs uppercase tracking-wide text-slate-400">Overview</p>
                <p className="text-sm text-slate-700">{loadingTeams ? '...' : teams.length} teams</p>
                <p className="text-sm text-slate-700">
                  {loadingDecisions ? '...' : decisions.length} recent decisions
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="flex flex-wrap gap-2">
              <Link href="/teams">
                <Button size="sm" className="rounded-lg bg-[#3a8aca] hover:bg-[#3a8aca]/90">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Team
                </Button>
              </Link>
              <Link href="/preferences">
                <Button size="sm" variant="outline" className="rounded-lg">
                  Keep Preferences Fresh
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        <DashboardPreferencePrompt />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card className="xl:min-h-[24rem]">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Teams</CardTitle>
                <CardDescription>Your lunch groups</CardDescription>
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
            {loadingTeams ? (
              <p className="text-sm text-slate-500">Loading teams...</p>
            ) : teams.length > 0 ? (
              <div className="max-h-[18rem] space-y-2 overflow-y-auto pr-1">
                {teams.map((team) => (
                  <Link key={team.id} href={`/teams/${team.id}`}>
                    <div className="cursor-pointer rounded-lg border p-3 transition-all hover:border-[#3a8aca] hover:bg-slate-50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#3a8aca]/10">
                            <Users className="h-4 w-4 text-[#3a8aca]" />
                          </div>
                          <div>
                            <h3 className="font-medium text-slate-900">{team.name}</h3>
                            <p className="text-sm text-slate-500">
                              {team.memberCount} {team.memberCount === 1 ? 'member' : 'members'}
                            </p>
                          </div>
                        </div>
                        <ArrowRight className="h-4 w-4 text-slate-400" />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">You have not joined any teams yet.</p>
            )}
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
