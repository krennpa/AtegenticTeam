'use client'

import { useState, useEffect } from 'react'
import { ProfileForm } from '../../components/forms/ProfileForm'
import { PreferenceGame } from '../../components/forms/PreferenceGame'
import { useAuth } from '../../lib/auth-context'
import { Team } from '../../lib/types'
import Link from 'next/link'

export default function ProfilePage() {
  const { logout, api, user } = useAuth()
  const [teams, setTeams] = useState<Team[]>([])
  const [loadingTeams, setLoadingTeams] = useState(true)

  useEffect(() => {
    if (api && user) {
      loadTeams()
    }
  }, [api, user])

  const loadTeams = async () => {
    try {
      setLoadingTeams(true)
      const data = await api.get<Team[]>('/teams/')
      setTeams(data)
    } catch (err) {
      console.error('Failed to load teams:', err)
    } finally {
      setLoadingTeams(false)
    }
  }

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
        <button className="px-3 py-1.5 rounded bg-slate-800 text-white" onClick={logout}>Logout</button>
      </div>
      
      <ProfileForm />
      <PreferenceGame teams={teams} />
      
      {/* Team Memberships Section */}
      <div className="bg-white border border-slate-200 rounded-lg p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">My Teams</h2>
          <Link 
            href="/teams"
            className="text-blue-600 hover:text-blue-800 text-sm underline"
          >
            Manage Teams
          </Link>
        </div>
        
        {loadingTeams ? (
          <p className="text-slate-500">Loading teams...</p>
        ) : teams.length === 0 ? (
          <div className="text-center py-4">
            <p className="text-slate-600 mb-2">You're not a member of any teams yet.</p>
            <Link 
              href="/teams"
              className="text-blue-600 hover:text-blue-800 underline"
            >
              Create or join a team
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {teams.map((team) => (
              <div key={team.id} className="flex justify-between items-center p-3 bg-slate-50 rounded">
                <div>
                  <Link 
                    href={`/teams/${team.id}`}
                    className="font-medium text-slate-900 hover:text-blue-600"
                  >
                    {team.name}
                  </Link>
                  <div className="text-sm text-slate-500">
                    {team.memberCount} member{team.memberCount !== 1 ? 's' : ''}
                    {team.description && ` • ${team.description}`}
                  </div>
                </div>
                <Link
                  href={`/teams/${team.id}/decision`}
                  className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700 transition-colors"
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
