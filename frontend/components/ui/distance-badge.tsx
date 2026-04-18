import { Badge } from './badge'

type DistanceBadgeProps = {
  distanceKm?: number | null
}

function getDistanceTone(distanceKm: number): string {
  if (distanceKm <= 1.5) {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
  }
  if (distanceKm <= 4) {
    return 'border-sky-200 bg-sky-50 text-sky-700 hover:bg-sky-100'
  }
  return 'border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-200'
}

export function DistanceBadge({ distanceKm }: DistanceBadgeProps) {
  if (typeof distanceKm !== 'number') {
    return null
  }

  return (
    <Badge className={getDistanceTone(distanceKm)}>
      {distanceKm.toFixed(2)} km from base
    </Badge>
  )
}
