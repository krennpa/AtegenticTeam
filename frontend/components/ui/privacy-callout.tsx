import { ShieldCheck } from 'lucide-react'

type PrivacyCalloutProps = {
  className?: string
  title?: string
  description?: string
}

export function PrivacyCallout({
  className = '',
  title = 'Privacy Notice',
  description = 'Individual preferences remain private. Teammates only see aggregated team signals and final recommendations.',
}: PrivacyCalloutProps) {
  return (
    <div className={`rounded-lg border border-blue-200 bg-blue-50 p-4 ${className}`.trim()}>
      <div className="flex items-start gap-2">
        <ShieldCheck className="mt-0.5 h-4 w-4 text-blue-700" />
        <div>
          <h3 className="font-semibold text-blue-900">{title}</h3>
          <p className="text-sm text-blue-800">{description}</p>
        </div>
      </div>
    </div>
  )
}
