'use client'

import { AuthForm } from '../../../components/forms/AuthForm'

export default function LoginPage() {
  return (
    <main className="space-y-6">
      <h1 className="text-xl font-semibold">Login</h1>
      <AuthForm mode="login" />
    </main>
  )
}
