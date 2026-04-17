import './globals.css'
import React from 'react'
import type { Metadata } from 'next'
import { AuthProvider } from '../lib/auth-context'
import { LayoutWrapper } from '../components/layout/LayoutWrapper'

export const metadata: Metadata = {
  title: 'Umamimatch',
  description: 'Group lunch decision helper',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <AuthProvider>
          <LayoutWrapper>{children}</LayoutWrapper>
        </AuthProvider>
      </body>
    </html>
  )
}
