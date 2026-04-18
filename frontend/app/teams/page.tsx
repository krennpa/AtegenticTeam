'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '../../lib/auth-context'
import { Team, TeamWithMembers } from '../../lib/types'
import Link from 'next/link'
import { BaseStatusBadge } from '../../components/ui/base-status-badge'
import { MapPin } from 'lucide-react'

export default function TeamsPage() {
  const { api, user } = useAuth()
  const [teams, setTeams] = useState<TeamWithMembers[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createForm, setCreateForm] = useState({
    name: '',
    description: '',
    location: '',
    maxMembers: ''
  })

  useEffect(() => {
    if (api) {
      loadTeams()
    }
  }, [api])

  const loadTeams = async () => {
    try {
      setLoading(true)
      const data = await api.get<TeamWithMembers[]>('/teams/')
      setTeams(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load teams')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateTeam = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!api) return

    try {
      const payload = {
        name: createForm.name,
        description: createForm.description || undefined,
        location: createForm.location || undefined,
        maxMembers: createForm.maxMembers ? parseInt(createForm.maxMembers) : undefined
      }
      
      await api.post<Team>('/teams/', payload)
      setCreateForm({ name: '', description: '', location: '', maxMembers: '' })
      setShowCreateForm(false)
      loadTeams()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create team')
    }
  }

  if (!user) {
    return (
      <div className="text-center py-8">
        <p>Please log in to manage teams.</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="text-center py-8">
        <p>Loading teams...</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-slate-900">My Teams</h1>
        <button
          onClick={() => setShowCreateForm(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          Create Team
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {showCreateForm && (
        <div className="bg-white border border-slate-200 rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Create New Team</h2>
          <form onSubmit={handleCreateTeam} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Team Name *
              </label>
              <input
                type="text"
                value={createForm.name}
                onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Description
              </label>
              <textarea
                value={createForm.description}
                onChange={(e) => setCreateForm(prev => ({ ...prev, description: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={3}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Team Base (optional)
              </label>
              <input
                type="text"
                value={createForm.location}
                onChange={(e) => setCreateForm(prev => ({ ...prev, location: e.target.value }))}
                placeholder="Office, neighborhood, or meetup anchor"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-slate-500">
                Team base helps show distance-aware restaurant context.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Max Members (optional)
              </label>
              <input
                type="number"
                value={createForm.maxMembers}
                onChange={(e) => setCreateForm(prev => ({ ...prev, maxMembers: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                min="1"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
              >
                Create Team
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="bg-slate-300 text-slate-700 px-4 py-2 rounded-md hover:bg-slate-400 transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {teams.length === 0 ? (
        <div className="text-center py-8 bg-slate-50 rounded-lg">
          <p className="text-slate-600 mb-4">You haven't joined any teams yet.</p>
          <p className="text-sm text-slate-500">Create a team or search for existing teams to join.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {teams.map((team) => (
            <div key={team.id} className="bg-white border border-slate-200 rounded-lg p-6 hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <h3 className="text-xl font-semibold text-slate-900 mb-2">
                    <Link 
                      href={`/teams/${team.id}`}
                      className="hover:text-blue-600 transition-colors"
                    >
                      {team.name}
                    </Link>
                  </h3>
                  {team.description && (
                    <p className="text-slate-600 mb-3">{team.description}</p>
                  )}
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <BaseStatusBadge hasBase={Boolean(team.location && team.location.trim())} />
                    {team.location && (
                      <p className="inline-flex items-center gap-1 text-sm text-slate-500">
                        <MapPin className="h-3.5 w-3.5" />
                        {team.location}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-sm text-slate-500">
                    <span>{team.memberCount} member{team.memberCount !== 1 ? 's' : ''}</span>
                    {team.maxMembers && (
                      <span>Max: {team.maxMembers}</span>
                    )}
                    <span>Created: {new Date(team.createdAt).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Link
                    href={`/teams/${team.id}`}
                    className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700 transition-colors"
                  >
                    View
                  </Link>
                  <Link
                    href={`/teams/${team.id}/decision`}
                    className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700 transition-colors"
                  >
                    Decide
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-8 text-center">
        <Link
          href="/teams/search"
          className="text-blue-600 hover:text-blue-800 underline"
        >
          Search for teams to join
        </Link>
      </div>
    </div>
  )
}
