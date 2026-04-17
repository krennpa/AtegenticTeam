'use client'

import React, { useState } from 'react'
import { useAuth } from '../../lib/auth-context'

export function RestaurantUrlForm({ meProfileId }: { meProfileId: string }) {
  const { api } = useAuth()
  const [urls, setUrls] = useState<string>('')
  const [result, setResult] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onRun(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const urlList = urls.split(/\n|,/).map(s => s.trim()).filter(Boolean)
      const resp = await api.post<any>('/decision/', {
        participantProfileIds: [meProfileId],
        restaurantUrls: urlList,
      })
      setResult(resp)
    } catch (err: any) {
      setError(err.message || 'Failed to decide')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={onRun} className="space-y-3">
        <label className="block text-sm font-medium">Restaurant menu URLs (one per line)</label>
        <textarea
          className="w-full rounded border p-2 h-32"
          placeholder="https://example.com/menu\nhttps://www.enjoyhenry.com/menuplan-bdo/"
          value={urls}
          onChange={e => setUrls(e.target.value)}
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button disabled={loading} className="px-4 py-2 bg-emerald-600 text-white rounded disabled:opacity-50">
          {loading ? 'Running…' : 'Run Decision'}
        </button>
      </form>
      {result && (
        <div className="rounded border p-3 bg-white">
          <h3 className="font-semibold mb-2">Result</h3>
          {result.bestRestaurantId ? (
            <p className="mb-2">Best Restaurant ID: <span className="font-mono">{result.bestRestaurantId}</span></p>
          ) : (
            <p>No clear winner.</p>
          )}
          <div className="mt-2 space-y-2">
            {result.ranking?.map((r: any) => (
              <div key={r.restaurantId} className="rounded border p-2">
                <div className="flex justify-between">
                  <span>Restaurant: <span className="font-mono">{r.restaurantId}</span></span>
                  <span>Score: {r.score}</span>
                </div>
                <ul className="list-disc ml-5 text-sm text-slate-600">
                  {r.topMatches?.map((m: any) => (
                    <li key={m.profileId + m.dish}>{m.profileId} → {m.dish} ({m.score.toFixed(2)})</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
