'use client'

import React, { useState } from 'react'
import { useAuth } from '../../lib/auth-context'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../ui/card'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Button } from '../ui/button'

export type AuthFormProps = {
  mode: 'login' | 'signup'
}

export function AuthForm({ mode }: AuthFormProps) {
  const { login, signup } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await signup(email, password, displayName)
      }
    } catch (err: any) {
      setError(err.message || 'Failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="max-w-md w-full shadow">
      <CardHeader>
        <CardTitle>{mode === 'login' ? 'Welcome back' : 'Create your account'}</CardTitle>
        <CardDescription>
          {mode === 'login' ? 'Log in to continue to Dynalunch' : 'Sign up to start making effortless lunch decisions'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" value={email} onChange={e => setEmail(e.target.value)} type="email" required placeholder="you@example.com" />
          </div>
          {mode === 'signup' && (
            <div className="space-y-2">
              <Label htmlFor="displayName">Display Name</Label>
              <Input id="displayName" value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="Your name" />
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" value={password} onChange={e => setPassword(e.target.value)} type="password" required placeholder="••••••••" />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" disabled={loading} className="w-full rounded-2xl">
            {loading ? 'Please wait…' : mode === 'login' ? 'Login' : 'Sign up'}
          </Button>
        </form>
      </CardContent>
      <CardFooter>
        <p className="text-xs text-muted-foreground">By continuing, you agree to our Terms and Privacy Policy.</p>
      </CardFooter>
    </Card>
  )
}
