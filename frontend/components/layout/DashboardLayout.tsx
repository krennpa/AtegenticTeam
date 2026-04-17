'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '../../lib/auth-context'
import { Button } from '../ui/button'
import { Avatar, AvatarFallback } from '../ui/avatar'
import { 
  Users, 
  Settings, 
  Search, 
  Home,
  LogOut,
  Plus,
  Sparkles
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { NotificationBell } from './NotificationBell'

interface DashboardLayoutProps {
  children: React.ReactNode
}

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: Home },
  { name: 'Decision', href: '/decision', icon: Sparkles },
  { name: 'Teams', href: '/teams', icon: Users },
  { name: 'Search Teams', href: '/teams/search', icon: Search },
  { name: 'Profile', href: '/profile', icon: Settings },
]

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname()
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="border-b bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-xl font-bold text-slate-900">
              Umamimatch
            </Link>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search teams..."
                className="w-80 rounded-lg border border-slate-200 bg-slate-50 pl-10 pr-4 py-2 text-sm focus:border-[#3a8aca] focus:outline-none focus:ring-1 focus:ring-[#3a8aca]"
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <NotificationBell />
            <Link href="/teams">
              <Button className="rounded-lg bg-[#3a8aca] hover:bg-[#3a8aca]/90">
                <Plus className="h-4 w-4 mr-2" />
                New Team
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="text-xs">
                  {user?.displayName?.charAt(0)?.toUpperCase() || user?.email?.charAt(0)?.toUpperCase() || 'U'}
                </AvatarFallback>
              </Avatar>
              <Button variant="ghost" onClick={logout} className="rounded-lg">
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className="w-64 border-r bg-white">
          <nav className="p-4">
            <div className="mb-6">
              <h2 className="mb-2 px-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Navigation
              </h2>
              <div className="space-y-1">
                {navigation.map((item) => {
                  const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className={cn(
                        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-[#3a8aca]/10 text-[#3a8aca] border-r-2 border-[#3a8aca]'
                          : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                      {item.name}
                    </Link>
                  )
                })}
              </div>
            </div>
            
            {user && (
              <div className="border-t pt-4">
                <div className="px-2">
                  <div className="flex items-center gap-2 mb-2">
                    <Avatar className="h-6 w-6">
                      <AvatarFallback className="text-xs">
                        {user.displayName?.charAt(0)?.toUpperCase() || user.email?.charAt(0)?.toUpperCase() || 'U'}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {user.displayName || 'User'}
                      </p>
                      <p className="text-xs text-slate-500 truncate">{user.email}</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
