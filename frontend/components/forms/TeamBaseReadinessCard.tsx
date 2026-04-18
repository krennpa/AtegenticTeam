'use client'

import Link from 'next/link'
import { MapPin } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Team } from '../../lib/types'
import { BaseStatusBadge } from '../ui/base-status-badge'

type TeamBaseReadinessCardProps = {
  teams: Team[]
  loading: boolean
}

function hasTeamBase(team: Team): boolean {
  return Boolean(team.location && team.location.trim())
}

function hasDistanceReadyBase(team: Team): boolean {
  return typeof team.locationLat === 'number' && typeof team.locationLng === 'number'
}

export function TeamBaseReadinessCard({ teams, loading }: TeamBaseReadinessCardProps) {
  const teamsWithBase = teams.filter(hasTeamBase)
  const teamsMissingBase = teams.filter((team) => !hasTeamBase(team))
  const teamsDistanceReady = teams.filter(hasDistanceReadyBase)

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-slate-600" />
          Team Base Readiness
        </CardTitle>
        <CardDescription>
          A team base helps surface distance-aware restaurant context.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {loading ? (
          <p className="text-sm text-slate-500">Loading base status...</p>
        ) : (
          <>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Total Teams</p>
                <p className="text-lg font-semibold text-slate-900">{teams.length}</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Base Set</p>
                <p className="text-lg font-semibold text-slate-900">{teamsWithBase.length}</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Distance Ready</p>
                <p className="text-lg font-semibold text-slate-900">{teamsDistanceReady.length}</p>
              </div>
            </div>

            {teamsMissingBase.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">Teams Missing Base</p>
                <div className="space-y-2">
                  {teamsMissingBase.slice(0, 5).map((team) => (
                    <Link key={team.id} href={`/teams/${team.id}`}>
                      <div className="flex items-center justify-between rounded-lg border border-slate-200 p-2 hover:bg-slate-50">
                        <span className="text-sm text-slate-800">{team.name}</span>
                        <BaseStatusBadge hasBase={false} compact />
                      </div>
                    </Link>
                  ))}
                </div>
                <Link href="/teams" className="text-sm text-blue-600 hover:text-blue-800">
                  Open Teams
                </Link>
              </div>
            ) : (
              <p className="text-sm text-emerald-700">All teams have a base configured.</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
