'use client'

import { AuthForm } from '../../../components/forms/AuthForm'

export default function LoginPage() {
  return (
    <main className="min-h-[70vh] grid place-items-center">
      <AuthForm mode="login" />
    </main>
  )
}
