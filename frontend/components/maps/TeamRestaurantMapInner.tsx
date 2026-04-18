'use client'

import { useEffect, useMemo } from 'react'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { Circle, MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import { RestaurantMapPoint, TeamMapBase } from './TeamRestaurantMap'

interface TeamRestaurantMapInnerProps {
  teamBase?: TeamMapBase | null
  restaurants: RestaurantMapPoint[]
  selectedRestaurantId?: string | null
  onSelectRestaurant?: (id: string) => void
  radiusMeters?: number
  emptyMessage: string
}

const FALLBACK_CENTER: [number, number] = [48.2082, 16.3738]

function buildMarkerIcon({
  colorClass,
  ringClass,
  label,
}: {
  colorClass: string
  ringClass: string
  label?: string
}) {
  return L.divIcon({
    className: 'umami-map-marker-wrapper',
    html: `<div class="umami-map-marker ${colorClass} ${ringClass}">${label ?? ''}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -12],
  })
}

const TEAM_MARKER_ICON = buildMarkerIcon({
  colorClass: 'umami-map-marker-team',
  ringClass: '',
})

function restaurantMarkerIcon(isActive: boolean, isTopPick: boolean) {
  if (isTopPick) {
    return buildMarkerIcon({
      colorClass: 'umami-map-marker-top',
      ringClass: isActive ? 'umami-map-marker-active' : '',
      label: '1',
    })
  }

  return buildMarkerIcon({
    colorClass: 'umami-map-marker-default',
    ringClass: isActive ? 'umami-map-marker-active' : '',
  })
}

function FitBoundsController({
  teamBase,
  restaurants,
}: {
  teamBase?: TeamMapBase | null
  restaurants: RestaurantMapPoint[]
}) {
  const map = useMap()

  useEffect(() => {
    const points: [number, number][] = []
    if (teamBase) points.push([teamBase.lat, teamBase.lng])
    for (const restaurant of restaurants) {
      points.push([restaurant.lat, restaurant.lng])
    }

    if (points.length === 0) {
      map.setView(FALLBACK_CENTER, 12)
      return
    }

    if (points.length === 1) {
      map.setView(points[0], 15)
      return
    }

    map.fitBounds(points, {
      padding: [42, 42],
      maxZoom: 16,
    })
  }, [map, teamBase, restaurants])

  return null
}

export function TeamRestaurantMapInner({
  teamBase,
  restaurants,
  selectedRestaurantId,
  onSelectRestaurant,
  radiusMeters,
  emptyMessage,
}: TeamRestaurantMapInnerProps) {
  const topRestaurantId = useMemo(() => {
    const scored = restaurants.filter((restaurant) => typeof restaurant.score === 'number')
    if (scored.length === 0) return null

    const sorted = [...scored].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    return sorted[0]?.id ?? null
  }, [restaurants])

  const hasMapData = Boolean(teamBase) || restaurants.length > 0

  return (
    <>
      <style jsx global>{`
        .umami-map-marker-wrapper {
          background: transparent;
          border: 0;
        }

        .umami-map-marker {
          display: flex;
          height: 26px;
          width: 26px;
          align-items: center;
          justify-content: center;
          border-radius: 9999px;
          color: #ffffff;
          font-size: 11px;
          font-weight: 700;
          border: 2px solid #ffffff;
          box-shadow: 0 8px 20px rgba(15, 23, 42, 0.28);
          transition: transform 120ms ease;
        }

        .umami-map-marker-active {
          transform: scale(1.12);
          box-shadow: 0 10px 25px rgba(15, 23, 42, 0.36);
        }

        .umami-map-marker-team {
          background: #0f172a;
        }

        .umami-map-marker-top {
          background: #059669;
        }

        .umami-map-marker-default {
          background: #2563eb;
        }
      `}</style>

      {!hasMapData ? (
        <div className="flex h-full items-center justify-center bg-slate-50 px-4 text-center text-sm text-slate-500">
          {emptyMessage}
        </div>
      ) : (
        <MapContainer
          center={FALLBACK_CENTER}
          zoom={13}
          className="h-full w-full"
          zoomControl
          scrollWheelZoom
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          />

          <FitBoundsController teamBase={teamBase} restaurants={restaurants} />

          {teamBase && (
            <>
              <Marker position={[teamBase.lat, teamBase.lng]} icon={TEAM_MARKER_ICON}>
                <Popup>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-slate-900">Team base</p>
                    <p className="text-xs text-slate-700">{teamBase.name}</p>
                  </div>
                </Popup>
              </Marker>

              {radiusMeters ? (
                <Circle
                  center={[teamBase.lat, teamBase.lng]}
                  radius={radiusMeters}
                  pathOptions={{
                    color: '#16a34a',
                    fillColor: '#22c55e',
                    fillOpacity: 0.08,
                    weight: 1.5,
                  }}
                />
              ) : null}
            </>
          )}

          {restaurants.map((restaurant) => {
            const isSelected = selectedRestaurantId === restaurant.id
            const isTopPick = restaurant.isTopPick || topRestaurantId === restaurant.id

            return (
              <Marker
                key={restaurant.id}
                position={[restaurant.lat, restaurant.lng]}
                icon={restaurantMarkerIcon(isSelected, Boolean(isTopPick))}
                eventHandlers={{
                  click: () => {
                    onSelectRestaurant?.(restaurant.id)
                  },
                }}
              >
                <Popup>
                  <div className="min-w-[180px] space-y-2">
                    <p className="text-sm font-semibold text-slate-900">{restaurant.name}</p>
                    {restaurant.address ? (
                      <p className="text-xs text-slate-700">{restaurant.address}</p>
                    ) : null}
                    <div className="flex flex-wrap gap-2 text-xs">
                      {typeof restaurant.score === 'number' ? (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700">
                          Score {restaurant.score.toFixed(1)}
                        </span>
                      ) : null}
                      {typeof restaurant.distanceKm === 'number' ? (
                        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-blue-700">
                          {restaurant.distanceKm.toFixed(2)} km
                        </span>
                      ) : null}
                    </div>
                    {restaurant.mapsUri ? (
                      <a
                        href={restaurant.mapsUri}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-medium text-blue-700 underline"
                      >
                        Open in maps
                      </a>
                    ) : null}
                  </div>
                </Popup>
              </Marker>
            )
          })}
        </MapContainer>
      )}
    </>
  )
}
