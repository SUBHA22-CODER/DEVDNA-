import { Background, Controls, MarkerType, MiniMap, ReactFlow, ReactFlowProvider, useReactFlow } from '@xyflow/react'
import { AnimatePresence, motion } from 'framer-motion'
import { Filter, LayoutGrid, Maximize2, Network, RotateCcw, Search, Sparkles, Table2, X, Zap } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ComponentDrawer, { EvidenceList } from '../components/graph/ComponentDrawer'
import GraphNode from '../components/graph/GraphNode'
import MultimodalAuditModal from '../components/MultimodalAuditModal'
import ProjectGate from '../components/ProjectGate'
import { Badge, Button, Card, ErrorState, EvidenceBadge, IconButton, Modal, PageHeader, Skeleton, TypeBadge } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'
import { EDGE_LABELS, NODE_TYPES } from '../utils/constants'
import { filterGraph, layout, neighbourhood, shortId } from '../utils/graph'

const nodeTypes = { dna: GraphNode }
const DEFAULT_TYPES = ['route', 'app', 'function', 'database', 'external_api', 'env_var', 'worker', 'test']
const DEFAULT_EDGES = ['calls', 'handled_by', 'served_by', 'runs_on_startup', 'uses_database', 'calls_http', 'reads_env', 'exercises', 'runs_worker']

export default function Architecture() {
  return (
    <ProjectGate>
      {(project) => (
        <ReactFlowProvider>
          <Explorer project={project} />
        </ReactFlowProvider>
      )}
    </ProjectGate>
  )
}

function Explorer({ project }) {
  const [params, setParams] = useSearchParams()
  const arch = useAsync(() => api.architecture(project.id), [project.id, project.latest_run_id])
  const predictionId = params.get('prediction')
  const prediction = useAsync(() => api.prediction(predictionId), [predictionId], { enabled: Boolean(predictionId) })
  const [view, setView] = useState('graph')
  const [types, setTypes] = useState(new Set(DEFAULT_TYPES))
  const [edgeTypes, setEdgeTypes] = useState(new Set(DEFAULT_EDGES))
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(params.get('focus'))
  const [drawerId, setDrawerId] = useState(params.get('focus'))
  const [blastOf, setBlastOf] = useState(null)
  const [edge, setEdge] = useState(null)
  const [showFilters, setShowFilters] = useState(false)
  const [auditModalOpen, setAuditModalOpen] = useState(false)
  const flow = useReactFlow()

  const components = arch.data?.components || []
  const edges = arch.data?.edges || []

  const graph = useMemo(() => filterGraph(components, edges, { types, edgeTypes, query }), [components, edges, types, edgeTypes, query])
  const positions = useMemo(() => layout(graph.nodes, graph.edges), [graph.nodes, graph.edges])

  // highlight state: prediction impact > blast radius > selection neighbourhood > search
  const highlight = useMemo(() => {
    const impact = prediction.data?.impact
    if (predictionId && impact) {
      const states = {}
      impact.seeds.forEach((s) => (states[s] = 'source'))
      impact.affected.forEach((a) => (states[a.id] = a.certainty === 'definite' ? 'impact-definite' : 'impact-possible'))
      impact.tests.forEach((t) => t.prediction !== 'pass' && (states[t.id] = t.prediction === 'fail' ? 'impact-definite' : 'impact-possible'))
      return { states, dimOthers: true, label: `Predicted impact: ${impact.scenario_label} on ${impact.target.name}` }
    }
    if (blastOf) {
      const { upstream } = neighbourhood(edges, blastOf)
      const states = { [blastOf]: 'source' }
      upstream.forEach((u) => (states[u] = 'impact-definite'))
      return { states, dimOthers: true, label: `Blast radius of ${shortId(blastOf)}: ${upstream.size} dependents (structural, ignores error handling)` }
    }
    if (selected) {
      const { upstream, downstream } = neighbourhood(edges, selected)
      const states = {}
      upstream.forEach((u) => (states[u] = 'upstream'))
      downstream.forEach((d) => (states[d] = 'downstream'))
      return { states, dimOthers: true, label: null }
    }
    if (graph.matches) {
      const states = {}
      graph.matches.forEach((m) => (states[m] = 'match'))
      return { states, dimOthers: true, label: `${graph.matches.size} matches` }
    }
    return { states: {}, dimOthers: false, label: null }
  }, [prediction.data, predictionId, blastOf, selected, edges, graph.matches])

  const rfNodes = useMemo(
    () =>
      graph.nodes.map((c) => {
        const state = highlight.states[c.id]
        return {
          id: c.id,
          type: 'dna',
          position: positions[c.id] || { x: 0, y: 0 },
          selected: c.id === selected,
          data: {
            id: c.id,
            type: c.type,
            label: c.type === 'function' ? c.name : c.type === 'test' ? c.name : c.name,
            sub: c.type === 'function' ? (c.data.module || '') : c.type === 'route' ? (shortId(c.data.handler || '')) : NODE_TYPES[c.type]?.label,
            criticality: c.type !== 'test' ? c.metrics?.criticality : 0,
            state,
            dimmed: highlight.dimOthers && !state && c.id !== selected,
          },
        }
      }),
    [graph.nodes, positions, highlight, selected],
  )

  const rfEdges = useMemo(
    () =>
      graph.edges.map((e) => {
        const s = highlight.states
        const active = (s[e.source] || e.source === selected) && (s[e.target] || e.target === selected)
        const impact = active && (String(s[e.source]).startsWith('impact') || s[e.target] === 'source')
        const color = impact ? '#f43f5e' : active ? '#a78bfa' : e.classification === 'inferred' ? '#3a3f52' : '#4b5168'
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          className: impact ? 'edge-flow' : '',
          style: { stroke: color, strokeWidth: active ? 1.8 : 1, opacity: highlight.dimOthers && !active ? 0.15 : 1, strokeDasharray: e.classification === 'inferred' && !impact ? '4 3' : undefined },
          markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
          data: e,
        }
      }),
    [graph.edges, highlight, selected],
  )

  const fit = useCallback(() => flow.fitView({ padding: 0.15, duration: 400 }), [flow])

  useEffect(() => {
    if (rfNodes.length) setTimeout(fit, 60)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph.nodes.length, types, arch.data])

  const focusNode = useCallback(
    (id, center = false) => {
      const c = components.find((x) => x.id === id)
      if (!c) return
      if (!types.has(c.type)) setTypes((t) => new Set([...t, c.type]))
      setSelected(id)
      setDrawerId(id)
      setBlastOf(null)
      if (center) {
        setTimeout(() => {
          const p = positions[id]
          if (p) flow.setCenter(p.x + 105, p.y + 23, { zoom: 1.2, duration: 500 })
        }, 50)
      }
    },
    [components, types, positions, flow],
  )

  useEffect(() => {
    const f = params.get('focus')
    if (f && components.length) focusNode(f, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [components.length])

  const reset = () => {
    setTypes(new Set(DEFAULT_TYPES))
    setEdgeTypes(new Set(DEFAULT_EDGES))
    setQuery('')
    setSelected(null)
    setDrawerId(null)
    setBlastOf(null)
    setParams({})
    setTimeout(fit, 80)
  }

  const toggle = (set, setter, key) => {
    const next = new Set(set)
    next.has(key) ? next.delete(key) : next.add(key)
    setter(next)
  }

  const counts = useMemo(() => {
    const out = {}
    components.forEach((c) => (out[c.type] = (out[c.type] || 0) + 1))
    return out
  }, [components])

  if (arch.error) return <ErrorState error={arch.error} onRetry={arch.reload} />

  return (
    <>
      <PageHeader
        eyebrow="Architecture Explorer"
        title="Component graph"
        subtitle="Every node and edge comes from static analysis of the source. Click a node for evidence; edges point from a component to what it depends on."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setAuditModalOpen(true)}
              className="gap-1.5 text-xs font-medium border-violet-500/30 text-violet-200 hover:bg-violet-500/10"
            >
              <Sparkles className="h-3.5 w-3.5 text-violet-400" />
              Visual Diagram Audit
            </Button>
            <div className="flex rounded-lg border border-white/[0.07] bg-ink-850 p-0.5">
              {[['graph', Network, 'Graph'], ['table', Table2, 'Table']].map(([v, Icon, label]) => (
                <button key={v} onClick={() => setView(v)} className={`relative flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium ${view === v ? 'text-ink-100' : 'text-ink-400'}`} aria-pressed={view === v}>
                  {view === v && <motion.span layoutId="arch-view" className="absolute inset-0 rounded-md bg-ink-700" />}
                  <Icon className="relative h-3.5 w-3.5" /> <span className="relative">{label}</span>
                </button>
              ))}
            </div>
          </div>
        }
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelected(null)
              setBlastOf(null)
            }}
            placeholder="Search components, files…"
            aria-label="Search components"
            className="h-9 w-full rounded-lg border border-ink-600 bg-ink-900 pl-9 pr-8 text-sm text-ink-100 outline-none focus:border-violet-400"
          />
          {query && (
            <button aria-label="Clear search" className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-400" onClick={() => setQuery('')}>
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <Button size="md" icon={Filter} onClick={() => setShowFilters((s) => !s)} variant={showFilters ? 'primary' : 'secondary'}>
          Filters
        </Button>
        <Button icon={Maximize2} onClick={fit}>Fit</Button>
        <Button icon={RotateCcw} onClick={reset}>Reset</Button>
        {selected && !blastOf && (
          <Button icon={Zap} variant="danger" onClick={() => setBlastOf(selected)}>Blast radius</Button>
        )}
      </div>

      <AnimatePresence>
        {showFilters && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <Card className="mb-3 space-y-3 p-3">
              <div>
                <div className="mb-1.5 text-[11px] uppercase tracking-wider text-ink-400">Component types</div>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(NODE_TYPES).filter(([k]) => counts[k]).map(([k, t]) => (
                    <button key={k} onClick={() => toggle(types, setTypes, k)} aria-pressed={types.has(k)}
                      className={`flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors ${types.has(k) ? 'border-white/15 bg-ink-700 text-ink-100' : 'border-white/[0.05] text-ink-500'}`}>
                      <span className="h-2 w-2 rounded-full" style={{ background: t.color, opacity: types.has(k) ? 1 : 0.3 }} />
                      {t.label} <span className="text-ink-400">{counts[k]}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-1.5 text-[11px] uppercase tracking-wider text-ink-400">Relationship types</div>
                <div className="flex flex-wrap gap-1.5">
                  {Object.keys(EDGE_LABELS).map((k) => (
                    <button key={k} onClick={() => toggle(edgeTypes, setEdgeTypes, k)} aria-pressed={edgeTypes.has(k)}
                      className={`rounded-md border px-2 py-1 text-xs ${edgeTypes.has(k) ? 'border-white/15 bg-ink-700 text-ink-100' : 'border-white/[0.05] text-ink-500'}`}>
                      {EDGE_LABELS[k]}
                    </button>
                  ))}
                </div>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {highlight.label && (
          <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mb-3 flex items-center justify-between gap-2 rounded-lg border border-rose-400/20 bg-rose-500/[0.06] px-3 py-2 text-sm text-rose-100">
            <span className="flex items-center gap-2"><Zap className="h-4 w-4" /> {highlight.label}</span>
            <IconButton icon={X} label="Clear highlight" onClick={() => { setBlastOf(null); setQuery(''); if (predictionId) setParams({}) }} />
          </motion.div>
        )}
      </AnimatePresence>

      {arch.loading && !arch.data ? (
        <Skeleton className="h-[640px] w-full" />
      ) : view === 'graph' ? (
        <Card className="relative h-[calc(100vh-17rem)] min-h-[520px] overflow-hidden">
          {rfNodes.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-ink-400">No components match the current filters.</div>
          ) : (
            <ReactFlow
              nodes={rfNodes}
              edges={rfEdges}
              nodeTypes={nodeTypes}
              onNodeClick={(_, n) => focusNode(n.id)}
              onEdgeClick={(_, e) => setEdge(e.data)}
              onPaneClick={() => { setSelected(null); setBlastOf(null) }}
              nodesConnectable={false}
              nodesDraggable
              minZoom={0.1}
              maxZoom={2}
              proOptions={{ hideAttribution: true }}
              fitView
            >
              <Background color="#1b1e29" gap={22} />
              <Controls showInteractive={false} position="bottom-left" />
              <MiniMap pannable zoomable nodeColor={(n) => NODE_TYPES[n.data.type]?.color || '#555'} maskColor="rgba(7,8,11,0.7)" className="!hidden md:!block" />
            </ReactFlow>
          )}
          <Legend />
        </Card>
      ) : (
        <ComponentTable components={graph.nodes} matches={graph.matches} onSelect={(id) => focusNode(id)} />
      )}

      <ComponentDrawer
        projectId={project.id}
        componentId={drawerId}
        onClose={() => setDrawerId(null)}
        onSelectNode={(id, center) => focusNode(id, center || view === 'graph')}
        onBlastRadius={(id) => { setBlastOf(id); setSelected(id); setDrawerId(null) }}
      />

      <Modal open={Boolean(edge)} onClose={() => setEdge(null)} title={edge ? `${EDGE_LABELS[edge.type] || edge.type}` : ''} subtitle={edge ? `${shortId(edge.source)} → ${shortId(edge.target)}` : ''}>
        {edge && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-ink-300">
              Evidence classification: <EvidenceBadge classification={edge.classification} />
            </div>
            <EvidenceList evidence={edge.evidence} />
            <div className="flex gap-2">
              <Button size="sm" onClick={() => { focusNode(edge.source, true); setEdge(null) }}>Open source</Button>
              <Button size="sm" onClick={() => { focusNode(edge.target, true); setEdge(null) }}>Open target</Button>
            </div>
          </div>
        )}
      </Modal>
      <MultimodalAuditModal open={auditModalOpen} onClose={() => setAuditModalOpen(false)} projectId={project.id} />
    </>
  )
}

function Legend() {
  const [open, setOpen] = useState(true)
  return (
    <div className="absolute right-3 top-3 z-10 w-48 rounded-lg border border-white/10 bg-ink-900/90 text-xs backdrop-blur">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between px-3 py-2 font-medium text-ink-200" aria-expanded={open}>
        <span className="flex items-center gap-1.5"><LayoutGrid className="h-3.5 w-3.5" /> Legend</span>
        <span className="text-ink-400">{open ? '–' : '+'}</span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
            <ul className="space-y-1 px-3 pb-2">
              {Object.entries(NODE_TYPES).filter(([k]) => k !== 'module').map(([k, t]) => (
                <li key={k} className="flex items-center gap-2 text-ink-300"><t.icon className="h-3 w-3" style={{ color: t.color }} /> {t.label}</li>
              ))}
            </ul>
            <div className="space-y-1 border-t border-white/[0.06] px-3 py-2 text-ink-300">
              <div className="flex items-center gap-2"><span className="h-px w-5 bg-[#6b7190]" /> confirmed edge</div>
              <div className="flex items-center gap-2"><span className="w-5 border-t border-dashed border-[#6b7190]" /> inferred edge</div>
              <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-violet-400" /> depends on selection</div>
              <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-cyan-400" /> selection depends on</div>
              <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-rose-400" /> failure impact</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function ComponentTable({ components, matches, onSelect }) {
  const [sort, setSort] = useState('criticality')
  const rows = [...components]
    .filter((c) => !matches || matches.has(c.id))
    .sort((a, b) => (sort === 'name' ? a.id.localeCompare(b.id) : (b.metrics?.[sort] || 0) - (a.metrics?.[sort] || 0)))
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06] text-left text-xs uppercase tracking-wider text-ink-400">
              {[['name', 'Component'], [null, 'Type'], [null, 'Location'], ['criticality', 'Criticality'], ['dependents', 'Dependents'], ['routes_depending', 'Routes'], ['tests_covering', 'Tests']].map(([key, label]) => (
                <th key={label} className="px-4 py-2.5 font-medium">
                  {key ? <button onClick={() => setSort(key)} className={sort === key ? 'text-violet-200' : 'hover:text-ink-200'}>{label}{sort === key ? ' ↓' : ''}</button> : label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id} onClick={() => onSelect(c.id)} className="cursor-pointer border-b border-white/[0.03] hover:bg-ink-700/30">
                <td className="max-w-xs truncate px-4 py-2 font-mono text-xs text-ink-100">{shortId(c.id)}</td>
                <td className="px-4 py-2"><TypeBadge type={c.type} /></td>
                <td className="px-4 py-2 font-mono text-xs text-ink-400">{c.file ? `${c.file}:${c.line}` : '—'}</td>
                <td className="px-4 py-2 tabular-nums">{c.type === 'test' ? '—' : c.metrics?.criticality}</td>
                <td className="px-4 py-2 tabular-nums">{c.metrics?.dependents}</td>
                <td className="px-4 py-2 tabular-nums">{c.metrics?.routes_depending}</td>
                <td className="px-4 py-2 tabular-nums">{c.metrics?.tests_covering}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-white/[0.05] px-4 py-2 text-xs text-ink-400">
        <Badge>{rows.length}</Badge> components shown
      </div>
    </Card>
  )
}
