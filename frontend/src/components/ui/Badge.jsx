import { EXPERIMENT_STATUS, NODE_TYPES, SEVERITY } from '../../utils/constants'

export function Badge({ className = '', children, title }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${className || 'border-ink-600 bg-ink-700 text-ink-200'}`}>
      {children}
    </span>
  )
}

export function SeverityBadge({ severity }) {
  const s = SEVERITY[severity] || SEVERITY.info
  return <Badge className={s.cls}>{s.label}</Badge>
}

export function StatusBadge({ status }) {
  const s = EXPERIMENT_STATUS[status] || { label: status, cls: '' }
  return <Badge className={s.cls}>{s.label}</Badge>
}

const EVIDENCE = {
  confirmed: { label: 'Confirmed', cls: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/25', title: 'Directly visible in source code' },
  inferred: { label: 'Inferred', cls: 'text-amber-200 bg-amber-500/10 border-amber-500/25', title: 'Relies on a static-analysis heuristic' },
  unknown: { label: 'Unknown', cls: 'text-ink-200 bg-ink-700 border-ink-500', title: 'Not determinable statically' },
}
export function EvidenceBadge({ classification }) {
  const e = EVIDENCE[classification] || EVIDENCE.unknown
  return <Badge className={e.cls} title={e.title}>{e.label}</Badge>
}

export function TypeBadge({ type }) {
  const t = NODE_TYPES[type]
  if (!t) return <Badge>{type}</Badge>
  const Icon = t.icon
  return (
    <Badge className="border-white/10 bg-white/[0.03]" title={t.label}>
      <Icon className="h-3 w-3" style={{ color: t.color }} />
      <span className="text-ink-200">{t.label}</span>
    </Badge>
  )
}

export function CertaintyBadge({ certainty }) {
  if (certainty === 'definite') return <Badge className="text-rose-300 bg-rose-500/10 border-rose-500/25" title="Reached without crossing a handled call site">Definite</Badge>
  if (certainty === 'possible') return <Badge className="text-amber-200 bg-amber-500/10 border-amber-500/25" title="Only reached through call sites that handle the error">Possible</Badge>
  return <Badge>Unaffected</Badge>
}
