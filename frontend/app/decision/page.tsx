'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '../../lib/auth-context'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card'
import { Button } from '../../components/ui/button'
import { DecisionRun, Team } from '../../lib/types'
import { Sparkles, Users, Plus, ArrowRight } from 'lucide-react'

function extractRestaurantName(decision: DecisionRun): string {
  const name = decision.result?.recommendationRestaurantName
  const url = decision.result?.recommendationRestaurantUrl
  
  // If name exists and is not empty, use it
  if (name && name.trim() !== '') return name
  
  // Extract from URL
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

export default function DecisionPage() {
  const { api } = useAuth()
  const [decisions, setDecisions] = useState<DecisionRun[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [loading, setLoading] = useState(true)
  const [teamsLoading, setTeamsLoading] = useState(true)

  useEffect(() => {
    async function fetchDecisions() {
      try {
        const data = await api.get<DecisionRun[]>('/decision/history?limit=20')
        setDecisions(data)
      } catch (error) {
        console.error('Failed to fetch decisions:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchDecisions()
  }, [api])

  useEffect(() => {
    async function fetchTeams() {
      try {
        const data = await api.get<Team[]>('/teams/')
        setTeams(data)
      } catch (error) {
        console.error('Failed to fetch teams:', error)
      } finally {
        setTeamsLoading(false)
      }
    }
    fetchTeams()
  }, [api])

  return (
    <main className="max-w-5xl mx-auto space-y-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">Decisions</h1>
        <p className="text-slate-600">
          View past decisions and make new ones for your teams
        </p>
      </div>

      {/* Make New Decision Section */}
      <Card className="border-purple-200 bg-purple-50">
        <CardHeader>
          <CardTitle className="text-purple-900">Make a New Decision</CardTitle>
          <CardDescription className="text-purple-800">Select a team to start the AI decision process</CardDescription>
        </CardHeader>
        <CardContent>
          {teamsLoading ? (
            <p className="text-sm text-purple-700">Loading teams...</p>
          ) : teams.length > 0 ? (
            <div className="space-y-3">
              {teams.map((team) => (
                <Link key={team.id} href={`/teams/${team.id}/decision`}>
                  <div className="flex items-center justify-between p-4 rounded-lg border border-purple-200 bg-white hover:border-purple-400 hover:bg-purple-50 transition-all cursor-pointer">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                        <Users className="h-5 w-5 text-purple-600" />
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
            <div className="text-center py-6">
              <p className="text-sm text-purple-700 mb-3">You haven't joined any teams yet.</p>
              <Link href="/teams">
                <Button className="rounded-lg bg-purple-600 hover:bg-purple-700">
                  <Plus className="h-4 w-4 mr-2" />
                  Create or Join a Team
                </Button>
              </Link>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Past Decisions Section */}
      <Card>
        <CardHeader>
          <CardTitle>Past Decisions</CardTitle>
          <CardDescription>Your decision history</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-slate-500">Loading decisions...</p>
          ) : decisions.length > 0 ? (
            <div className="space-y-3">
              {decisions.map((decision) => {
                const team = teams.find(t => t.id === decision.teamId)
                const restaurantName = extractRestaurantName(decision)
                const dish = decision.result.recommendedDish || 'View details for more info'
                
                return (
                  <div key={decision.id} className="p-4 rounded-lg border hover:border-purple-300 hover:bg-slate-50 transition-all">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center flex-shrink-0">
                          <Sparkles className="h-5 w-5 text-purple-600" />
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
            <div className="text-center py-6">
              <p className="text-sm text-slate-500 mb-3">No decisions yet. Make your first one!</p>
              <Link href="/teams">
                <Button className="rounded-lg bg-[#3a8aca] hover:bg-[#3a8aca]/90">
                  <Sparkles className="h-4 w-4 mr-2" />
                  Make a Decision
                </Button>
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
