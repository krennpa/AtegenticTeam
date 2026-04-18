'use client'

import dynamic from 'next/dynamic'
import { MapPin, Sparkles, Star } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface TeamMapBase {
  id: string
  name: string
  lat: number
  lng: number
}

export interface RestaurantMapPoint {
  id: string
  name: string
  lat: number
  lng: number
  address?: string
  score?: number | null
  distanceKm?: number | null
  mapsUri?: string | null
  isTopPick?: boolean
}

interface TeamRestaurantMapProps {
  teamBase?: TeamMapBase | null
  restaurants: RestaurantMapPoint[]
  selectedRestaurantId?: string | null
  onSelectRestaurant?: (id: string) => void
  radiusMeters?: number
  className?: string
  mapHeightClassName?: string
  emptyMessage?: string
}

const TeamRestaurantMapInner = dynamic(
  () => import('./TeamRestaurantMapInner').then((mod) => mod.TeamRestaurantMapInner),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center bg-slate-100 text-sm text-slate-500">
        Loading map...
      </div>
    ),
  },
)

export function TeamRestaurantMap({
  teamBase,
  restaurants,
  selectedRestaurantId,
  onSelectRestaurant,
  radiusMeters,
  className,
  mapHeightClassName,
  emptyMessage,
}: TeamRestaurantMapProps) {
  return (
    <section
      className={cn(
        'overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm',
        className,
      )}
    >
      <div className="border-b border-slate-100 bg-gradient-to-r from-slate-50 via-white to-slate-50 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1">
            <MapPin className="h-3.5 w-3.5 text-slate-700" />
            Team base
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-1">
            <Star className="h-3.5 w-3.5 text-emerald-700" />
            Top match
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-1">
            <Sparkles className="h-3.5 w-3.5 text-blue-700" />
            Candidates ({restaurants.length})
          </span>
        </div>
      </div>

      <div className={cn('h-[380px]', mapHeightClassName)}>
        <TeamRestaurantMapInner
          teamBase={teamBase}
          restaurants={restaurants}
          selectedRestaurantId={selectedRestaurantId}
          onSelectRestaurant={onSelectRestaurant}
          radiusMeters={radiusMeters}
          emptyMessage={
            emptyMessage ?? 'No map-ready locations available yet. Add a location to unlock map context.'
          }
        />
      </div>
    </section>
  )
}
