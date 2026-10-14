import { motion } from 'framer-motion'

// Cards animate themselves on mount instead of inheriting variant labels from parents,
// so a card that mounts later (e.g. after an AI response) can never get stuck hidden.
export function Card({ className = '', interactive = false, children, ...props }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      whileHover={interactive ? { y: -2, borderColor: 'rgba(139,92,246,0.35)' } : undefined}
      whileTap={interactive ? { scale: 0.99 } : undefined}
      className={`min-w-0 rounded-xl border border-white/[0.06] bg-ink-850/80 ${interactive ? 'cursor-pointer' : ''} ${className}`}
      {...props}
    >
      {children}
    </motion.div>
  )
}

export function CardHeader({ title, subtitle, icon: Icon, action, className = '' }) {
  return (
    <div className={`flex items-start justify-between gap-3 border-b border-white/[0.05] px-4 py-3 ${className}`}>
      <div className="flex min-w-0 items-center gap-2.5">
        {Icon && (
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-ink-700 text-ink-200">
            <Icon className="h-3.5 w-3.5" />
          </span>
        )}
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-ink-100">{title}</h3>
          {subtitle && <p className="truncate text-xs text-ink-300">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  )
}

export function Stat({ label, value, hint, icon: Icon, accent = 'violet' }) {
  const ring = accent === 'cyan' ? 'text-cyan-300 bg-cyan-400/10' : accent === 'amber' ? 'text-amber-300 bg-amber-400/10' : accent === 'rose' ? 'text-rose-300 bg-rose-400/10' : accent === 'emerald' ? 'text-emerald-300 bg-emerald-400/10' : 'text-violet-300 bg-violet-400/10'
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-ink-300">{label}</span>
        {Icon && (
          <span className={`flex h-7 w-7 items-center justify-center rounded-md ${ring}`}>
            <Icon className="h-3.5 w-3.5" />
          </span>
        )}
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums text-ink-100">{value}</div>
      {hint && <div className="mt-1 text-xs text-ink-300">{hint}</div>}
    </Card>
  )
}

export function PageHeader({ title, subtitle, actions, eyebrow }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <div className="mb-1 text-xs font-medium uppercase tracking-[0.18em] text-violet-300/80">{eyebrow}</div>}
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-ink-300">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
