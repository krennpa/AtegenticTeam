'use client'

import React, { useEffect, useState } from 'react'
import { useAuth } from '../../lib/auth-context'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Textarea } from '../ui/textarea'
import { Button } from '../ui/button'

type Profile = {
  id: string
  userId: string
  displayName?: string | null
  budgetPreference: 'low' | 'medium' | 'high'
  allergies: string[]
  dietaryRestrictions: string[]
  otherPreferences: Record<string, any>
}

export function ProfileForm() {
  const { api } = useAuth()
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get<Profile>('/profiles/me').then(setProfile).catch((e) => setError(e.message))
  }, [api])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!profile) return
    setSaving(true)
    setError(null)
    try {
      const payload = {
        displayName: profile.displayName,
        budgetPreference: profile.budgetPreference,
        allergies: profile.allergies,
        dietaryRestrictions: profile.dietaryRestrictions,
        otherPreferences: profile.otherPreferences,
      }
      const updated = await api.put<Profile>('/profiles/me', payload)
      setProfile(updated)
    } catch (err: any) {
      setError(err.message || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  if (!profile) return <p>Loading… {error && <span className="text-red-600">{error}</span>}</p>

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Profile</CardTitle>
        <CardDescription>Manage your preferences. These remain private to the team.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="displayName">Display Name</Label>
            <Input
              id="displayName"
              value={profile.displayName ?? ''}
              onChange={(e) => setProfile({ ...profile, displayName: e.target.value })}
              placeholder="Your name"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="budget">Budget</Label>
            <select
              id="budget"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={profile.budgetPreference}
              onChange={(e) => setProfile({ ...profile, budgetPreference: e.target.value as Profile['budgetPreference'] })}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="allergies">Allergies (comma-separated)</Label>
            <Input
              id="allergies"
              value={(profile.allergies || []).join(', ')}
              onChange={(e) => setProfile({ ...profile, allergies: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
              placeholder="e.g. peanuts, shellfish"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="dietary">Dietary Restrictions (comma-separated)</Label>
            <Textarea
              id="dietary"
              value={(profile.dietaryRestrictions || []).join(', ')}
              onChange={(e) => setProfile({ ...profile, dietaryRestrictions: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
              placeholder="e.g. vegetarian, halal"
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" disabled={saving} className="rounded-2xl">
            {saving ? 'Saving…' : 'Save Profile'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
