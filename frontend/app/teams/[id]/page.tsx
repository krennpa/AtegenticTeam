'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '../../../lib/auth-context'
import { TeamPreferenceSnapshot, TeamWithMembers, User } from '../../../lib/types'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Avatar, AvatarFallback } from '../../../components/ui/avatar'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../../../components/ui/dialog'
import { Button } from '../../../components/ui/button'

function prettifyPreferenceToken(value: string): string {
  return value
    .replace(/[_:]/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

export default function TeamDetailsPage() {
  const { api, user } = useAuth()
  const params = useParams()
  const router = useRouter()
  const teamId = params.id as string
  
  const [team, setTeam] = useState<TeamWithMembers | null>(null)
  const [teamPreference, setTeamPreference] = useState<TeamPreferenceSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingTeamPreference, setLoadingTeamPreference] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [teamPreferenceError, setTeamPreferenceError] = useState<string | null>(null)
  const [leaving, setLeaving] = useState(false)
  const [rebuildingTeamPreference, setRebuildingTeamPreference] = useState(false)
  
  // User search and invitation state
  const [showInviteForm, setShowInviteForm] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [searchResults, setSearchResults] = useState<User[]>([])
  const [searching, setSearching] = useState(false)
  const [inviting, setInviting] = useState<string | null>(null)

  useEffect(() => {
    if (api && user && teamId) {
      void loadTeam()
      void loadTeamPreference()
    }
  }, [api, teamId, user])

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

  const loadTeamPreference = async () => {
    try {
      setLoadingTeamPreference(true)
      setTeamPreferenceError(null)
      const data = await api.getTeamPreferences(teamId)
      setTeamPreference(data)
    } catch (err) {
      setTeamPreferenceError(err instanceof Error ? err.message : 'Failed to load team preference snapshot')
    } finally {
      setLoadingTeamPreference(false)
    }
  }

  const handleLeaveTeam = async () => {
    if (!api || !team) return
    
    const confirmed = window.confirm('Are you sure you want to leave this team?')
    if (!confirmed) return

    try {
      setLeaving(true)
      await api.delete(`/teams/${teamId}/leave`)
      router.push('/teams')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to leave team')
    } finally {
      setLeaving(false)
    }
  }

  const handleSearchUsers = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!api || !searchTerm.trim()) return

    try {
      setSearching(true)
      const results = await api.get<User[]>(`/teams/${teamId}/search-users/${encodeURIComponent(searchTerm)}`)
      setSearchResults(results)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search users')
    } finally {
      setSearching(false)
    }
  }

  const handleInviteUser = async (userId: string) => {
    if (!api) return

    try {
      setInviting(userId)
      await api.post(`/teams/${teamId}/invite/${userId}`)
      // Remove user from search results and reload team
      setSearchResults(prev => prev.filter(u => u.id !== userId))
      await Promise.all([loadTeam(), loadTeamPreference()])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to invite user')
    } finally {
      setInviting(null)
    }
  }

  const handleRebuildTeamPreference = async () => {
    if (!api) return

    try {
      setRebuildingTeamPreference(true)
      setTeamPreferenceError(null)
      const rebuilt = await api.rebuildTeamPreferences(teamId)
      setTeamPreference(rebuilt)
    } catch (err) {
      setTeamPreferenceError(err instanceof Error ? err.message : 'Failed to rebuild team preference snapshot')
    } finally {
      setRebuildingTeamPreference(false)
    }
  }

  if (!user) {
    return (
      <div className="text-center py-8">
        <p>Please log in to view team details.</p>
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

  if (error || !team) {
    return (
      <div className="text-center py-8">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error || 'Team not found'}
        </div>
        <Link href="/teams" className="text-blue-600 hover:text-blue-800 underline">
          Back to Teams
        </Link>
      </div>
    )
  }

  const isCreator = team.creatorUserId === user.id
  const teamSignals = teamPreference?.otherPreferences?.signals ?? {}
  const teamDislikes = teamPreference?.otherPreferences?.dislikes ?? []
  const teamMoods = teamPreference?.otherPreferences?.recentMoods ?? []
  const signalEntries = Object.entries(teamSignals)

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">{team.name}</h1>
          {team.description && (
            <p className="text-slate-600 text-lg">{team.description}</p>
          )}
          {team.location && (
            <p className="text-slate-500 mt-2">Location: {team.location}</p>
          )}
        </div>
        <div className="flex gap-2">
          <Link href={`/teams/${teamId}/decision`}>
            <Button className="rounded-2xl">Make Decision</Button>
          </Link>
          <Dialog open={showInviteForm} onOpenChange={setShowInviteForm}>
            <DialogTrigger asChild>
              <Button className="rounded-2xl" onClick={() => setShowInviteForm(true)}>Invite Members</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Invite Team Members</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSearchUsers} className="mb-4">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Search by name or email..."
                    className="flex-1 px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <Button type="submit" disabled={searching || !searchTerm.trim()} className="rounded-2xl">
                    {searching ? 'Searching...' : 'Search'}
                  </Button>
                </div>
              </form>
              {searchResults.length > 0 && (
                <div className="space-y-2">
                  {searchResults.map((user) => (
                    <div key={user.id} className="flex justify-between items-center p-3 bg-slate-50 rounded">
                      <div>
                        <div className="font-medium text-slate-900">{user.displayName || 'Anonymous'}</div>
                        <div className="text-sm text-slate-500">{user.email}</div>
                      </div>
                      <Button
                        onClick={() => handleInviteUser(user.id)}
                        disabled={inviting === user.id}
                        className="rounded-2xl"
                      >
                        {inviting === user.id ? 'Inviting...' : 'Invite'}
                      </Button>
                    </div>
                  ))}
                </div>
              )}
              {searchTerm && !searching && searchResults.length === 0 && (
                <div className="text-center py-4 text-slate-500">No users found matching "{searchTerm}"</div>
              )}
            </DialogContent>
          </Dialog>
          {!isCreator && (
            <Button onClick={handleLeaveTeam} disabled={leaving} className="rounded-2xl" variant="destructive">
              {leaving ? 'Leaving...' : 'Leave Team'}
            </Button>
          )}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Team Info */}
        <div className="bg-white border border-slate-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">Team Information</h2>
          <div className="space-y-3">
            <div>
              <span className="text-sm font-medium text-slate-500">Members:</span>
              <span className="ml-2 text-slate-900">
                {team.members.length}
                {team.maxMembers && ` / ${team.maxMembers}`}
              </span>
            </div>
            <div>
              <span className="text-sm font-medium text-slate-500">Created:</span>
              <span className="ml-2 text-slate-900">
                {new Date(team.createdAt).toLocaleDateString()}
              </span>
            </div>
            {team.location && (
              <div>
                <span className="text-sm font-medium text-slate-500">Location:</span>
                <span className="ml-2 text-slate-900">{team.location}</span>
              </div>
            )}
            <div>
              <span className="text-sm font-medium text-slate-500">Status:</span>
              <span className={`ml-2 px-2 py-1 rounded text-xs ${
                team.isActive 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-red-100 text-red-800'
              }`}>
                {team.isActive ? 'Active' : 'Inactive'}
              </span>
            </div>
          </div>
        </div>

        {/* Members List */}
        <div className="bg-white border border-slate-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">Team Members</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {team.members.map((member) => {
              const name = member.displayName || 'Anonymous'
              const initial = name.charAt(0).toUpperCase()
              return (
                <div key={member.id} className="flex items-center gap-3 p-2 rounded hover:bg-slate-50">
                  <Avatar>
                    <AvatarFallback>{initial}</AvatarFallback>
                  </Avatar>
                  <div className="flex-1">
                    <div className="font-medium text-slate-900">
                      {name}
                      {member.userId === team.creatorUserId && (
                        <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">Creator</span>
                      )}
                      {member.userId === user.id && (
                        <span className="ml-2 px-2 py-1 bg-green-100 text-green-800 text-xs rounded">You</span>
                      )}
                    </div>
                    <div className="text-sm text-slate-500">Joined: {new Date(member.joinedAt).toLocaleDateString()}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="mt-6 bg-white border border-slate-200 rounded-lg p-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-xl font-semibold">Team Preference Snapshot</h2>
            <p className="text-sm text-slate-600">
              Aggregated and masked signals only. Individual answers remain private.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={handleRebuildTeamPreference}
            disabled={loadingTeamPreference || rebuildingTeamPreference}
          >
            {rebuildingTeamPreference ? 'Rebuilding...' : 'Rebuild Snapshot'}
          </Button>
        </div>

        {teamPreferenceError && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 mb-4">
            {teamPreferenceError}
          </div>
        )}

        {loadingTeamPreference ? (
          <p className="text-sm text-slate-600">Loading team preference snapshot...</p>
        ) : teamPreference ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Budget Profile</p>
                <p className="text-base font-semibold text-slate-900">{prettifyPreferenceToken(teamPreference.budgetPreference)}</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Contributing Members</p>
                <p className="text-base font-semibold text-slate-900">{teamPreference.memberCount}</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Last Updated</p>
                <p className="text-base font-semibold text-slate-900">{new Date(teamPreference.updatedAt).toLocaleString()}</p>
              </div>
            </div>

            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Shared Allergies</p>
              <div className="mt-1 flex flex-wrap gap-2">
                {teamPreference.allergies.length > 0 ? (
                  teamPreference.allergies.map((allergy) => (
                    <span key={allergy} className="rounded-full bg-rose-100 px-2 py-1 text-xs text-rose-800">
                      {prettifyPreferenceToken(allergy)}
                    </span>
                  ))
                ) : (
                  <p className="text-sm text-slate-600">No shared allergy signals yet.</p>
                )}
              </div>
            </div>

            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Shared Dietary Restrictions</p>
              <div className="mt-1 flex flex-wrap gap-2">
                {teamPreference.dietaryRestrictions.length > 0 ? (
                  teamPreference.dietaryRestrictions.map((restriction) => (
                    <span key={restriction} className="rounded-full bg-amber-100 px-2 py-1 text-xs text-amber-800">
                      {prettifyPreferenceToken(restriction)}
                    </span>
                  ))
                ) : (
                  <p className="text-sm text-slate-600">No shared dietary restrictions yet.</p>
                )}
              </div>
            </div>

            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Top Team Signals</p>
              <div className="mt-1 space-y-2">
                {signalEntries.length > 0 ? (
                  signalEntries.map(([key, signal]) => (
                    <div key={key} className="rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700">
                      <span className="font-medium text-slate-900">{prettifyPreferenceToken(key)}</span>
                      <span className="ml-2">{prettifyPreferenceToken(signal.value)}</span>
                      <span className="ml-2 text-slate-500">({signal.support}/{signal.memberCount} support)</span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-600">No aggregated signal cards yet.</p>
                )}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Recent Team Moods</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {teamMoods.length > 0 ? (
                    teamMoods.map((mood) => (
                      <span key={mood} className="rounded-full bg-blue-100 px-2 py-1 text-xs text-blue-800">
                        {prettifyPreferenceToken(mood)}
                      </span>
                    ))
                  ) : (
                    <p className="text-sm text-slate-600">No mood signals yet.</p>
                  )}
                </div>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Current Team Vetoes</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {teamDislikes.length > 0 ? (
                    teamDislikes.map((dislike) => (
                      <span key={dislike} className="rounded-full bg-red-100 px-2 py-1 text-xs text-red-700">
                        {prettifyPreferenceToken(dislike)}
                      </span>
                    ))
                  ) : (
                    <p className="text-sm text-slate-600">No active vetoes.</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-600">No team preference snapshot found yet.</p>
        )}
      </div>

      {/* User Invitation Form is now shown in Dialog above */}

      {/* Privacy Notice */}
      <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="font-semibold text-blue-900 mb-2">Privacy Notice</h3>
        <p className="text-blue-800 text-sm">
          Individual preferences (budget, allergies, dietary restrictions) remain private. 
          Only team membership and display names are visible to other members.
        </p>
      </div>

      <div className="mt-6 text-center">
        <Link href="/teams" className="text-blue-600 hover:text-blue-800 underline">
          ← Back to Teams
        </Link>
      </div>
    </div>
  )
}
