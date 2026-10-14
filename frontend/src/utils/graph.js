import dagre from '@dagrejs/dagre'
import { PROPAGATING } from './constants'

/**
 * Nodes that depend on `id` (upstream: they break if `id` breaks) and nodes `id` depends on (downstream).
 * Edges point from dependent -> dependency, matching the backend.
 */
export function neighbourhood(edges, id) {
  const prop = edges.filter((e) => PROPAGATING.includes(e.type))
  const walk = (start, next) => {
    const seen = new Set()
    const stack = [start]
    while (stack.length) {
      const cur = stack.pop()
      for (const n of next(cur)) {
        if (!seen.has(n) && n !== start) {
          seen.add(n)
          stack.push(n)
        }
      }
    }
    return seen
  }
  const incoming = (n) => prop.filter((e) => e.target === n).map((e) => e.source)
  const outgoing = (n) => prop.filter((e) => e.source === n).map((e) => e.target)
  return { upstream: walk(id, incoming), downstream: walk(id, outgoing) }
}

/** Keep only visible component types; drop edges whose ends are hidden or whose type is hidden. */
export function filterGraph(components, edges, { types, edgeTypes, query }) {
  const q = (query || '').trim().toLowerCase()
  const nodes = components.filter((c) => types.has(c.type))
  const ids = new Set(nodes.map((n) => n.id))
  const visibleEdges = edges.filter((e) => ids.has(e.source) && ids.has(e.target) && edgeTypes.has(e.type))
  const matches = q ? new Set(nodes.filter((n) => `${n.id} ${n.name} ${n.file || ''}`.toLowerCase().includes(q)).map((n) => n.id)) : null
  return { nodes, edges: visibleEdges, matches }
}

const NODE_W = 210
const NODE_H = 46

/** Left-to-right layered layout: tests -> routes -> handlers -> services -> resources. */
export function layout(nodes, edges) {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 14, ranksep: 70, marginx: 20, marginy: 20 })
  g.setDefaultEdgeLabel(() => ({}))
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }))
  edges.forEach((e) => g.setEdge(e.source, e.target))
  dagre.layout(g)
  const pos = {}
  nodes.forEach((n) => {
    const p = g.node(n.id)
    pos[n.id] = { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 }
  })
  return pos
}

export function shortId(id) {
  return id.replace(/^(func|class|module|app|worker|test):/, '')
}
