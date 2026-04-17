'use client'

import { useEffect, useState } from 'react'
import { Bell } from 'lucide-react'
import { useAuth } from '../../lib/auth-context'
import { Notification, NotificationCountResponse } from '../../lib/types'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '../ui/dropdown-menu'
import { Button } from '../ui/button'
import { useRouter } from 'next/navigation'

export function NotificationBell() {
  const { api } = useAuth()
  const router = useRouter()
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [isOpen, setIsOpen] = useState(false)

  const fetchUnreadCount = async () => {
    try {
      const data = await api.get<NotificationCountResponse>('/notifications/unread-count')
      setUnreadCount(data.unreadCount)
    } catch (error) {
      console.error('Failed to fetch unread count:', error)
    }
  }

  const fetchNotifications = async () => {
    try {
      const data = await api.get<Notification[]>('/notifications?limit=10')
      setNotifications(data)
    } catch (error) {
      console.error('Failed to fetch notifications:', error)
    }
  }

  useEffect(() => {
    fetchUnreadCount()
    const interval = setInterval(fetchUnreadCount, 30000) // Poll every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open)
    if (open) {
      fetchNotifications()
    }
  }

  const handleNotificationClick = async (notification: Notification) => {
    if (!notification.isRead) {
      try {
        await api.post(`/notifications/${notification.id}/mark-read`)
        setUnreadCount(prev => Math.max(0, prev - 1))
        setNotifications(prev =>
          prev.map(n => (n.id === notification.id ? { ...n, isRead: true } : n))
        )
      } catch (error) {
        console.error('Failed to mark notification as read:', error)
      }
    }

    if (notification.type === 'team_decision' && notification.teamId) {
      router.push(`/dashboard?tab=past-decisions`)
      setIsOpen(false)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await api.post('/notifications/mark-all-read')
      setUnreadCount(0)
      setNotifications(prev => prev.map(n => ({ ...n, isRead: true })))
    } catch (error) {
      console.error('Failed to mark all as read:', error)
    }
  }

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)

    if (seconds < 60) return 'just now'
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
  }

  return (
    <DropdownMenu open={isOpen} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <div className="flex items-center justify-between px-2 py-2">
          <h3 className="font-semibold">Notifications</h3>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleMarkAllRead}
              className="text-xs"
            >
              Mark all read
            </Button>
          )}
        </div>
        <DropdownMenuSeparator />
        {notifications.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            No notifications
          </div>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            {notifications.map((notification) => (
              <DropdownMenuItem
                key={notification.id}
                onClick={() => handleNotificationClick(notification)}
                className={`flex flex-col items-start px-4 py-3 cursor-pointer ${
                  !notification.isRead ? 'bg-blue-50' : ''
                }`}
              >
                <div className="flex items-start justify-between w-full">
                  <div className="flex-1">
                    <p className="font-medium text-sm">{notification.title}</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      {notification.message}
                    </p>
                  </div>
                  {!notification.isRead && (
                    <div className="ml-2 mt-1 h-2 w-2 rounded-full bg-blue-500 flex-shrink-0" />
                  )}
                </div>
                <span className="text-xs text-muted-foreground mt-2">
                  {formatTimeAgo(notification.createdAt)}
                </span>
              </DropdownMenuItem>
            ))}
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
