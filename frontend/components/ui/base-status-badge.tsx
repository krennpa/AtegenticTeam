import { Badge } from './badge'

type BaseStatusBadgeProps = {
  hasBase: boolean
  compact?: boolean
}

export function BaseStatusBadge({ hasBase, compact = false }: BaseStatusBadgeProps) {
  if (hasBase) {
    return (
      <Badge className="border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100">
        {compact ? 'Base set' : 'Team base set'}
      </Badge>
    )
  }

  return (
    <Badge className="border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100">
      {compact ? 'Base missing' : 'Team base missing'}
    </Badge>
  )
}
