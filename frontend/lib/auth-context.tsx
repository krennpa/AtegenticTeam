'use client'

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createApiClient } from './api'

type User = { id: string; email: string; displayName?: string | null }

type AuthContextValue = {
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string, displayName?: string) => Promise<void>
  logout: () => void
  api: ReturnType<typeof createApiClient>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const router = useRouter()

  useEffect(() => {
    const t = window.localStorage.getItem('auth_token')
    const u = window.localStorage.getItem('auth_user')
    if (t) setToken(t)
    if (u) setUser(JSON.parse(u))
  }, [])

  const api = useMemo(() => createApiClient(() => token), [token])

  async function login(email: string, password: string) {
    const res = await api.post<{ user: User; token: string }>('/auth/login', { email, password })
    setToken(res.token)
    setUser(res.user)
    window.localStorage.setItem('auth_token', res.token)
    window.localStorage.setItem('auth_user', JSON.stringify(res.user))
    router.push('/profile')
  }

  async function signup(email: string, password: string, displayName?: string) {
    const res = await api.post<{ user: User; token: string }>('/auth/signup', { email, password, displayName })
    setToken(res.token)
    setUser(res.user)
    window.localStorage.setItem('auth_token', res.token)
    window.localStorage.setItem('auth_user', JSON.stringify(res.user))
    router.push('/profile')
  }

  function logout() {
    setToken(null)
    setUser(null)
    window.localStorage.removeItem('auth_token')
    window.localStorage.removeItem('auth_user')
    router.push('/')
  }

  const value: AuthContextValue = { user, token, login, signup, logout, api }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
