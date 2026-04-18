'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { PreferenceGame } from '../../components/forms/PreferenceGame'
import { useAuth } from '../../lib/auth-context'

export default function PreferencesPage() {
  const { user } = useAuth()

  if (!user) {
    return (
      <main className="space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">Preference Game</h1>
        <p className="text-slate-600">Please log in to continue.</p>
      </main>
    )
  }

  return (
    <main className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-slate-900">Preference Game</h1>
          <p className="mt-1 text-sm text-slate-600">
            Shape your flavor profile with fast, playful prompts.
          </p>
        </div>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Link>
      </div>

      <PreferenceGame
        questionLimit={5}
        title="Preference Game"
        description="Pick what sounds right now. Every answer improves your matching profile."
      />
    </main>
  )
}
