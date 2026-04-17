'use client'

import { AuthForm } from '../../../components/forms/AuthForm'

export default function SignupPage() {
  return (
    <main className="space-y-6">
      <h1 className="text-xl font-semibold">Signup</h1>
      <AuthForm mode="signup" />
    </main>
  )
}
