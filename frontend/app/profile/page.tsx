'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ProfileForm } from '../../components/forms/ProfileForm'
import { PreferenceSummaryCard } from '../../components/forms/PreferenceSummaryCard'
import { useAuth } from '../../lib/auth-context'
import { Team } from '../../lib/types'

export default function ProfilePage() {
  const { logout, api, user } = useAuth()
  const [teams, setTeams] = useState<Team[]>([])
  const [loadingTeams, setLoadingTeams] = useState(true)

  useEffect(() => {
    if (!api || !user) return

    const loadTeams = async () => {
      try {
        setLoadingTeams(true)
        const data = await api.get<Team[]>('/teams/')
        setTeams(data)
      } catch (error) {
        console.error('Failed to load teams:', error)
      } finally {
        setLoadingTeams(false)
      }
    }

    void loadTeams()
  }, [api, user])

  if (!user) {
    return (
      <main className="space-y-6">
        <h1 className="text-xl font-semibold">My Profile</h1>
        <p className="text-slate-600">Please log in to view your profile and preferences.</p>
      </main>
    )
  }

  return (
    <main className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">My Profile</h1>
        <button className="rounded bg-slate-800 px-3 py-1.5 text-white" onClick={logout}>
          Logout
        </button>
      </div>

      <ProfileForm />
      <PreferenceSummaryCard />

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">My Teams</h2>
          <Link href="/teams" className="text-sm text-blue-600 underline hover:text-blue-800">
            Manage Teams
          </Link>
        </div>

        {loadingTeams ? (
          <p className="text-slate-500">Loading teams...</p>
        ) : teams.length === 0 ? (
          <div className="py-4 text-center">
            <p className="mb-2 text-slate-600">You are not a member of any teams yet.</p>
            <Link href="/teams" className="text-blue-600 underline hover:text-blue-800">
              Create or join a team
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {teams.map((team) => (
              <div key={team.id} className="flex items-center justify-between rounded bg-slate-50 p-3">
                <div>
                  <Link href={`/teams/${team.id}`} className="font-medium text-slate-900 hover:text-blue-600">
                    {team.name}
                  </Link>
                  <div className="text-sm text-slate-500">
                    {team.memberCount} member{team.memberCount !== 1 ? 's' : ''}
                    {team.description ? ` - ${team.description}` : ''}
                  </div>
                </div>
                <Link
                  href={`/teams/${team.id}/decision`}
                  className="rounded bg-green-600 px-3 py-1 text-sm text-white transition-colors hover:bg-green-700"
                >
                  Decide
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
