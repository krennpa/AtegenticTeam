import { Badge } from './badge'

type FreshnessBadgeProps = {
  contentAgeDays?: number | null
  hasContent?: boolean
}

export function FreshnessBadge({ contentAgeDays, hasContent = true }: FreshnessBadgeProps) {
  if (!hasContent) {
    return (
      <Badge className="border-red-200 bg-red-50 text-red-700 hover:bg-red-100">
        No menu content
      </Badge>
    )
  }

  if (typeof contentAgeDays !== 'number') {
    return (
      <Badge className="border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-200">
        Freshness unknown
      </Badge>
    )
  }

  if (contentAgeDays <= 0) {
    return (
      <Badge className="border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100">
        Updated today
      </Badge>
    )
  }

  if (contentAgeDays === 1) {
    return (
      <Badge className="border-sky-200 bg-sky-50 text-sky-700 hover:bg-sky-100">
        Updated 1 day ago
      </Badge>
    )
  }

  if (contentAgeDays <= 3) {
    return (
      <Badge className="border-sky-200 bg-sky-50 text-sky-700 hover:bg-sky-100">
        Updated {contentAgeDays} days ago
      </Badge>
    )
  }

  return (
    <Badge className="border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100">
      Updated {contentAgeDays} days ago
    </Badge>
  )
}
