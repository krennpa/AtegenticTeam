'use client'

import Link from 'next/link'
import { usePreferenceGame } from '../../lib/use-preference-game'
import { Button } from '../ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'

export function PreferenceSummaryCard() {
  const { progress, loading, error } = usePreferenceGame({ questionLimit: 1 })
  const completion = Math.max(0, Math.min(100, progress?.completionPercent ?? 0))

  return (
    <Card className="border-sky-200/70 bg-gradient-to-r from-sky-50 via-white to-emerald-50">
      <CardHeader>
        <CardTitle>Preference Progress</CardTitle>
        <CardDescription>
          Continue the game to improve team matching quality.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && <p className="text-sm text-slate-600">Loading preference progress...</p>}
        {error && <p className="text-sm text-red-700">{error}</p>}

        {!loading && !error && progress && (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-sky-200 bg-white p-3">
                <p className="text-xs uppercase text-slate-500">Points</p>
                <p className="text-xl font-semibold text-slate-900">{progress.points}</p>
              </div>
              <div className="rounded-lg border border-emerald-200 bg-white p-3">
                <p className="text-xs uppercase text-slate-500">Level</p>
                <p className="text-xl font-semibold text-slate-900">{progress.level}</p>
              </div>
              <div className="rounded-lg border border-amber-200 bg-white p-3">
                <p className="text-xs uppercase text-slate-500">Completion</p>
                <p className="text-xl font-semibold text-slate-900">{progress.completionPercent}%</p>
              </div>
            </div>

            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-500 transition-all"
                style={{ width: `${completion}%` }}
              />
            </div>
          </>
        )}

        <Link href="/preferences">
          <Button className="rounded-lg bg-sky-600 hover:bg-sky-700">
            Continue Preference Game
          </Button>
        </Link>
      </CardContent>
    </Card>
  )
}
