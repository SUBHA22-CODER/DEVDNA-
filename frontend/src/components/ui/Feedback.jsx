import { motion } from 'framer-motion'
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react'
import { Button } from './Button'

export function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded-md bg-ink-700/60 ${className}`} />
}

export function SkeletonCards({ count = 4, className = 'h-24' }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className={className} />
      ))}
    </div>
  )
}

export function Spinner({ label }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-300">
      <Loader2 className="h-4 w-4 animate-spin text-violet-300" />
      {label}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center justify-center rounded-xl border border-dashed border-ink-600 bg-ink-900/40 px-6 py-12 text-center">
      {Icon && (
        <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/15 to-cyan-400/10 text-violet-200 ring-1 ring-white/10">
          <Icon className="h-5 w-5" />
        </div>
      )}
      <h3 className="text-sm font-semibold text-ink-100">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-ink-300">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </motion.div>
  )
}

export function ErrorState({ error, onRetry, title = 'Something went wrong' }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} role="alert" className="flex items-start gap-3 rounded-xl border border-rose-500/25 bg-rose-500/[0.06] p-4">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-300" />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-rose-100">{title}</div>
        <div className="mt-0.5 text-sm text-rose-200/80">{error?.message || String(error)}</div>
        {error?.fields?.length > 0 && (
          <ul className="mt-1 text-xs text-rose-200/70">
            {error.fields.map((f) => (
              <li key={f.field}>{f.field}: {f.message}</li>
            ))}
          </ul>
        )}
      </div>
      {onRetry && (
        <Button size="sm" variant="ghost" icon={RefreshCw} onClick={() => onRetry()}>
          Retry
        </Button>
      )}
    </motion.div>
  )
}

export function InlineNotice({ tone = 'info', icon: Icon, children }) {
  const cls = {
    info: 'border-cyan-400/20 bg-cyan-400/[0.05] text-cyan-100/90',
    warn: 'border-amber-400/25 bg-amber-400/[0.06] text-amber-100/90',
    violet: 'border-violet-400/25 bg-violet-400/[0.06] text-violet-100/90',
  }[tone]
  return (
    <div className={`flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-sm ${cls}`}>
      {Icon && <Icon className="mt-0.5 h-4 w-4 shrink-0" />}
      <div className="min-w-0">{children}</div>
    </div>
  )
}
