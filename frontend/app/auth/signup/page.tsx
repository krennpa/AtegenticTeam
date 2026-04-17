'use client'

import { AuthForm } from '../../../components/forms/AuthForm'

export default function SignupPage() {
  return (
    <main className="min-h-[70vh] grid place-items-center">
      <AuthForm mode="signup" />
    </main>
  )
}
