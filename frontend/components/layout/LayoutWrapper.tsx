'use client'

import { usePathname } from 'next/navigation'
import { useAuth } from '../../lib/auth-context'
import { DashboardLayout } from './DashboardLayout'

interface LayoutWrapperProps {
  children: React.ReactNode
}

export function LayoutWrapper({ children }: LayoutWrapperProps) {
  const pathname = usePathname()
  const { user } = useAuth()

  // Landing page and auth pages should not use dashboard layout
  const isLandingPage = pathname === '/'
  const isAuthPage = pathname.startsWith('/auth/')
  const shouldUseDashboardLayout = user && !isLandingPage && !isAuthPage

  if (shouldUseDashboardLayout) {
    return <DashboardLayout>{children}</DashboardLayout>
  }

  // For landing page and auth pages, use simple container
  return (
    <div className={isLandingPage ? '' : 'mx-auto max-w-3xl p-6'}>
      {children}
    </div>
  )
}
