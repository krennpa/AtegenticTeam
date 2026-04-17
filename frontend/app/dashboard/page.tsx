'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '../../lib/auth-context'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card'
import { Button } from '../../components/ui/button'
import { Users, ClipboardList, Settings, Plus, ArrowRight, Sparkles } from 'lucide-react'
import { Team, DecisionRun } from '../../lib/types'

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
    } catch { /* ignore */ }
  }
  return 'Restaurant'
}

export default function DashboardPage() {
  const { user, api } = useAuth()
  const [teams, setTeams] = useState<Team[]>([])
  const [decisions, setDecisions] = useState<DecisionRun[]>([])
  const [loading, setLoading] = useState(true)
  const [decisionsLoading, setDecisionsLoading] = useState(true)

  useEffect(() => {
    async function fetchTeams() {
      try {
        const data = await api.get<Team[]>('/teams/')
        setTeams(data)
      } catch (error) {
        console.error('Failed to fetch teams:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchTeams()
  }, [api])

  useEffect(() => {
    async function fetchDecisions() {
      try {
        const data = await api.get<DecisionRun[]>('/decision/history?limit=5')
        console.log('Fetched decisions:', data)
        setDecisions(data)
      } catch (error) {
        console.error('Failed to fetch decisions:', error)
      } finally {
        setDecisionsLoading(false)
      }
    }
    fetchDecisions()
  }, [api])

  return (
    <main className="grid gap-6 md:grid-cols-[240px_1fr]">
      {/* Sidebar */}
      <aside className="rounded-2xl border bg-card">
        <nav className="p-4 space-y-2">
          <Link href="/teams">
            <Button variant="ghost" className="w-full justify-start rounded-2xl">
              <Users className="mr-2 h-4 w-4" /> Teams
            </Button>
          </Link>
          <Link href="/profile">
            <Button variant="ghost" className="w-full justify-start rounded-2xl">
              <Settings className="mr-2 h-4 w-4" /> Profile
            </Button>
          </Link>
          <Link href="/teams/search">
            <Button variant="ghost" className="w-full justify-start rounded-2xl">
              <ClipboardList className="mr-2 h-4 w-4" /> Search Teams
            </Button>
          </Link>
        </nav>
      </aside>

      {/* Main */}
      <section className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Welcome{user?.displayName ? `, ${user.displayName}` : ''} 👋</CardTitle>
            <CardDescription>Quick actions to get you going.</CardDescription>
          </CardHeader>
        </Card>

        {/* Teams Section */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Teams</CardTitle>
                <CardDescription>Your lunch groups</CardDescription>
              </div>
              <Link href="/teams">
                <Button className="rounded-lg bg-[#3a8aca] hover:bg-[#3a8aca]/90">
                  <Plus className="h-4 w-4 mr-2" /> Create Team
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-slate-500">Loading teams...</p>
            ) : teams.length > 0 ? (
              <div className="space-y-3">
                {teams.map((team) => (
                  <Link key={team.id} href={`/teams/${team.id}`}>
                    <div className="flex items-center justify-between p-4 rounded-lg border hover:border-[#3a8aca] hover:bg-slate-50 transition-all cursor-pointer">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-[#3a8aca]/10 flex items-center justify-center">
                          <Users className="h-5 w-5 text-[#3a8aca]" />
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
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">You haven't joined any teams yet.</p>
            )}
          </CardContent>
        </Card>

        {/* Recent Decisions Section */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Recent Decisions</CardTitle>
                <CardDescription>Your latest lunch choices</CardDescription>
              </div>
              <Link href="/teams">
                <Button className="rounded-lg bg-[#63308c] hover:bg-[#63308c]/90">
                  <Plus className="h-4 w-4 mr-2" /> Make a Decision
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {decisionsLoading ? (
              <p className="text-sm text-slate-500">Loading decisions...</p>
            ) : decisions.length > 0 ? (
              <div className="space-y-3">
                {decisions.map((decision) => {
                  const team = teams.find(t => t.id === decision.teamId)
                  const restaurantName = extractRestaurantName(decision)
                  const dish = decision.result.recommendedDish || 'View details for more info'
                  
                  return (
                    <div key={decision.id} className="p-4 rounded-lg border hover:border-[#63308c] hover:bg-slate-50 transition-all">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-3 flex-1 min-w-0">
                          <div className="w-10 h-10 rounded-lg bg-[#63308c]/10 flex items-center justify-center flex-shrink-0">
                            <Sparkles className="h-5 w-5 text-[#63308c]" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Decision made</span>
                            </div>
                            <h3 className="font-semibold text-lg text-slate-900 truncate">
                              🏆 {restaurantName}
                            </h3>
                            <p className="text-sm text-slate-600 truncate">
                              {dish}
                            </p>
                            <div className="flex items-center gap-2 mt-2 flex-wrap">
                              {team && (
                                <span className="text-xs text-slate-500 flex items-center gap-1">
                                  <Users className="h-3 w-3" />
                                  {team.name}
                                </span>
                              )}
                              <span className="text-xs text-slate-400">
                                {new Date(decision.createdAt).toLocaleDateString('en-US', { 
                                  month: 'short', 
                                  day: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit'
                                })}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No decisions yet. Make your first one!</p>
            )}
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
