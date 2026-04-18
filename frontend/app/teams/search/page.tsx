'use client'

import { useState } from 'react'
import { useAuth } from '../../../lib/auth-context'
import { Team } from '../../../lib/types'
import Link from 'next/link'

export default function TeamSearchPage() {
  const { api, user } = useAuth()
  const [searchTerm, setSearchTerm] = useState('')
  const [searchResults, setSearchResults] = useState<Team[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [joiningTeam, setJoiningTeam] = useState<string | null>(null)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!api || !searchTerm.trim()) return

    try {
      setLoading(true)
      setError(null)
      const results = await api.get<Team[]>(`/teams/search/${encodeURIComponent(searchTerm)}`)
      setSearchResults(results)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search teams')
    } finally {
      setLoading(false)
    }
  }

  const handleJoinTeam = async (teamId: string) => {
    if (!api) return

    try {
      setJoiningTeam(teamId)
      await api.post('/teams/join', { teamId })
      // Remove the team from search results since user has joined
      setSearchResults(prev => prev.filter(team => team.id !== teamId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to join team')
    } finally {
      setJoiningTeam(null)
    }
  }

  if (!user) {
    return (
      <div className="text-center py-8">
        <p>Please log in to search for teams.</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900 mb-4">Search Teams</h1>
        <p className="text-slate-600">Find and join existing teams to collaborate on lunch decisions.</p>
      </div>

      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex gap-2">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Enter team name to search..."
            className="flex-1 px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={loading || !searchTerm.trim()}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {searchResults.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-slate-900">Search Results</h2>
          {searchResults.map((team) => (
            <div key={team.id} className="bg-white border border-slate-200 rounded-lg p-6">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <h3 className="text-xl font-semibold text-slate-900 mb-2">{team.name}</h3>
                  {team.description && (
                    <p className="text-slate-600 mb-3">{team.description}</p>
                  )}
                  {team.location && (
                    <p className="text-sm text-slate-500 mb-3">Location: {team.location}</p>
                  )}
                  <div className="flex items-center gap-4 text-sm text-slate-500">
                    <span>{team.memberCount} member{team.memberCount !== 1 ? 's' : ''}</span>
                    {team.maxMembers && (
                      <span>Max: {team.maxMembers}</span>
                    )}
                    <span>Created: {new Date(team.createdAt).toLocaleDateString()}</span>
                  </div>
                  {team.maxMembers && team.memberCount >= team.maxMembers && (
                    <div className="mt-2">
                      <span className="px-2 py-1 bg-red-100 text-red-800 text-xs rounded">
                        Team Full
                      </span>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleJoinTeam(team.id)}
                    disabled={
                      joiningTeam === team.id || 
                      (team.maxMembers ? team.memberCount >= team.maxMembers : false)
                    }
                    className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {joiningTeam === team.id ? 'Joining...' : 'Join Team'}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {searchTerm && !loading && searchResults.length === 0 && (
        <div className="text-center py-8 bg-slate-50 rounded-lg">
          <p className="text-slate-600">No teams found matching "{searchTerm}"</p>
          <p className="text-sm text-slate-500 mt-2">Try a different search term or create a new team.</p>
        </div>
      )}

      <div className="mt-8 text-center">
        <Link href="/teams" className="text-blue-600 hover:text-blue-800 underline">
          ← Back to My Teams
        </Link>
      </div>
    </div>
  )
}
