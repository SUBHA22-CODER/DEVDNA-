import { motion } from 'framer-motion'
import { ArrowDownRight, ArrowUpLeft, Crosshair, FileCode2, Radar, Zap } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAsync } from '../../hooks/useAsync'
import { api } from '../../services/api'
import { EDGE_LABELS, NODE_TYPES } from '../../utils/constants'
import { shortId } from '../../utils/graph'
import { Badge, Button, Drawer, ErrorState, EvidenceBadge, SeverityBadge, Skeleton, TypeBadge } from '../ui'

const SCENARIO_FOR = { database: 'db_unavailable', external_api: 'external_api_unavailable', env_var: 'missing_env_var', worker: 'worker_unavailable' }
const TABS = ['Details', 'Relationships', 'Source', 'Findings']

export function EvidenceList({ evidence }) {
  if (!evidence?.length) return <p className="text-xs text-ink-400">No source evidence recorded.</p>
  return (
    <ul className="space-y-1.5">
      {evidence.map((ev, i) => (
        <li key={i} className="rounded-md border border-white/[0.05] bg-ink-900/70 px-2.5 py-1.5">
          <div className="flex items-center gap-2 font-mono text-[11px] text-cyan-200">
            <FileCode2 className="h-3 w-3" /> {ev.file}{ev.line ? `:${ev.line}` : ''}
          </div>
          {ev.snippet && <code className="mt-1 block whitespace-pre-wrap break-all font-mono text-[11px] text-ink-200">{ev.snippet}</code>}
          {ev.detail && <div className="mt-0.5 text-[11px] text-ink-400">{ev.detail}</div>}
        </li>
      ))}
    </ul>
  )
}

function EdgeRow({ edge, otherId, direction, onSelectNode }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="rounded-lg border border-white/[0.06] bg-ink-900/40">
      <div className="flex items-center gap-2 px-3 py-2">
        {direction === 'out' ? <ArrowDownRight className="h-3.5 w-3.5 text-cyan-300" /> : <ArrowUpLeft className="h-3.5 w-3.5 text-violet-300" />}
        <span className="text-[11px] text-ink-400">{EDGE_LABELS[edge.type] || edge.type}</span>
        <button onClick={() => onSelectNode(otherId)} className="min-w-0 flex-1 truncate text-left font-mono text-xs text-ink-100 hover:text-violet-200">
          {shortId(otherId)}
        </button>
        <EvidenceBadge classification={edge.classification} />
        <button onClick={() => setOpen((o) => !o)} className="text-[11px] text-violet-300 hover:underline" aria-expanded={open}>
          {open ? 'Hide' : 'Evidence'}
        </button>
      </div>
      {open && (
        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="overflow-hidden px-3 pb-2">
          <EvidenceList evidence={edge.evidence} />
        </motion.div>
      )}
    </li>
  )
}

export default function ComponentDrawer({ projectId, componentId, onClose, onSelectNode, onBlastRadius }) {
  const [tab, setTab] = useState('Details')
  const { data, error, loading, reload } = useAsync(() => api.component(projectId, componentId), [projectId, componentId], { enabled: Boolean(componentId) })
  const t = NODE_TYPES[data?.type]
  const scenario = SCENARIO_FOR[data?.type]

  return (
    <Drawer open={Boolean(componentId)} onClose={onClose} title={data?.name || shortId(componentId || '')} subtitle={componentId} icon={t?.icon}>
      {loading && (
        <div className="space-y-3 p-5">
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      )}
      {error && <div className="p-5"><ErrorState error={error} onRetry={reload} /></div>}
      {data && !loading && (
        <div>
          <div className="flex flex-wrap items-center gap-2 px-5 pt-4">
            <TypeBadge type={data.type} />
            {data.file && <Badge className="border-white/10 bg-white/[0.03] font-mono text-ink-200">{data.file}{data.line ? `:${data.line}` : ''}</Badge>}
          </div>
          <div className="flex flex-wrap gap-2 px-5 pt-3">
            <Button size="sm" icon={Zap} onClick={() => onBlastRadius(componentId)}>Show blast radius</Button>
            {scenario && (
              <Link to={`/prediction?scenario=${scenario}&target=${encodeURIComponent(componentId)}`}>
                <Button size="sm" variant="primary" icon={Radar}>Predict failure</Button>
              </Link>
            )}
          </div>
          <div className="mt-4 flex gap-1 border-b border-white/[0.06] px-5" role="tablist">
            {TABS.map((name) => (
              <button key={name} role="tab" aria-selected={tab === name} onClick={() => setTab(name)} className={`relative px-3 py-2 text-xs font-medium ${tab === name ? 'text-ink-100' : 'text-ink-400 hover:text-ink-200'}`}>
                {name}
                {name === 'Findings' && data.findings.length > 0 && <span className="ml-1 text-rose-300">{data.findings.length}</span>}
                {tab === name && <motion.span layoutId="drawer-tab" className="absolute inset-x-1 -bottom-px h-0.5 rounded-full bg-violet-400" />}
              </button>
            ))}
          </div>
          <motion.div key={tab} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="p-5">
            {tab === 'Details' && (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-2">
                  {[
                    ['Criticality', data.metrics.criticality],
                    ['Dependents', data.metrics.dependents],
                    ['Depends on', data.metrics.dependencies],
                    ['Routes affected', data.metrics.routes_depending],
                    ['Tests covering', data.metrics.tests_covering],
                    ['Betweenness', data.metrics.betweenness],
                  ].map(([k, v]) => (
                    <div key={k} className="rounded-lg border border-white/[0.05] bg-ink-900/60 p-2.5">
                      <div className="text-[10px] uppercase tracking-wider text-ink-400">{k}</div>
                      <div className="mt-0.5 font-medium tabular-nums text-ink-100">{v ?? '—'}</div>
                    </div>
                  ))}
                </div>
                {data.data?.method && <Row k="HTTP" v={<span className="font-mono">{data.data.method} {data.data.path}</span>} />}
                {data.data?.handler && <Row k="Handler" v={<button className="font-mono text-violet-200 hover:underline" onClick={() => onSelectNode(data.data.handler)}>{shortId(data.data.handler)}</button>} />}
                {data.data?.framework && <Row k="Framework" v={data.data.framework} />}
                {data.data?.engine && <Row k="Engine" v={data.data.engine} />}
                {data.data?.launcher_methods && <Row k="Starts via" v={data.data.launcher_methods.join(', ')} />}
                {data.data?.raises?.length > 0 && <Row k="Raises" v={data.data.raises.join(', ')} />}
                {data.data?.args?.length > 0 && <Row k="Arguments" v={<span className="font-mono">{data.data.args.join(', ')}</span>} />}
                {data.data?.nodeid && <Row k="Pytest id" v={<span className="break-all font-mono">{data.data.nodeid}</span>} />}
                {data.data?.sql?.length > 0 && (
                  <div>
                    <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-400">SQL statements</div>
                    {data.data.sql.map((s, i) => (
                      <code key={i} className="mb-1 block rounded bg-ink-900 px-2 py-1 font-mono text-[11px] text-amber-100/90">L{s.line}: {s.statement}</code>
                    ))}
                  </div>
                )}
                <div className="text-xs text-ink-400">
                  {data.upstream.length} components depend on this (upstream) · it depends on {data.downstream.length} (downstream).
                </div>
              </div>
            )}
            {tab === 'Relationships' && (
              <div className="space-y-4">
                <Section title={`Depends on (${data.outgoing.filter((e) => e.type !== 'contains').length})`}>
                  {data.outgoing.filter((e) => e.type !== 'contains').map((e) => <EdgeRow key={e.id} edge={e} otherId={e.target} direction="out" onSelectNode={onSelectNode} />)}
                </Section>
                <Section title={`Used by (${data.incoming.filter((e) => e.type !== 'contains').length})`}>
                  {data.incoming.filter((e) => e.type !== 'contains').map((e) => <EdgeRow key={e.id} edge={e} otherId={e.source} direction="in" onSelectNode={onSelectNode} />)}
                </Section>
              </div>
            )}
            {tab === 'Source' &&
              (data.source_excerpt ? (
                <pre className="overflow-x-auto rounded-lg border border-white/[0.06] bg-ink-950 p-3 font-mono text-[11px] leading-relaxed text-ink-200">{data.source_excerpt}</pre>
              ) : (
                <p className="text-sm text-ink-400">No source excerpt for this component type (resources like databases and env variables are inferred from the code that uses them; see Relationships).</p>
              ))}
            {tab === 'Findings' &&
              (data.findings.length ? (
                <ul className="space-y-2">
                  {data.findings.map((f) => (
                    <li key={f.id} className="rounded-lg border border-white/[0.06] bg-ink-900/50 p-3">
                      <div className="flex items-center gap-2"><SeverityBadge severity={f.severity} /><span className="text-sm text-ink-100">{f.title}</span></div>
                      <p className="mt-1 text-xs text-ink-300">{f.description}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-ink-400">No findings attached to this component.</p>
              ))}
          </motion.div>
          <div className="px-5 pb-5">
            <button onClick={() => onSelectNode(componentId, true)} className="flex items-center gap-1.5 text-xs text-ink-400 hover:text-ink-200">
              <Crosshair className="h-3 w-3" /> Center in graph
            </button>
          </div>
        </div>
      )}
    </Drawer>
  )
}

function Row({ k, v }) {
  return (
    <div className="flex gap-3 text-sm">
      <span className="w-24 shrink-0 text-ink-400">{k}</span>
      <span className="min-w-0 text-ink-100">{v}</span>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-medium uppercase tracking-wider text-ink-400">{title}</div>
      <ul className="space-y-1.5">{children}</ul>
    </div>
  )
}
