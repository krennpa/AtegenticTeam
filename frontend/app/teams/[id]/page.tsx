'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '../../../lib/auth-context'
import { TeamWithMembers, User } from '../../../lib/types'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Avatar, AvatarFallback } from '../../../components/ui/avatar'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../../../components/ui/dialog'
import { Button } from '../../../components/ui/button'

export default function TeamDetailsPage() {
  const { api, user } = useAuth()
  const params = useParams()
  const router = useRouter()
  const teamId = params.id as string
  
  const [team, setTeam] = useState<TeamWithMembers | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [leaving, setLeaving] = useState(false)
  
  // User search and invitation state
  const [showInviteForm, setShowInviteForm] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [searchResults, setSearchResults] = useState<User[]>([])
  const [searching, setSearching] = useState(false)
  const [inviting, setInviting] = useState<string | null>(null)

  useEffect(() => {
    if (api && teamId) {
      loadTeam()
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
      loadTeam()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to invite user')
    } finally {
      setInviting(null)
    }
  }

  const resetInviteForm = () => {
    setShowInviteForm(false)
    setSearchTerm('')
    setSearchResults([])
    setError(null)
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

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">{team.name}</h1>
          {team.description && (
            <p className="text-slate-600 text-lg">{team.description}</p>
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
